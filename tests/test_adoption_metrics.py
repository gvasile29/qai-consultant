"""Tests for src/adoption_metrics.py, the landing-page adoption tiles in
components.py, and scripts/usage_report.py — no network, no Pinecone."""

import importlib.util
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import adoption_metrics  # noqa: E402
from components import ADOPTION_MIN_RATINGS, adoption_tiles, build_adoption_strip_html  # noqa: E402
from theme import LIGHT_TOKENS  # noqa: E402


# ── adoption_metrics ────────────────────────────────────────────────────────────

def test_list_ids_accepts_plain_id_lists():
    index = MagicMock()
    index.list.return_value = iter([["a", "b"], ["c"]])
    assert adoption_metrics._list_ids(index, "usage_global_", "app-metrics") == ["a", "b", "c"]


def test_list_ids_accepts_list_response_pages():
    page = SimpleNamespace(vectors=[SimpleNamespace(id="usage_global_2026-10-01")])
    index = MagicMock()
    index.list.return_value = iter([page])
    assert adoption_metrics._list_ids(index, "usage_global_", "app-metrics") == ["usage_global_2026-10-01"]


def test_fetch_app_metrics_aggregates_counters():
    def vec(n):
        return SimpleNamespace(metadata={"count": n})

    stored = {
        "visit_counter": vec(50),
        "usage_global_2026-09-23": vec(4), "usage_global_2026-10-01": vec(6),
        "download_test_plan_pdf": vec(3), "download_risk_register_md": vec(2),
        "feedback_yes": vec(3), "feedback_partially": vec(1), "feedback_no": vec(1),
    }
    index = MagicMock()
    index.list.return_value = iter([["usage_global_2026-10-01", "usage_global_2026-09-23"]])
    index.fetch.side_effect = lambda ids, namespace: SimpleNamespace(
        vectors={i: stored[i] for i in ids if i in stored})

    app = adoption_metrics.fetch_app_metrics(index=index)
    assert app["visits"] == 50
    assert app["generation_runs"] == 10
    assert app["generation_runs_since"] == "2026-09-23"
    assert app["downloads_total"] == {"md": 2, "pdf": 3}
    assert app["downloads"]["test_plan"] == {"md": 0, "pdf": 3}
    assert app["feedback_total"] == 5
    assert app["feedback_useful_pct"] == 80.0


def test_fetch_pypi_metrics_sums_without_mirrors_only():
    responses = {
        "/recent": {"data": {"last_day": 1, "last_week": 5, "last_month": 20}},
        "/overall?mirrors=false": {"data": [
            {"category": "without_mirrors", "date": "2026-07-15", "downloads": 10},
            {"category": "without_mirrors", "date": "2026-07-16", "downloads": 3},
            {"category": "with_mirrors", "date": "2026-07-16", "downloads": 99},
        ]},
    }
    with patch.object(adoption_metrics, "_get_json",
                      side_effect=lambda url: responses[url[len(adoption_metrics._PYPISTATS):]]):
        stats = adoption_metrics.fetch_pypi_metrics()
    assert stats["downloads_total"] == 13
    assert stats["since"] == "2026-07-15"
    assert stats["last_week"] == 5


def test_fetch_registry_metrics_counts_only_our_server_and_finds_latest():
    meta = "io.modelcontextprotocol.registry/official"
    name = adoption_metrics.REGISTRY_SERVER_NAME
    data = {"servers": [
        {"server": {"name": name, "version": "3.6.2"}, "_meta": {meta: {"isLatest": False}}},
        {"server": {"name": name, "version": "3.6.3"}, "_meta": {meta: {"isLatest": True}}},
        {"server": {"name": "io.github.someone/else", "version": "9.9"}, "_meta": {meta: {"isLatest": True}}},
    ]}
    with patch.object(adoption_metrics, "_get_json", return_value=data):
        reg = adoption_metrics.fetch_registry_metrics()
    assert reg == {"name": name, "versions_published": 2, "latest_version": "3.6.3"}


def test_collect_adoption_isolates_failures():
    with patch.object(adoption_metrics, "fetch_app_metrics", side_effect=RuntimeError("pinecone down")), \
            patch.object(adoption_metrics, "fetch_pypi_metrics", return_value={"downloads_total": 1}), \
            patch.object(adoption_metrics, "fetch_github_metrics", side_effect=OSError("rate limited")):
        snap = adoption_metrics.collect_adoption()
    assert snap == {"app": None, "pypi": {"downloads_total": 1}, "github": None}


def test_collect_adoption_does_not_wait_on_a_slow_source():
    release = threading.Event()
    with patch.object(adoption_metrics, "fetch_app_metrics", side_effect=lambda: release.wait(10)), \
            patch.object(adoption_metrics, "fetch_pypi_metrics", return_value={"downloads_total": 1}), \
            patch.object(adoption_metrics, "fetch_github_metrics", return_value={"stars": 2}):
        start = time.monotonic()
        snap = adoption_metrics.collect_adoption(timeout=0.3)
        elapsed = time.monotonic() - start
    release.set()
    assert elapsed < 2
    assert snap["app"] is None and snap["pypi"] == {"downloads_total": 1}


# ── components: adoption tiles ──────────────────────────────────────────────────

def _snapshot(**app_overrides):
    app = {
        "visits": 559, "generation_runs": 13, "generation_runs_since": "2026-09-23",
        "downloads_total": {"md": 0, "pdf": 0}, "feedback_total": 0, "feedback_useful_pct": None,
    }
    app.update(app_overrides)
    return {"app": app, "pypi": {"downloads_total": 2257, "since": "2026-07-15"}, "github": {"stars": 7}}


def _labels(snapshot):
    return [label for label, _value, _sub in adoption_tiles(snapshot)]


def test_tiles_hide_zero_downloads_and_too_few_ratings():
    snap = _snapshot(feedback_total=ADOPTION_MIN_RATINGS - 1, feedback_useful_pct=100.0)
    assert _labels(snap) == ["App visits", "AI runs", "MCP installs", "GitHub stars"]


def test_tiles_show_downloads_and_useful_pct_once_meaningful():
    snap = _snapshot(downloads_total={"md": 4, "pdf": 6}, feedback_total=ADOPTION_MIN_RATINGS,
                     feedback_useful_pct=80.0)
    tiles = {label: (value, sub) for label, value, sub in adoption_tiles(snap)}
    assert tiles["Downloads"][0] == "10"
    assert tiles["Found it useful"] == ("80%", f"of {ADOPTION_MIN_RATINGS} ratings")
    assert tiles["App visits"][0] == "559"
    assert tiles["MCP installs"] == ("2,257", "PyPI downloads since Jul 2026")
    assert tiles["AI runs"][1] == "since Sep 2026"


def test_tiles_skip_failed_sources():
    assert _labels({"app": None, "pypi": {"downloads_total": 5, "since": None}, "github": None}) == ["MCP installs"]


def test_strip_is_empty_when_every_source_failed():
    assert build_adoption_strip_html(LIGHT_TOKENS, {"app": None, "pypi": None, "github": None}) == ""
    assert build_adoption_strip_html(LIGHT_TOKENS, {}) == ""


def test_strip_renders_tiles_and_credits_listings():
    html = build_adoption_strip_html(LIGHT_TOKENS, _snapshot())
    assert "2,257" in html and "559" in html
    assert "glama.ai/mcp/servers/gvasile29/qai-consultant" in html
    assert "registry.modelcontextprotocol.io" in html


# ── scripts/usage_report.py ─────────────────────────────────────────────────────

def test_usage_report_imports_the_shared_fetchers():
    spec = importlib.util.spec_from_file_location("usage_report", REPO_ROOT / "scripts" / "usage_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.fetch_pypi_metrics is adoption_metrics.fetch_pypi_metrics
    assert {name for name, *_ in module.SECTIONS} == {"app", "pypi", "github", "registry"}
