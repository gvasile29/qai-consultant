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

# Function-word profiles per language. Words that are also common English
# words ("a", "in", "on", "an", "die", "was", "so", "me", "come") are
# deliberately excluded so English text never scores for another language.
# Words shared between related languages (de, que, se, la ...) are fine: the
# language whose profile covers the most tokens wins, and a near-tie is
# reported as an unrecognized language rather than guessed.
_LANG_STOPWORDS = {
    "ro": frozenset((
        "si", "și", "de", "la", "cu", "pentru", "sa", "să", "care", "este",
        "sunt", "în", "un", "o", "din", "pe", "nu", "se", "ce", "al", "ale",
        "sau", "mai", "dar", "fie", "prin", "dupa", "după", "toate", "fiecare",
        "au", "avem", "pot", "trebuie", "acest", "aceasta", "această",
        "echipa", "echipă", "testare", "testele", "planul", "rolul", "ca", "că",
        "va", "vor", "cel", "cea", "sale", "lui", "acestui", "ale", "unei",
    )),
    "fr": frozenset((
        "le", "la", "les", "des", "et", "est", "pour", "dans", "que", "qui",
        "une", "un", "du", "au", "aux", "sur", "pas", "avec", "sont", "nous",
        "vous", "ce", "cette", "ces", "être", "ou", "par", "en", "il", "elle",
        "ne", "se", "tous", "toutes", "chaque", "doit", "doivent", "plus",
        "mais", "ont", "sera", "seront", "leur", "leurs", "ainsi", "afin",
        "entre", "sans", "aussi", "où", "d'un", "l'application", "qu'il",
    )),
    "de": frozenset((
        "der", "die", "das", "und", "ist", "nicht", "mit", "für", "fur", "von",
        "zu", "den", "dem", "ein", "eine", "auf", "wird", "werden", "im", "es",
        "sich", "auch", "bei", "nach", "aus", "oder", "als", "wie", "wir",
        "sind", "alle", "jede", "muss", "müssen", "dass", "zur", "zum", "einer",
        "eines", "über", "unter", "durch", "des", "einen", "kann", "können",
    )),
    "es": frozenset((
        "el", "los", "las", "y", "es", "por", "con", "para", "una", "del", "se",
        "que", "su", "al", "más", "pero", "como", "esta", "este", "están",
        "debe", "deben", "todos", "todas", "cada", "sus", "lo", "ser", "son",
        "entre", "sin", "también", "sobre", "hasta", "desde", "donde",
        "de", "la", "un", "los", "será", "serán",
    )),
    "it": frozenset((
        "il", "di", "che", "per", "della", "sono", "gli", "nel", "le", "la",
        "un", "una", "con", "non", "è", "dei", "delle", "del", "anche", "questo",
        "questa", "come", "tutti", "tutte", "sul", "alla", "ogni", "deve",
        "devono", "essere", "più", "ma", "nella", "dello", "degli", "sarà",
        "saranno", "gli", "lo", "si", "da", "dal", "dalla", "fra", "tra",
    )),
    "pt": frozenset((
        "os", "em", "uma", "dos", "das", "não", "nao", "para", "com", "que",
        "de", "do", "da", "na", "nos", "nas", "são", "mais", "como",
        "por", "ou", "ser", "está", "deve", "devem", "todos", "todas", "seu",
        "sua", "ao", "aos", "pelo", "pela", "um", "se", "é", "também", "entre",
        "sem", "sobre", "cada", "será", "serão", "isso", "este", "esta",
    )),
    "nl": frozenset((
        "het", "een", "van", "en", "zijn", "voor", "niet", "met", "de", "op",
        "te", "dat", "ook", "wordt", "worden", "aan", "bij", "naar", "als",
        "deze", "alle", "moet", "moeten", "om", "uit", "er", "door",
        "geen", "wel", "hun", "dit", "zal", "zullen", "kan", "kunnen",
    )),
}
# Backwards-compatible aliases (older tests/callers import these names).
_RO_STOPWORDS = _LANG_STOPWORDS["ro"]
_OTHER_STOPWORDS = frozenset().union(*(v for k, v in _LANG_STOPWORDS.items() if k != "ro"))

# Characters that point strongly at one language (small additive bonus).
_LANG_DIACRITICS = {
    "ro": "ăâîșşțţ",
    "fr": "çèêëœùûôéàïî",
    "de": "äöüß",
    "es": "ñ¿¡áíóú",
    "it": "òì",
    "pt": "ãõç",
    "nl": "ĳ",
}

LANGUAGE_NAMES = {
    "ro": "Romanian", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch",
}

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

    Returns {"language": "en"|"ro"|"fr"|"de"|"es"|"it"|"pt"|"nl"|"other"|
    "unknown", "english_ratio": float, "romanian_ratio": float,
    "token_count": int, "reliable": bool, "warning": str}. "other" means
    confidently not English but not matched to a single known language (or a
    near-tie between related languages): it is never reported as a wrong named
    language. `reliable` is False (and `warning` non-empty) only when the text
    is confidently non-English. Short / terse inputs return "unknown" with
    reliable=True: no warning is better than a false one.
    """
    tokens = [w.lower() for w in _WORD_RE.findall(text or "")]
    n = len(tokens)
    if n < MIN_TOKENS_FOR_LANGUAGE:
        return {"language": "unknown", "english_ratio": 0.0, "romanian_ratio": 0.0,
                "token_count": n, "reliable": True, "warning": ""}
    lowered = (text or "").lower()
    en = sum(1 for t in tokens if t in _EN_STOPWORDS) / n
    ro = sum(1 for t in tokens if t in _RO_STOPWORDS) / n
    n_chars = max(1, len(lowered))

    scores = {}
    for lang, words in _LANG_STOPWORDS.items():
        ratio = sum(1 for t in tokens if t in words) / n
        diac = sum(lowered.count(c) for c in _LANG_DIACRITICS[lang]) / n_chars
        scores[lang] = ratio + min(0.05, diac * 3)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_lang, best = ranked[0]
    second = ranked[1][1]
    any_diacritic = bool(re.search(r"[ăâîșşțţàèéêëïôûùçäöüßñãõ]", lowered))

    language = "en"
    if best >= 0.10 and best > 2 * en:
        # A clear winner over every other profile; otherwise it is ambiguous.
        language = best_lang if best >= 1.25 * second else "other"
    elif en < 0.04 and any_diacritic:
        language = "other"

    if language == "en":
        return {"language": "en", "english_ratio": round(en, 3), "romanian_ratio": round(ro, 3),
                "token_count": n, "reliable": True, "warning": ""}
    name = LANGUAGE_NAMES.get(language, "unrecognized language")
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


# A QA signal is weaker than a full QA document but strong enough to review a
# short or vague genuine document instead of rejecting it: a test-plan /
# strategy / case wording, a "testing" mention, or "Test N:" case lines.
_QA_SIGNAL_RE = re.compile(
    r"\btest[- ]?(?:plans?|strateg(?:y|ies)|cases?|scenarios?|suites?|scripts?|specifications?)\b"
    r"|\b(?:qa|quality assurance)\b"
    r"|\btesting\b"
    r"|^\s*(?:[#>*|-]+\s*)?(?:test|tc[-_ ]?)\s*\d+\s*[:.)\-]",
    re.IGNORECASE | re.MULTILINE,
)


def has_qa_signal(text: str) -> bool:
    """True when `text` carries an explicit QA-document wording (test plan,
    test strategy, test case(s), testing, QA, "Test N:" lines)."""
    return bool(_QA_SIGNAL_RE.search(text or ""))
