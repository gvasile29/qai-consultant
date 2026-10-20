"""
QAI Consultant — Adoption metrics (shared by the Streamlit landing page and
scripts/usage_report.py).

Sources:
  - Streamlit app counters in Pinecone's "app-metrics" namespace
    (visit_counter.py): visits, download_<doc>_<md|pdf>, feedback_<value>,
    plus usage_guard.py's daily usage_global_<date> run counters.
  - PyPI downloads of qai-consultant-mcp via pypistats.org (keyless).
    Installs from the official MCP registry and Glama both resolve to
    `uvx qai-consultant-mcp` / pip, so PyPI downloads already include them;
    neither listing publishes its own install counts (registry: none at
    all; Glama: API-key-only, with an attribution licence).
  - GitHub stars (public API, unauthenticated, 60 req/h per IP — callers
    must cache; app.py caches for an hour).
  - Official MCP registry: number of published versions + latest version.

collect_adoption() (the landing page's source) never raises: it runs the
app/PyPI/GitHub fetches in parallel with a short timeout, and each section
is None when its source fails or is slow — callers hide whatever is
missing. The registry is left out of it on purpose: it carries no adoption
numbers and its API has been seen taking ~9s to answer. The fetch_*
functions raise, for the report script's error output.

Used only from app.py and scripts/ — never imported by the MCP server path.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
import urllib.parse
import urllib.request

from qai_consultant.common.logger import get_logger

logger = get_logger(__name__)

PYPI_PACKAGE = "qai-consultant-mcp"
GITHUB_REPO = "gvasile29/qai-consultant"
REGISTRY_SERVER_NAME = "io.github.gvasile29/qai-consultant-mcp"

_PYPISTATS = "https://pypistats.org/api/packages/" + PYPI_PACKAGE
_GITHUB_API = "https://api.github.com/repos/" + GITHUB_REPO
_REGISTRY_API = "https://registry.modelcontextprotocol.io/v0/servers"
_TIMEOUT_SECONDS = 10
COLLECT_TIMEOUT_SECONDS = 6


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "qai-consultant-adoption-metrics"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # nosec B310 - fixed https URLs only
        return json.loads(resp.read().decode("utf-8"))


def _list_ids(index, prefix: str, namespace: str) -> list:
    """index.list() yields plain id lists on some Pinecone SDK versions and
    ListResponse pages of ListItem(id=...) on others; accept both."""
    ids: list = []
    for page in index.list(prefix=prefix, namespace=namespace):
        items = getattr(page, "vectors", page)
        ids.extend(getattr(item, "id", item) for item in items)
    return ids


def fetch_app_metrics(index=None) -> dict:
    from qai_consultant.observability.visit_counter import (
        DOWNLOAD_DOCS,
        DOWNLOAD_FORMATS,
        FEEDBACK_VALUES,
        NAMESPACE,
        VECTOR_ID,
        _open_index,
        all_event_counter_ids,
        download_counter_id,
        feedback_counter_id,
        read_counters,
    )

    index = index or _open_index()
    run_ids = _list_ids(index, "usage_global_", NAMESPACE)
    counts = read_counters([VECTOR_ID] + all_event_counter_ids() + run_ids, index=index)

    downloads = {
        doc: {fmt: counts[download_counter_id(doc, fmt)] for fmt in DOWNLOAD_FORMATS}
        for doc in DOWNLOAD_DOCS
    }
    feedback = {v: counts[feedback_counter_id(v)] for v in FEEDBACK_VALUES}
    feedback_total = sum(feedback.values())
    run_days = sorted(r[len("usage_global_"):] for r in run_ids)
    return {
        "visits": counts[VECTOR_ID],
        "generation_runs": sum(counts[r] for r in run_ids),
        "generation_runs_since": run_days[0] if run_days else None,
        "generation_run_days": len(run_ids),
        "downloads": downloads,
        "downloads_total": {
            fmt: sum(downloads[d][fmt] for d in DOWNLOAD_DOCS) for fmt in DOWNLOAD_FORMATS
        },
        "feedback": feedback,
        "feedback_total": feedback_total,
        "feedback_useful_pct": (
            round(100 * (feedback["yes"] + feedback["partially"]) / feedback_total, 1)
            if feedback_total else None
        ),
    }


def fetch_pypi_metrics() -> dict:
    recent = _get_json(_PYPISTATS + "/recent")["data"]
    overall = _get_json(_PYPISTATS + "/overall?mirrors=false")["data"]
    daily = [row for row in overall if row.get("category") == "without_mirrors"]
    return {
        "package": PYPI_PACKAGE,
        "downloads_total": sum(row["downloads"] for row in daily),
        "since": min((row["date"] for row in daily), default=None),
        "last_month": recent.get("last_month"),
        "last_week": recent.get("last_week"),
        "last_day": recent.get("last_day"),
    }


def fetch_github_metrics() -> dict:
    repo = _get_json(_GITHUB_API)
    return {"repo": GITHUB_REPO, "stars": repo.get("stargazers_count"), "forks": repo.get("forks_count")}


def fetch_registry_metrics() -> dict:
    query = urllib.parse.urlencode({"search": REGISTRY_SERVER_NAME.split("/")[-1]})
    data = _get_json(f"{_REGISTRY_API}?{query}")
    entries = [e for e in data.get("servers", []) if e.get("server", {}).get("name") == REGISTRY_SERVER_NAME]
    latest = next(
        (e["server"]["version"] for e in entries
         if e.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {}).get("isLatest")),
        None,
    )
    return {"name": REGISTRY_SERVER_NAME, "versions_published": len(entries), "latest_version": latest}


def collect_adoption(timeout: float = COLLECT_TIMEOUT_SECONDS) -> dict:
    """App counters, PyPI and GitHub in parallel; each None on failure or
    when it hasn't answered within `timeout` seconds. Never raises."""
    sources = {"app": fetch_app_metrics, "pypi": fetch_pypi_metrics, "github": fetch_github_metrics}
    result: dict = {name: None for name in sources}
    deadline = time.monotonic() + timeout
    pool = ThreadPoolExecutor(max_workers=len(sources))
    try:
        futures = {name: pool.submit(fn) for name, fn in sources.items()}
        for name, future in futures.items():
            try:
                result[name] = future.result(timeout=max(0.0, deadline - time.monotonic()))
            except FutureTimeout:
                logger.warning("Adoption metrics source %s timed out", name)
            except Exception as exc:
                logger.warning("Adoption metrics source %s failed: %s", name, exc)
    finally:
        pool.shutdown(wait=False)  # a slow source must not hold up the page
    return result
