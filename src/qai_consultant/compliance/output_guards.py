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

# Also appended to GROUNDING_RULES, so every generator prompt that embeds
# GROUNDING_RULES already carries it; exported separately for any prompt that
# does not. The text deliberately names no regulator, so the prompt cannot
# whitelist one for the sanitizer's "absent from the source" check.
REGULATORY_RULES = """\
- Never name a specific regulator, supervisory authority, statute, directive, market-code,
  penalty or fine amount, record-retention period, or regulatory reporting format unless it
  appears in the PROJECT CONTEXT or in the retrieved knowledge-base text. Do not recall
  them from memory, and do not guess which body supervises or fines whom. Write
  "applicable regulations (to be confirmed with a domain/legal expert)" instead.
"""

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
- Never assert the seniority, experience level, or skills of the team, or tooling and
  process facts (CI/CD, peer review, version control, environments) that the intake does
  not state. Mark any such assumption explicitly as an assumption.
- Never invent specific SLAs, latencies, throughputs, fines, monetary amounts, break-even
  points, or effort uplifts and present them as facts. A figure that is not in the PROJECT
  CONTEXT or the knowledge base must be labelled "illustrative, not from the project
  context", or replaced by "to be defined with the team".
""" + REGULATORY_RULES

CITATION_RULES = """\
CITATION RULES:
- Cite knowledge-base material only as [Source N], where N is a source actually numbered
  in the RELEVANT QA KNOWLEDGE BASE block above.
- Never cite section numbers, clause numbers, page numbers, or syllabus chapter titles
  (e.g. "<standard> (<section number> <title>)") unless that exact number appears in the provided
  knowledge-base text. Name the standard or document instead, without a section number.
- Name an ISTQB syllabus or any standard exactly as it appears in the [Source N] header
  or knowledge-base text, and never add a version number or a year in parentheses that
  is not written there. Do not mix naming styles for the same syllabus.
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
- Keep the tone calibrated and proportional to the score given: a mid-range score means
  "needs improvement". Never use absolutes such as "fundamentally incomplete", "unusable",
  "worthless", or "fails to meet" a standard; say what is missing and what to add.
"""

NUMERIC_RULES = """\
NUMERIC TARGETS:
- Any number that is a threshold, SLA, target, or quota (response times, percentages,
  coverage levels, defect rates, sample or spot-check rates, bug-fix deadlines, device
  counts, effort splits) and is NOT in the PROJECT CONTEXT is an invented number. Write it
  as "suggested target, to be agreed" (or "proposed"), never as a project requirement,
  and never as an established fact.
- Prefer a measurable criterion without a number ("agreed latency budget, to be defined
  with the team") over an invented figure.
"""

SCOPE_RULES = """\
SCOPE AND TOOLS:
- Do not add features, user flows, integrations, platforms, or compliance areas that the
  PROJECT CONTEXT never mentions. If one seems relevant, list it as "Out of scope unless
  confirmed" or as a question for the team.
- Name a specific third-party tool or product only if it is in the stated tech stack or
  tools. Otherwise name the tool category, or label the suggestion "option to evaluate".
"""

STYLE_RULES = """\
STYLE:
- Never use em dashes or en dashes as punctuation. Use a comma, colon, parentheses, or a
  new sentence instead. Do not leave stray semicolons used as separators inside table cells.
"""

# Embedded by every document generator prompt, after GROUNDING_RULES/CITATION_RULES.
GENERATION_RULES = NUMERIC_RULES + SCOPE_RULES + STYLE_RULES

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
    r"\bno (?:(?:dedicated|prior|existing|formal|documented) [^.\n;:*()|]{2,60}?"
    r"|(?:CI/CD|CI|continuous integration|peer review|code review|version control|issue tracker"
    r"|test management|test environments?|staging environments?)\b[^.\n;:*()|]{0,40}?)"
    r"(?=\s*[.\n;:*(),|]|$)",
    re.IGNORECASE,
)
_ABSENCE_QUALIFIER = " (not stated in the project context)"


_CONTEXT_BLOCK = re.compile(
    r"PROJECT CONTEXT:\s*(.*?)(?=\n\s*(?:RELEVANT QA KNOWLEDGE BASE|RISK REGISTER|MEASURED EXECUTION DATA|MULTIPLIERS APPLIED)|\Z)",
    re.DOTALL,
)
_CLAIM_FILLER = {"dedicated", "prior", "existing", "formal", "documented"}
_CONTRADICTION_NOTE = " (project context lists related coverage - assess its adequacy, not its absence)"


def project_context_of(prompt: Optional[str]) -> str:
    """The PROJECT CONTEXT block of a generator prompt ("" when absent)."""
    m = _CONTEXT_BLOCK.search(prompt or "")
    return m.group(1).lower() if m else ""


_AUTOMATION_WORDS = {
    "automation", "automated", "framework", "suite", "scripts", "tooling", "regression",
}
_NEGATED_VALUE = re.compile(
    r"^\W*(?:no|none|not|without|zero|nil|n/a|nothing|never|absent|missing)\b|\bno\b[^.\n]{0,40}\byet\b|\bnone\b",
    re.IGNORECASE,
)


def _claim_words(claim: str) -> set:
    return {w for w in re.findall(r"[a-z0-9/]{5,}", claim.lower()) if w not in _CLAIM_FILLER}


def _absence_verdict(claim: str, context_text: str) -> str:
    """How the PROJECT CONTEXT relates to an absence claim: ``"asserted"`` (a
    context line mentions the thing without negating it, so the denial is
    false), ``"supported"`` (the only related lines themselves state the
    absence, so the denial is true and must be left alone), or ``"unknown"``."""
    if not context_text:
        return "unknown"
    words = _claim_words(claim)
    if not words:
        return "unknown"
    automation_claim = bool(words & _AUTOMATION_WORDS)
    asserted = supported = False
    for line in context_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        label, _, value = line.partition(":") if ":" in line else ("", "", line)
        # Whole-word match only: "automatically trades the battery" in the project
        # description is not a claim that an automation suite exists.
        # With "Label: value" lines, only fields describing existing assets can
        # contradict a denial ("Compliance: GDPR" is a requirement, not prior
        # compliance testing); free text without a label keeps the whole-line match.
        label = label.replace("_", " ")
        label_ok = (
            not label
            or bool(re.search(r"\bautomat\w*|\btests?\b|\btool\w*|\bexisting\b|\bsetup\b|\binfrastructure\b|\bprocess\w*", label))
            or (
                any(w in label for w in words)
                and not re.search(r"\bdescri\w*|\bcompliance\b|\bregulat\w*|\brisks?\b|\bcontext\b", label)
            )
        )
        related = (label_ok and any(re.search(rf"\b{re.escape(w)}\b", line) for w in words)) or (
            automation_claim and bool(re.search(r"\bautomat(?:ion|ed)\b|\btests?\b", label))
        )
        if not related:
            continue
        if _NEGATED_VALUE.search(value.strip()):
            supported = True
        else:
            asserted = True
    if asserted:
        return "asserted"
    return "supported" if supported else "unknown"


def qualify_absence_claims(text: str, context_text: str = "") -> str:
    """The model keeps asserting unprovided absences as fact ("No dedicated
    security specialist"). Whether something is missing is unknowable from the
    intake, so append an explicit "not stated" qualifier -- turning a false
    finding into an honest gap. When the project context itself lists the thing
    (e.g. "no dedicated regression suite" vs a listed "E2E test suite"), it
    contradicts the denial, so say that instead. When the context itself states
    the absence ("Existing Automation: No automation yet"), the denial is
    supported and left untouched. Idempotent."""

    def _repl(m: "re.Match") -> str:
        tail = text[m.end():m.end() + 80].lstrip("* ")
        if tail.startswith(("(not stated", "(project context")) or "not stated" in m.group(0):
            return m.group(0)
        verdict = _absence_verdict(m.group(0), context_text)
        if verdict == "supported":
            return m.group(0)
        if verdict == "asserted":
            # The context contradicts "no ..." outright, so don't keep the denial.
            return re.sub(r"^no\b", "Limited", m.group(0), flags=re.I) + _CONTRADICTION_NOTE
        return m.group(0) + _ABSENCE_QUALIFIER

    return _ABSENCE_CLAIM.sub(_repl, text)


_PEOPLE_TRAIT = r"(?:senior|junior|experienc\w*|skilled|expert\w*|seasoned|mid-level|proficien\w*)"
_ASSUMED_PEOPLE = re.compile(
    rf"\s*\((?=[^()\n]*\bassum)(?=[^()\n]*\b(?P<trait>{_PEOPLE_TRAIT})\b)[^()\n]*\)",
    re.IGNORECASE,
)
ASSUMED_PEOPLE_NOTE = " (assumption, not stated in the project context)"


def qualify_assumed_people_traits(text: str, context_text: str = "") -> str:
    """"Team is small but experienced (assumed, since they're senior)": the
    seniority is an invention. Replace the parenthetical with an explicit
    "assumption, not stated" note unless the intake itself mentions that trait.
    Idempotent (the note carries no trait word)."""

    def _repl(m: "re.Match") -> str:
        trait = m.group("trait").lower()
        stem = trait[:6] if trait.startswith(("experienc", "expert", "proficien")) else trait
        if stem in context_text:
            return m.group(0)
        return ASSUMED_PEOPLE_NOTE

    return _ASSUMED_PEOPLE.sub(_repl, text)


def lint_output(text: str, context_text: str = "", knowledge_text: str = "") -> list:
    """Problems that must never survive sanitizing (used by the live smoke
    script and tests as the "won't happen again" gate)."""
    problems = []
    if any(line.count("**") % 2 for line in text.split("\n") if not line.lstrip().startswith("```")):
        problems.append("lone ** markdown marker")
    if _MANDATE.search(text) or _UNUSABLE.search(text):
        problems.append("standards overstatement (mandated/unusable)")
    for m in _ABSENCE_CLAIM.finditer(text):
        tail = text[m.end():m.end() + 80].lstrip("* ")
        if (
            not tail.startswith(("(not stated", "(project context"))
            and "not stated" not in m.group(0)
            and _absence_verdict(m.group(0), context_text.lower()) != "supported"
        ):
            problems.append(f"unqualified absence claim: {m.group(0)!r}")
    if qualify_assumed_people_traits(text, context_text.lower()) != text:
        problems.append("assumed seniority/experience not stated in the project context")
    if replace_dashes(text) != text:
        problems.append("em/en dash used as punctuation")
    if clean_separator_debris(text) != text:
        problems.append("stray semicolon separator")
    if soften_absolute_tone(text) != text:
        problems.append("absolute tone (fundamentally/fails to meet)")
    if context_text:
        for _end, m in _threshold_hits(text, context_text.lower()):
            problems.append(f"unflagged invented threshold: {m.group(0)!r}")
        for snippet in _unflagged_regulatory_tokens(text, context_text.lower()):
            problems.append(f"unverified regulatory claim: {snippet!r}")
        for _end, m in _figure_hits(text, context_text.lower() + "\n" + knowledge_text.lower(), context_text.lower()):
            problems.append(f"unflagged invented figure: {m.group(0)!r}")
        for _end, name in _tool_hits(text, context_text):
            problems.append(f"unflagged tool outside the stated stack: {name!r}")
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

# -- dashes, table debris, tone, versions, invented thresholds -----------------

_DASH = re.compile(r"\s*[—–]\s*")
_SOURCE_LABEL_DASH = re.compile(r"(\[Source \d+)\s*[—–]\s*")
_NUM_RANGE_EN = re.compile(r"(?<=\d)–(?=\d)")
_TABLE_SPLIT = re.compile(r"(?<!\\)\|")
_DASH_CHARS = ("—", "–")


def _dash_to_punct(line: str) -> str:
    line = _SOURCE_LABEL_DASH.sub(r"\1: ", line)
    line = _NUM_RANGE_EN.sub("-", line)

    def _repl(m: "re.Match") -> str:
        before = line[:m.start()].rstrip()
        return ": " if before.endswith(("**", "__")) else ", "

    return _DASH.sub(_repl, line)


# "64.4 – 181.8" / "20% – 25%": a spaced dash between two figures is a range
_NUM_RANGE_DASH = re.compile(r"(\d(?:[\d.,]*\d)?[%a-z]{0,2}) [—–] (?=\d)")


def replace_dashes(text: str) -> str:
    """No em/en dashes as punctuation in text written for the user. Headings
    ``A - B`` become ``A: B``; elsewhere a dash becomes ", " (": " after a bold
    label). Fenced code, and table cells that are only a dash (the "empty"
    placeholder), are left alone."""
    out = []
    in_fence = False
    text = _NUM_RANGE_DASH.sub(r"\1 to ", text)
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
        elif in_fence or not any(d in line for d in _DASH_CHARS):
            out.append(line)
        elif re.match(r"\s*#{1,6}\s", line):
            out.append(_dash_to_punct(_DASH.sub(": ", line, count=1)))
        elif line.lstrip().startswith("|"):
            cells = _TABLE_SPLIT.split(line)
            out.append("|".join(c if c.strip() in _DASH_CHARS else _dash_to_punct(c) for c in cells))
        else:
            out.append(_dash_to_punct(line))
    return "\n".join(out)


def _tidy_cell(c: str) -> str:
    pad_l = " " if c.startswith(" ") else ""
    pad_r = " " if c.endswith(" ") else ""
    c = re.sub(r"\s+;", ";", c)
    c = re.sub(r";(?:\s*;)+", ";", c)
    c = c.strip().lstrip(";").strip()
    if not re.search(r"&#?\w+;$", c):  # keep a trailing HTML entity intact
        c = c.rstrip(";").rstrip()
    return f"{pad_l}{c}{pad_r}" if c else c


def clean_separator_debris(text: str) -> str:
    """``<br>`` cells become "; " joins, which the model's own spacing turns into
    stray `` ; `` / leading / trailing / doubled semicolons. Tidy them inside
    table rows, and fix the `` ; `` spacing in prose. Fenced code is untouched."""
    out = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and ";" in line:
            if line.lstrip().startswith("|"):
                parts = _TABLE_SPLIT.split(line)
                line = "|".join(
                    _tidy_cell(c) if 0 < i < len(parts) - 1 else c for i, c in enumerate(parts)
                )
            else:
                line = re.sub(r"(?<=\w) +; ", "; ", line)
        out.append(line)
    return "\n".join(out)


_ABSOLUTE_ADJ = re.compile(
    r"\b(?:fundamentally|utterly|completely|totally)\s+"
    r"(?=(?:incomplete|flawed|broken|inadequate|deficient|insufficient|lacking)\b)",
    re.IGNORECASE,
)
_FAILS_TO_MEET = re.compile(r"\b(fails|fail) to meet\b", re.IGNORECASE)
_STANDARD_ANY = re.compile(r"\b(?:ISTQB|IEEE|29119|ISO|TMMi|OWASP|CT[A-Za-z]*-[A-Za-z]+)\b")


def soften_absolute_tone(text: str) -> str:
    """Drop "fundamentally"-style intensifiers before deficiency words and
    rewrite "fails to meet <standard>" (only in sentences that name a standard,
    so a risk like "the API fails to meet its SLA" is untouched)."""
    text = _ABSOLUTE_ADJ.sub("", text)

    def _fix(sentence: str) -> str:
        if _STANDARD_ANY.search(sentence):
            return _FAILS_TO_MEET.sub(
                lambda m: "does not yet meet" if m.group(1).lower() == "fails" else "do not yet meet",
                sentence,
            )
        return sentence

    return "\n".join(
        "".join(_fix(s) for s in re.split(r"(?<=[.!?])(\s+)", line)) for line in text.split("\n")
    )


_SYLLABUS_VERSION = re.compile(
    r"(?P<name>\b(?:CTFL|CTAL(?:-[A-Z]{2,3})?|CTEL-ITP|CT-[A-Z][A-Z0-9-]*)\b)"
    r"(?P<ver>\s+v?\d+(?:\.\d+)+(?:\s*\(\d{4}\))?|\s*\(v?\d+(?:\.\d+)*(?:,?\s*\d{4})?\)|\s*\(\d{4}\))",
    re.IGNORECASE,
)


def strip_unverified_syllabus_versions(text: str, source_text: Optional[str]) -> str:
    """"CT-MAT v1.0 (2019)": a version/year after an ISTQB syllabus name that is
    not written verbatim in the prompt is invented or inconsistent, so drop the
    qualifier. Without a source, nothing is stripped."""
    if not source_text:
        return text
    haystack = source_text.lower()

    def _repl(m: "re.Match") -> str:
        return m.group(0) if m.group(0).lower() in haystack else m.group("name")

    return _SYLLABUS_VERSION.sub(_repl, text)


_THRESHOLD = re.compile(
    r"(?:(?:\b(?:under|below|within|less than|at most|no more than|at least|above|over|more than|minimum of)\b|"
    r"[<>≤≥]=?)\s*"
    r"(?P<n1>\d+(?:\.\d+)?)\s*(?:%|ms\b|seconds?\b|secs?\b|minutes?\b|min\b|s\b|h\b|hours?\b)"
    r"(?:\s*\(p\d+\))?"
    r"(?:\s+(?:[\w-]+\s+){0,2}?(?:coverage|false positives?|pass rate|failure rate|error rate|defect leakage)\b)?"
    r"|"
    r"\b(?P<n2>\d{1,3})\s*%\s+(?:[\w-]+\s+){0,2}?(?:coverage|false positives?|pass rate|spot-check rate|defect leakage)\b"
    r"|"
    # bare quantities with no comparator: "5+ real devices", "24h/48h SLAs", "80% of effort"
    r"\b(?P<n3>\d{1,3})\+\s+(?:[\w-]+\s+){0,2}?(?:devices?|browsers?|users?|testers?|engineers?|environments?)\b"
    r"|"
    r"\b(?P<n4>\d{1,3})\s*h(?:ours?)?\s*/\s*\d{1,3}\s*h(?:ours?)?\b(?:\s+SLAs?)?"
    r"|"
    r"\b(?P<n5>\d{1,3})\s*%\s+of\s+(?:the\s+)?(?:testing\s+|total\s+|QA\s+)?(?:effort|time|budget|capacity)\b)",
    re.IGNORECASE,
)
_FLAG_WORDS = re.compile(
    r"suggested|proposed|to be agreed|to be defined|to be confirmed|assum|illustrative|"
    r"for example|e\.g\.|option to evaluate",
    re.IGNORECASE,
)
THRESHOLD_FLAG = " (suggested target)"


_FIGURE = re.compile(
    # throughput: "100+ requests/sec", "50 tps"
    r"\b(?P<f1>\d[\d,]*)\+?\s*(?:req(?:uest)?s?|transactions?|messages?|orders?)\s*(?:/|per\s+)\s*(?:sec(?:ond)?s?|s|min(?:ute)?s?)\b"
    r"|\b(?P<f2>\d[\d,]*)\+?\s*tps\b"
    # currency amounts: "€100K+", "$2M", "100 000 EUR"
    r"|[€$£]\s?(?P<f3>\d[\d,.]*)\s?[KkMm]?\+?"
    r"|\b(?P<f4>\d[\d,.]*)\s?[KkMm]?\+?\s?(?:EUR|USD|GBP)\b"
    # unquantified-but-specific money claims: "could cost millions"
    r"|\b(?:cost|costs|costing|lose|losing|lost|loss(?:es)? of)\s+(?:\w+\s+){0,2}?(?P<f5>millions|thousands)\b"
    # fix/response SLAs: "24-hour SLA", "48h for High"
    r"|\b(?P<f6>\d{1,3})\s*-?\s*h(?:ours?|rs?)?\s+(?:SLAs?\b|(?:for|to fix|to resolve)\s+(?:Critical|High|Medium|Low|P\d|Sev\w*))"
    # effort uplifts: "20% extra effort"
    r"|\b(?P<f7>\d{1,3})\s*%\s+(?:extra|additional|more|buffer|contingency)\b(?:\s+\w+){0,2}?\s*(?:effort|time|budget|capacity)?"
    # break-even / cycles: "~4 regression cycles"
    r"|~?\b(?P<f8>\d{1,2})\s+(?:regression|test|release|execution)\s+(?:cycles|runs|iterations)\b"
    # state-of-charge style limits: "90% SoC", "exceed 90%"
    r"|\b(?P<f9>\d{1,3})\s*%\s*(?:SoC|SoH|DoD|state of charge)\b"
    r"|\bexceed(?:s|ing)?\s+(?P<f10>\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
_FIGURE_GROUPS = tuple(f"f{i}" for i in range(1, 11))
FIGURE_FLAG = " (illustrative, not from the project context)"


def _norm_phrase(s: str) -> str:
    return re.sub(r"[\s*_]+", " ", s.lower()).strip()


def _figure_hits(text: str, haystack: str, context: str = ""):
    """(end_offset, match) for each invented-looking figure with a unit that is
    neither quoted verbatim in ``haystack`` (the whole prompt: context +
    knowledge, e.g. "3-5 regression cycles") nor has its bare number in the
    project ``context``, and whose line carries no flag word. A number that
    merely occurs somewhere in the knowledge base does not exempt an unrelated
    figure. Number-less claims ("cost millions") are always hits."""
    hay = _norm_phrase(haystack)
    for line_start, line in _lines_with_offsets(text):
        if line.lstrip().startswith("#") or _FLAG_WORDS.search(line):
            continue
        if "[source " in line.lower():
            # Attributed to a retrieved source; the citation guard validates the
            # marker itself, so don't also call the figure invented.
            continue
        for m in _FIGURE.finditer(line):
            num = next((m.group(g) for g in _FIGURE_GROUPS if m.group(g)), None)
            if num and num.lower() not in ("millions", "thousands"):
                if _norm_phrase(m.group(0)).lstrip("~") in hay:
                    continue
                bare = num.rstrip(".,")
                if re.search(rf"(?<![\d.]){re.escape(bare)}(?![\d.])", context):
                    continue
            yield line_start + m.end(), m


def _lines_with_offsets(text: str):
    pos = 0
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            yield pos, line
        pos += len(line) + 1


def _threshold_hits(text: str, context_text: str):
    """(end_offset, match) for each bare threshold whose number is absent from the
    project context and whose line carries no suggested/proposed flag."""
    for line_start, line in _lines_with_offsets(text):
        if line.lstrip().startswith("#") or _FLAG_WORDS.search(line):
            continue
        for m in _THRESHOLD.finditer(line):
            num = next(g for g in m.group("n1", "n2", "n3", "n4", "n5") if g)
            if re.search(rf"(?<![\d.]){re.escape(num)}(?![\d.])", context_text):
                continue
            yield line_start + m.end(), m


def flag_invented_thresholds(text: str, source_text: Optional[str]) -> str:
    """Latency/percentage thresholds ("under 2 s (p95)", ">= 90% coverage") whose
    number is not in the PROJECT CONTEXT get an explicit "(suggested target)"
    marker, and unit-bearing figures (throughput, money, SLA hours, effort
    uplifts, cycles, SoC limits) absent from the whole prompt get an
    "(illustrative, ...)" marker, unless the line already says
    suggested/proposed/illustrative. Only runs when the prompt carries a
    PROJECT CONTEXT block. Idempotent (the markers are flag words)."""
    context = project_context_of(source_text)
    if not context:
        return text
    inserts = {e: FIGURE_FLAG for e, _ in _figure_hits(text, (source_text or "").lower(), context)}
    inserts.update({e: THRESHOLD_FLAG for e, _ in _threshold_hits(text, context)})
    for end in sorted(inserts, reverse=True):
        text = text[:end] + inserts[end] + text[end:]
    return text

_VENDOR_TOOLS = re.compile(
    r"\b(BrowserStack|Sauce Labs|LambdaTest|Applitools|AppSee|Termly|OneTrust|TestRail|"
    r"Zephyr|Qase|Percy|Snyk|SonarQube|Burp Suite|Datadog|New Relic|Sentry|LoadRunner|Tricentis)\b"
)
TOOL_FLAG = " (suggested tool, not in the project's stated stack)"


def _tool_hits(text: str, haystack: str):
    """(end_offset, name) for the first mention of each vendor tool whose name is
    absent from ``haystack`` (project context) and that is not already marked
    anywhere in ``text``. One marker per tool per document keeps the output
    readable; a tool on a line that already says suggested/e.g. counts as handled."""
    haystack = haystack.lower()
    seen = {m.group(1).lower() for m in re.finditer(rf"{_VENDOR_TOOLS.pattern}\)?\s*\(suggested tool", text)}
    for line_start, line in _lines_with_offsets(text):
        if line.lstrip().startswith("#"):
            continue
        for m in _VENDOR_TOOLS.finditer(line):
            name = m.group(1).lower()
            if name in seen or name in haystack:
                continue
            seen.add(name)
            if _FLAG_WORDS.search(line):
                continue
            yield line_start + m.end(), m.group(1)


def flag_unlisted_tools(text: str, source_text: Optional[str]) -> str:
    """Third-party products the model introduced out of thin air (BrowserStack,
    Termly...) get a "(suggested tool ...)" marker unless the PROJECT CONTEXT
    already mentions them. Idempotent."""
    context = project_context_of(source_text)
    if not context:
        return text
    for end in sorted({e for e, _ in _tool_hits(text, context)}, reverse=True):
        text = text[:end] + TOOL_FLAG + text[end:]
    return text


# Conservative allowlist: regulator/statute/penalty/retention tokens the model
# tends to recall from memory (sometimes wrongly). The knowledge base has no
# energy-market content, so none of these can be verified unless the prompt
# itself carries them. Acronyms are case-sensitive to avoid common words.
_REG_ACRONYM = re.compile(
    r"(?<![\w-])(?:ACPR|ENTSO-E|RTE|CRE|ACER|REMIT|TTF|NAP|MiFID(?:\s+II)?)(?![\w-])"
)
_REG_PENALTY = re.compile(
    r"\bup to \d+(?:\.\d+)?\s*%\s+of\s+(?:[\w-]+\s+){0,3}?(?:revenue|turnover)\b", re.IGNORECASE
)
_REG_RETENTION = re.compile(r"(?<![\w.])\d{1,2}\+\s+years\b", re.IGNORECASE)
REGULATORY_FLAG = " (unverified, confirm with a domain expert)"
_REG_FLAG_MARK = "unverified, confirm with a domain expert"


def _regulatory_hits(sentence: str, haystack: str):
    """End offsets of regulatory tokens in ``sentence`` absent from ``haystack``."""
    for pattern in (_REG_ACRONYM, _REG_PENALTY, _REG_RETENTION):
        for m in pattern.finditer(sentence):
            token = m.group(0)
            if pattern is _REG_PENALTY:
                token = re.search(r"\d+(?:\.\d+)?\s*%", token).group(0).replace(" ", "")  # type: ignore[union-attr]
            elif pattern is _REG_RETENTION:
                token = re.sub(r"\s+", " ", token.lower())
            if re.search(rf"(?<![\w-]){re.escape(token.lower())}(?![\w-])", haystack):
                continue
            yield m.end()


def _sentences(line: str):
    return re.split(r"(?<=[.!?])(\s+)", line)


def _flag_sentence(sentence: str, haystack: str) -> str:
    if _REG_FLAG_MARK in sentence:
        return sentence
    ends = sorted(_regulatory_hits(sentence, haystack))
    if not ends:
        return sentence
    pos = ends[0]
    while pos < len(sentence) and sentence[pos] in "*_":
        pos += 1  # keep closing emphasis markers attached to the token
    return sentence[:pos] + REGULATORY_FLAG + sentence[pos:]


def flag_unverified_regulatory_claims(text: str, source_text: Optional[str]) -> str:
    """Name-dropped regulators, market codes, fine percentages and retention
    periods ("ACPR", "ENTSO-E", "7+ years") that are absent from the prompt were
    recalled from memory and are sometimes wrong, so append one "(unverified,
    confirm with a domain expert)" marker per sentence. Headings and fenced code
    are skipped; without a source nothing is judged. Idempotent."""
    if not source_text:
        return text
    haystack = source_text.lower()
    out = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and not line.lstrip().startswith("#"):
            line = "".join(_flag_sentence(s, haystack) for s in _sentences(line))
        out.append(line)
    return "\n".join(out)


def _unflagged_regulatory_tokens(text: str, haystack: str) -> list:
    found = []
    for _start, line in _lines_with_offsets(text):
        if line.lstrip().startswith("#"):
            continue
        for s in _sentences(line):
            if _REG_FLAG_MARK not in s and any(True for _ in _regulatory_hits(s, haystack)):
                found.append(s.strip()[:60])
    return found


def sanitize_llm_markdown(text: str, source_text: Optional[str] = None) -> str:
    """Apply every deterministic guard. ``source_text`` is the prompt (or its
    knowledge block) the answer was generated from."""
    text = fix_stray_emphasis(text)
    text = soften_standards_claims(text)
    text = qualify_absence_claims(text, project_context_of(source_text))
    text = qualify_assumed_people_traits(text, project_context_of(source_text))
    text = strip_unverifiable_section_refs(text, source_text)
    text = drop_invalid_source_citations(text, source_text)
    text = unquote_unverified_quotes(text, source_text)
    text = strip_unverified_syllabus_versions(text, source_text)
    text = flag_invented_thresholds(text, source_text)
    text = flag_unlisted_tools(text, source_text)
    text = flag_unverified_regulatory_claims(text, source_text)
    text = soften_absolute_tone(text)
    text = clean_separator_debris(text)
    return replace_dashes(text)
