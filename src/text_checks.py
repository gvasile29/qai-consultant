"""
QAI Consultant - shared dependency-free text checks for the deterministic
cores (review_core, maturity_core).

Stdlib only (re) so it ships in the MCP wheel and stays in the keyless
import graph. Two helpers:

  * detect_language(): stopword-ratio heuristic, English vs Romanian vs
    other. The review/maturity rubrics are English-keyword based, so a
    non-English input would otherwise be scored as "empty" with no hint why.
  * qa_term_hits(): distinct QA-domain terms present, used by review_core's
    "is this a QA document at all?" gate.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Unambiguous English function words (words that are also common Romanian
# words, e.g. "a", "in", "o", are deliberately excluded).
_EN_STOPWORDS = frozenset((
    "the", "and", "of", "to", "is", "are", "for", "with", "that", "this",
    "we", "our", "be", "as", "on", "by", "it", "from", "or", "will", "have",
    "has", "not", "all", "each", "an", "was", "were", "when", "which", "can",
    "should", "must", "if", "at", "their", "these", "those", "than", "then",
    "also", "into", "any", "per", "so", "do", "does", "i", "you", "your",
))

# Romanian function words, unambiguous against English.
_RO_STOPWORDS = frozenset((
    "si", "și", "de", "la", "cu", "pentru", "sa", "să", "care", "este",
    "sunt", "în", "un", "o", "din", "pe", "nu", "se", "ce", "al", "ale",
    "sau", "mai", "dar", "fie", "prin", "dupa", "după", "toate", "fiecare",
    "au", "am", "avem", "pot", "trebuie", "acest", "aceasta", "această",
    "echipa", "echipă", "testare", "testele", "planul", "rolul", "ca", "că",
))

# Function words of other common European languages (no overlap with English
# function words): DE / FR / ES / IT / PT / NL.
_OTHER_STOPWORDS = frozenset((
    "der", "das", "und", "ist", "nicht", "mit", "für", "fur", "von", "zu", "den",
    "dem", "ein", "eine", "auf", "wird", "werden",
    "le", "les", "des", "et", "est", "pour", "dans", "que", "qui", "une", "du",
    "au", "aux", "sur", "pas",
    "el", "los", "las", "y", "es", "por", "con", "para", "una", "del", "se",
    "il", "di", "che", "per", "della", "sono", "gli", "nel",
    "os", "em", "uma", "dos", "das", "não", "nao",
    "het", "een", "van", "en", "zijn", "voor", "niet", "met",
))

MIN_TOKENS_FOR_LANGUAGE = 30

LANGUAGE_WARNING = (
    "Input does not appear to be English ({detected}). The rubric is based "
    "on English keywords and section names, so the scores below are NOT "
    "reliable for this input - absence of evidence here mostly reflects "
    "the language, not the document. Translate the text to English and "
    "re-run for a meaningful result."
)


def is_sentence_like(segment: str, min_words: int = 6) -> bool:
    """True for prose-like text: enough words and a plausible share of
    English function words. A bare comma-separated keyword list fails this."""
    tokens = [w.lower() for w in _WORD_RE.findall(segment or "")]
    if len(tokens) < min_words:
        return False
    return sum(1 for t in tokens if t in _EN_STOPWORDS) / len(tokens) >= 0.10


def detect_language(text: str) -> dict:
    """Heuristic language detection by stopword ratio.

    Returns {"language": "en"|"ro"|"other"|"unknown", "english_ratio": float,
    "romanian_ratio": float, "token_count": int, "reliable": bool,
    "warning": str}. `reliable` is False (and `warning` non-empty) only when
    the text is confidently non-English. Short / terse inputs return
    "unknown" with reliable=True: no warning is better than a false one.
    """
    tokens = [w.lower() for w in _WORD_RE.findall(text or "")]
    n = len(tokens)
    if n < MIN_TOKENS_FOR_LANGUAGE:
        return {"language": "unknown", "english_ratio": 0.0, "romanian_ratio": 0.0,
                "token_count": n, "reliable": True, "warning": ""}
    en = sum(1 for t in tokens if t in _EN_STOPWORDS) / n
    ro = sum(1 for t in tokens if t in _RO_STOPWORDS) / n
    # Romanian diacritics are a strong extra signal.
    diacritics = len(re.findall(r"[ăâîșşțţ]", (text or "").lower()))
    diacritic_rate = diacritics / max(1, len(text))

    other = sum(1 for t in tokens if t in _OTHER_STOPWORDS) / n
    language = "en"
    if ro >= 0.10 and ro > 2 * en:
        language = "ro"
    elif other >= 0.10 and other > 2 * en:
        language = "other"
    elif en < 0.04 and diacritic_rate > 0.005:
        language = "other"

    if language == "en":
        return {"language": "en", "english_ratio": round(en, 3), "romanian_ratio": round(ro, 3),
                "token_count": n, "reliable": True, "warning": ""}
    name = "Romanian" if language == "ro" else "unrecognized language"
    return {"language": language, "english_ratio": round(en, 3), "romanian_ratio": round(ro, 3),
            "token_count": n, "reliable": False,
            "warning": LANGUAGE_WARNING.format(detected=name)}


# Distinct QA-domain terms (regex, word-start anchored). A document that
# matches fewer than MIN_QA_TERMS distinct ones, or none of the core ones,
# is not a QA document (recipes, user stories, meeting notes, ...).
_QA_TERMS = {
    "test": r"\btest(?:s|ed|ing|er|ers)?\b",
    "test_case": r"\btest[- ]cases?\b|\btc[-_ ]?\d+\b",
    "qa": r"\bqa\b|\bquality assurance\b",
    "defect": r"\bdefects?\b|\bbugs?\b",
    "requirement": r"\brequirements?\b|\breq[-_]?\d+\b",
    "risk": r"\brisks?\b",
    "scope": r"\bscope\b",
    "coverage": r"\bcoverage\b",
    "acceptance": r"\bacceptance\b",
    "regression": r"\bregression\b",
    "expected_result": r"\bexpected (?:result|outcome|behaviou?r)s?\b",
    "precondition": r"\bpreconditions?\b|\bprerequisites?\b",
    "severity": r"\bseverity\b|\bpriority\b",
    "verification": r"\bverif(?:y|ication)\b|\bvalidat(?:e|ion)\b",
    "automation": r"\bautomat(?:ed|ion)\b",
    "environment": r"\b(?:test|staging|qa) environments?\b",
    "criteria": r"\b(?:entry|exit|pass/fail|pass|fail) criteria\b",
    "traceability": r"\btraceab(?:le|ility)\b",
    "assertion": r"\bassert(?:ion|ions)?\b",
}
_QA_COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in _QA_TERMS.items()}
_QA_CORE = ("test", "test_case", "qa", "defect")

MIN_QA_TERMS = 2


def qa_term_hits(text: str) -> list:
    """Sorted list of distinct QA-domain term keys present in `text`."""
    return sorted(k for k, rx in _QA_COMPILED.items() if rx.search(text or ""))


def looks_like_qa_document(text: str, min_terms: int = MIN_QA_TERMS) -> tuple:
    """(is_qa, hits). Requires >= `min_terms` distinct terms AND at least
    one core term (test / test case / QA / defect). Callers that were told
    the document type explicitly pass min_terms=1 (core term only)."""
    hits = qa_term_hits(text)
    ok = len(hits) >= min_terms and any(c in hits for c in _QA_CORE)
    return ok, hits
