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


def qualify_absence_claims(text: str) -> str:
    """The model keeps asserting unprovided absences as fact ("No dedicated
    security specialist"). Whether something is missing is unknowable from the
    intake, so append an explicit "not stated" qualifier -- turning a false
    finding into an honest gap. Idempotent."""

    def _repl(m: "re.Match") -> str:
        tail = text[m.end():m.end() + 40].lstrip("* ")
        if tail.startswith("(not stated") or "not stated" in m.group(0):
            return m.group(0)
        return m.group(0) + _ABSENCE_QUALIFIER

    return _ABSENCE_CLAIM.sub(_repl, text)


def soften_standards_claims(text: str) -> str:
    """Rewrite known overstatements about what standards mandate."""
    text = _MANDATE.sub(lambda m: f"{m.group(1)}-recommended", text)
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


def sanitize_llm_markdown(text: str, source_text: Optional[str] = None) -> str:
    """Apply every deterministic guard. ``source_text`` is the prompt (or its
    knowledge block) the answer was generated from."""
    text = fix_stray_emphasis(text)
    text = soften_standards_claims(text)
    text = qualify_absence_claims(text)
    return strip_unverifiable_section_refs(text, source_text)
