"""Honesty guards for LLM-generated QA documents.

Two layers, both dependency-free (stdlib only):

1. Prompt rule blocks (``GROUNDING_RULES``, ``CITATION_RULES``,
   ``STANDARDS_RULES``) that the prompt builders embed so the model is told
   not to invent project facts, section citations, or standards mandates.
2. Deterministic post-processing (``sanitize_llm_markdown``) applied at every
   sink, because prompt rules reduce but never eliminate these failures
   (found by an exploratory QA pass over the live app, 2026-10).
"""

import re
from typing import Optional

GROUNDING_RULES = """\
GROUNDING RULES (these override any instinct to sound specific):
- Treat the PROJECT CONTEXT as the ONLY source of facts about this project. Never state
  as a fact anything about the project that the context does not say (infrastructure
  setup, legal pages, team roles, existing test data, tooling, past incidents).
- If something is unknown, write it as a gap or an assumption: "Not provided: <what> -
  verify with the team", or "Assuming <x> (not stated in the project context)". Never
  write the absence of something as a finding ("X is not configured", "there is no Y",
  "no prior Z exists") unless the context literally says so.
- Before writing that something is missing ("no dedicated X", "no regression suite"),
  re-read the PROJECT CONTEXT: if it lists that thing (e.g. an existing automation suite),
  the claim is false. Describe weaknesses of what IS listed instead of denying it exists.
- Use markdown bold only in matched pairs; never leave a lone ** (e.g. after an arrow).
- Risks may be conditional ("If <x> is not in place, ...") but must not assert that <x>
  is missing.
"""

CITATION_RULES = """\
CITATION RULES:
- Cite knowledge-base material only as [Source N], where N is a source actually numbered
  in the RELEVANT QA KNOWLEDGE BASE block above.
- Never cite section numbers, clause numbers, page numbers, or syllabus chapter titles
  (e.g. "<standard> (<section number> <title>)") unless that exact number appears in the provided
  knowledge-base text. Name the standard or document instead, without a section number.
- Never put words in a standard's mouth: do not write "<standard> states that ..." or
  use quotation marks around standard text unless the quoted words appear verbatim in the
  knowledge-base text. Otherwise paraphrase and attribute with [Source N].
"""

STANDARDS_RULES = """\
STANDARDS ACCURACY:
- ISTQB syllabi are bodies of knowledge for certification, not mandatory document
  templates. Never write "ISTQB-mandated", "ISTQB requires", or that a document is
  non-compliant with ISTQB.
- IEEE 829 / ISO/IEC/IEEE 29119-3 provide recommended document structures. Say a document
  "does not follow the recommended IEEE 829 structure", never that it "violates" a mandate.
- Keep the tone proportional to the score given: a mid-range score means "needs
  improvement", not "unusable" or "worthless".
"""

_STANDARD_NAME = r"(?:ISTQB|CTFL|CTAL|CT-[A-Z]+|OWASP|WSTG|MASTG|ISO|IEEE|TMMi|ASVS)"
# "<standard-ish token(s)> (3.1.3 Security Testing)" -> captures name and number.
_SECTION_REF = re.compile(
    rf"(?P<name>\b{_STANDARD_NAME}[\w\-/ .]{{0,30}}?)\s*"
    r"\((?:§|section\s+|clause\s+)?(?P<num>\d+(?:\.\d+)+)\b[^)\n]*\)",
    re.IGNORECASE,
)
_MANDATE = re.compile(r"\b(ISTQB|IEEE\s*829)[\s-]+mandated\b", re.IGNORECASE)
_UNUSABLE = re.compile(r"\bunusable\b", re.IGNORECASE)


def fix_stray_emphasis(text: str) -> str:
    """Drop an unmatched ``**`` on a line (e.g. ``-> **risk of timeouts`` with
    no closing pair), which Streamlit renders as literal asterisks. Lines with
    balanced pairs and fenced code blocks are left alone."""
    out = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.count("**") % 2 == 1:
            idx = line.rfind("**")
            line = line[:idx] + line[idx + 2:]
        out.append(line)
    return "\n".join(out)


_ABSENCE_CLAIM = re.compile(
    r"\bno (?:dedicated|prior|existing|formal|documented) [^.\n;:*()|]{2,60}?(?=\s*[.\n;:*(),|]|$)",
    re.IGNORECASE,
)
_ABSENCE_QUALIFIER = " (not stated in the project context)"


_CONTEXT_BLOCK = re.compile(
    r"PROJECT CONTEXT:\s*(.*?)(?=\n\s*(?:RELEVANT QA KNOWLEDGE BASE|RISK REGISTER|MEASURED EXECUTION DATA)|\Z)",
    re.DOTALL,
)
_CLAIM_FILLER = {"dedicated", "prior", "existing", "formal", "documented"}
_CONTRADICTION_NOTE = " (project context lists related coverage - assess its adequacy, not its absence)"


def project_context_of(prompt: Optional[str]) -> str:
    """The PROJECT CONTEXT block of a generator prompt ("" when absent)."""
    m = _CONTEXT_BLOCK.search(prompt or "")
    return m.group(1).lower() if m else ""


def qualify_absence_claims(text: str, context_text: str = "") -> str:
    """The model keeps asserting unprovided absences as fact ("No dedicated
    security specialist"). Whether something is missing is unknowable from the
    intake, so append an explicit "not stated" qualifier -- turning a false
    finding into an honest gap. When the claim shares a content word with the
    project context (e.g. "no dedicated regression suite" vs a listed "E2E test
    suite"), the context actively contradicts it, so say that instead.
    Idempotent."""

    def _repl(m: "re.Match") -> str:
        tail = text[m.end():m.end() + 80].lstrip("* ")
        if tail.startswith(("(not stated", "(project context")) or "not stated" in m.group(0):
            return m.group(0)
        words = {w for w in re.findall(r"[a-z0-9]{5,}", m.group(0).lower()) if w not in _CLAIM_FILLER}
        if context_text and any(w in context_text for w in words):
            # The context contradicts "no ..." outright, so don't keep the denial.
            return re.sub(r"^no\b", "Limited", m.group(0), flags=re.I) + _CONTRADICTION_NOTE
        return m.group(0) + _ABSENCE_QUALIFIER

    return _ABSENCE_CLAIM.sub(_repl, text)


def lint_output(text: str, context_text: str = "") -> list:
    """Problems that must never survive sanitizing (used by the live smoke
    script and tests as the "won't happen again" gate)."""
    problems = []
    if any(line.count("**") % 2 for line in text.split("\n") if not line.lstrip().startswith("```")):
        problems.append("lone ** markdown marker")
    if _MANDATE.search(text) or _UNUSABLE.search(text):
        problems.append("standards overstatement (mandated/unusable)")
    for m in _ABSENCE_CLAIM.finditer(text):
        tail = text[m.end():m.end() + 80].lstrip("* ")
        if not tail.startswith(("(not stated", "(project context")) and "not stated" not in m.group(0):
            problems.append(f"unqualified absence claim: {m.group(0)!r}")
    return problems

_NORMATIVE = re.compile(r"\b(mandatory|mandated|required)\b", re.IGNORECASE)
_STANDARD_IN_SENTENCE = re.compile(r"\b(?:ISTQB|IEEE\s*829|29119)\b", re.IGNORECASE)


def _soften_normative_sentences(text: str) -> str:
    """"X is a mandatory element ... per IEEE 829 and ISTQB": neither prescribes
    mandatory sections, so downgrade the normative word in any sentence that
    attributes it to those standards. Sentences without them are untouched."""

    def _fix(sentence: str) -> str:
        if _STANDARD_IN_SENTENCE.search(sentence):
            return _NORMATIVE.sub(lambda m: "recommended", sentence)
        return sentence

    return "\n".join(
        "".join(_fix(s) for s in re.split(r"(?<=[.!?])(\s+)", line)) for line in text.split("\n")
    )


def soften_standards_claims(text: str) -> str:
    """Rewrite known overstatements about what standards mandate."""
    text = _MANDATE.sub(lambda m: f"{m.group(1)}-recommended", text)
    text = _soften_normative_sentences(text)
    return _UNUSABLE.sub("of limited use as written", text)


def strip_unverifiable_section_refs(text: str, source_text: Optional[str]) -> str:
    """Remove ``(3.1.3 Title)`` section parentheticals after a standard's name
    when that section number never appears in ``source_text`` (the prompt that
    carried the retrieved knowledge). Without a source, nothing is stripped."""
    if not source_text:
        return text

    def _repl(m: "re.Match") -> str:
        return m.group(0) if m.group("num") in source_text else m.group("name").rstrip()

    return _SECTION_REF.sub(_repl, text)


_SOURCE_LABEL = re.compile(r"\[Source (\d+) —")
_SOURCE_CITE = re.compile(r"\s?\[Source (\d+)\]")
_QUOTE = re.compile(r"[\"“]([^\"”\n]{40,300})[\"”]")


def _normalize(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def drop_invalid_source_citations(text: str, source_text: Optional[str]) -> str:
    """Remove ``[Source N]`` markers whose N is not a source actually present in
    the prompt's knowledge block (no-op when the prompt carried none)."""
    valid = {int(n) for n in _SOURCE_LABEL.findall(source_text or "")}
    if not valid:
        return text
    return _SOURCE_CITE.sub(lambda m: m.group(0) if int(m.group(1)) in valid else "", text)


def unquote_unverified_quotes(text: str, source_text: Optional[str]) -> str:
    """A long quoted passage that does not appear verbatim in the prompt (project
    context or retrieved knowledge) was invented or reworded by the model, so
    drop the quotation marks and let it read as the paraphrase it is."""
    if not source_text or not _SOURCE_LABEL.search(source_text):
        return text
    haystack = _normalize(source_text)

    def _repl(m: "re.Match") -> str:
        return m.group(0) if _normalize(m.group(1)) in haystack else m.group(1)

    return _QUOTE.sub(_repl, text)

def sanitize_llm_markdown(text: str, source_text: Optional[str] = None) -> str:
    """Apply every deterministic guard. ``source_text`` is the prompt (or its
    knowledge block) the answer was generated from."""
    text = fix_stray_emphasis(text)
    text = soften_standards_claims(text)
    text = qualify_absence_claims(text, project_context_of(source_text))
    text = strip_unverifiable_section_refs(text, source_text)
    text = drop_invalid_source_citations(text, source_text)
    return unquote_unverified_quotes(text, source_text)
