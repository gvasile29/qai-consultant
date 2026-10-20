"""
QAI Consultant -- Knowledge Sources panel labels.

Dependency-free helpers that turn the chunks handed to a generator prompt into
the labels shown in the "Knowledge Sources Used" panel.

Two invariants the panel previously broke:

* Numbering: ``agent.format_knowledge_context()`` numbers every chunk
  ``[Source 1]``..``[Source N]`` in order, and the LLM cites those numbers. The
  panel used to de-duplicate by filename into an unordered set, so a document
  retrieved as several chunks collapsed to one line and the numbers the text
  cited (e.g. ``[Source 5]``) had no matching entry. ``build_source_labels``
  keeps the N mapping: ``[Source 2, 4] ...``.
* Names: some KB files carry download-time random suffixes
  (``ISTQB_CTAL-TM_Syllabus_v3.0_zKjKsaN.pdf``) that read like internal
  storage names. ``display_name`` shows a clean, human-readable title.
"""
import re

_KNOWN_EXTENSIONS = (".pdf", ".md", ".markdown", ".txt", ".html", ".htm", ".docx", ".doc", ".rst")
# tmpab12cd_name / tmp_ab12cd_name -- temp-file prefixes from uploads.
_TMP_PREFIX = re.compile(r"^(?:tmp|temp)[_\-]?[A-Za-z0-9]{6,10}[_\-]", re.IGNORECASE)
# Trailing browser/OS duplicate marker: " (1)".
_COPY_MARKER = re.compile(r"\s*\(\d+\)\s*$")
# Trailing random 7-char token (download-time suffix): needs a lowercase letter
# and an uppercase letter or digit after the first character, so ordinary
# words like "_Process" or "_studies" are never stripped.
_RANDOM_SUFFIX = re.compile(r"[_\-]([A-Za-z0-9]{7})$")


def _looks_random(token: str) -> bool:
    has_lower = any(c.islower() for c in token)
    has_inner_upper = any(c.isupper() for c in token[1:])
    has_digit = any(c.isdigit() for c in token)
    return has_lower and (has_inner_upper or has_digit)


def display_name(filename: str) -> str:
    """Clean, human-readable title for a KB source filename."""
    name = (filename or "").strip()
    if not name:
        return "Unknown"
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = _COPY_MARKER.sub("", name)
    lowered = name.lower()
    for ext in _KNOWN_EXTENSIONS:
        if lowered.endswith(ext):
            name = name[: -len(ext)]
            break
    name = _COPY_MARKER.sub("", name)
    name = _TMP_PREFIX.sub("", name)
    match = _RANDOM_SUFFIX.search(name)
    if match and _looks_random(match.group(1)):
        name = name[: match.start()]
    name = re.sub(r"\s+", " ", name.replace("_", " ")).strip()
    return name or "Unknown"


def build_source_labels(chunks) -> list:
    """One label per distinct document, keeping the prompt's ``[Source N]`` numbers.

    ``chunks`` must be exactly the list passed to
    ``agent.format_knowledge_context()`` (that function numbers them
    ``enumerate(chunks, 1)``). Returns e.g.
    ``["[Source 1, 3] [Standard] ISTQB CTAL TM Syllabus v3.0", "[Source 2] [Methodology] Risk Based Testing"]``,
    ordered by each document's first source number.
    """
    groups: dict = {}
    for n, chunk in enumerate(chunks or [], 1):
        meta = getattr(chunk, "metadata", None) or {}
        key = (meta.get("category") or "N/A", meta.get("filename") or "N/A")
        groups.setdefault(key, []).append(n)
    labels = []
    for (category, filename), numbers in groups.items():
        nums = ", ".join(str(n) for n in numbers)
        labels.append(f"[Source {nums}] [{category}] {display_name(filename)}")
    return labels
