"""
Regression tests for the MCP end-to-end QA round 2 (F8-F21): tolerant results
parsing, skipped-test semantics, flaky-bound validation, retrieval relevance
signalling/dedupe/empty-query, citation filtering, input caps and the
background index build. Keyless: fakes stand in for the embedder; the
real-index checks skip when the embedding model is not available locally.
"""

import asyncio
import json
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from unittest.mock import patch

from mcp.shared.memory import create_connected_server_and_client_session

import mcp_server
import results_core
from local_index import LOW_RELEVANCE_NOTE, LocalIndex

_VOCAB = ["apple", "banana", "cherry", "risk", "testing", "priority", "gdpr", "security"]


class _FakeEmbeddings:
    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    def _vec(self, text):
        t = text.lower()
        vec = [float(t.count(w)) for w in _VOCAB]
        return vec if any(vec) else [0.01] * len(_VOCAB)


def _run(coro):
    return asyncio.run(coro)


async def _call_tool(name, arguments):
    async with create_connected_server_and_client_session(mcp_server.mcp._mcp_server) as client:
        await client.initialize()
        result = await client.call_tool(name, arguments)
        assert not result.isError, result.content
        return json.loads(result.content[0].text)


def _fake_index(tmp_path, files):
    kb = tmp_path / "kb"
    for rel, content in files.items():
        p = kb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()):
        idx = LocalIndex(kb_dir=kb, cache_dir=tmp_path / "cache")
        idx._ensure_built()
    return idx


# ── F8: tolerant CSV / XML parsing ──────────────────────────────────────────────

@pytest.mark.parametrize("csv_text", [
    "Test Name,Status,Duration\nlogin works,PASS,1.5\nlogout,FAIL,2.0\n",
    "name,result,time_ms\nlogin works,ok,1500\nlogout,failure,2000\n",
    "test,outcome\nlogin works,success\nlogout,KO\n",
    "title;state\nlogin works;passed\nlogout;failed\n",
])
def test_f8_csv_header_and_status_aliases_parse(csv_text):
    records, warnings = results_core.parse_results_csv_detailed(csv_text)
    assert [r.name for r in records] == ["login works", "logout"]
    assert [r.status for r in records] == ["passed", "failed"]
    assert not any("missing" in w for w in warnings)


def test_f8_duration_units():
    ms, _ = results_core.parse_results_csv_detailed("name,status,time_ms\na,pass,1500\n")
    assert ms[0].duration_s == 1.5
    s, _ = results_core.parse_results_csv_detailed("name,status,duration\na,pass,1.5\nb,pass,250ms\n")
    assert [r.duration_s for r in s] == [1.5, 0.25]


def test_f8_status_synonyms():
    for raw, expected in [("pass", "passed"), ("OK", "passed"), ("success", "passed"),
                          ("fail", "failed"), ("failure", "failed"), ("KO", "failed"),
                          ("err", "error"), ("skip", "skipped"), ("ignored", "skipped"),
                          ("pending", "skipped")]:
        assert results_core.normalize_status(raw) == expected
    assert results_core.normalize_status("banana") is None


def test_f8_warnings_list_dropped_rows_and_unrecognised_columns():
    csv_text = "name,status,owner\na,pass,bob\nb,weird,bob\n,pass,bob\n"
    records, warnings = results_core.parse_results_csv_detailed(csv_text)
    assert len(records) == 1
    joined = " ".join(warnings)
    assert "owner" in joined
    assert "weird" in joined
    assert "empty test name" in joined


@pytest.mark.parametrize("csv_text", ["", "   \n", "name,status\n", "foo,bar\n1,2\n"])
def test_f8_unparseable_csv_returns_no_tests_found(csv_text):
    result = _run(_call_tool("analyze_test_results", {"csv_text": csv_text}))
    assert result["error"] == "no_tests_found"
    assert result["warnings"]
    assert "overall_pass_rate" not in result


def test_f8_html_error_page_as_xml_is_not_a_successful_empty_result():
    html = "<html><head><title>502 Bad Gateway</title></head><body><h1>502</h1></body></html>"
    result = _run(_call_tool("analyze_test_results", {"junit_xml": html}))
    assert result["error"] == "no_tests_found"
    assert "no <testcase>" in " ".join(result["warnings"])


def test_f8_aliased_csv_through_the_tool_reports_real_numbers():
    result = _run(_call_tool("analyze_test_results", {
        "csv_text": "Test Name,Status,Duration\na,PASS,1\nb,FAIL,2\n",
    }))
    assert "error" not in result
    assert result["total_tests"] == 2
    assert result["overall_pass_rate"] == 0.5


def test_f8_dropped_rows_warning_surfaces_in_tool_result():
    result = _run(_call_tool("analyze_test_results", {
        "csv_text": "name,status\na,pass\nb,bogus\n",
    }))
    assert "error" not in result
    assert any("bogus" in w for w in result["warnings"])


def test_f8_multi_run_with_one_bad_entry_warns_but_succeeds():
    good = '<testsuite><testcase classname="p" name="t"/></testsuite>'
    result = _run(_call_tool("analyze_test_results", {
        "junit_xml": [{"run_id": "r1", "xml": good}, {"run_id": "r2", "xml": "<html/>"}],
    }))
    assert "error" not in result
    assert result["runs"] == 1
    assert any("r2" in w for w in result["warnings"])


# ── F17: skipped tests are not failures ──────────────────────────────────────────

def _rec(status, run):
    return results_core.TestRecord(run_id=run, name="t", classname="c", status=status, duration_s=0.0)


def test_f17_pass_pass_skip_is_not_flaky():
    analysis = results_core.analyze([_rec("passed", "1"), _rec("passed", "2"), _rec("skipped", "3")])
    assert analysis.flaky == []
    assert analysis.ever_failing == []
    assert analysis.skipped == [{"test": "c::t", "skipped": 1, "runs": 3}]
    assert analysis.skipped_executions == 1
    assert analysis.overall_pass_rate == 1.0


def test_f17_always_skipped_is_not_ever_failing_and_pass_rate_is_zero_not_misleading():
    analysis = results_core.analyze([_rec("skipped", str(i)) for i in range(4)])
    assert analysis.ever_failing == []
    assert analysis.skipped_executions == 4


def test_f17_real_flaky_still_detected_with_a_skip_in_the_mix():
    runs = [_rec("passed", "1"), _rec("failed", "2"), _rec("passed", "3"),
            _rec("failed", "4"), _rec("skipped", "5")]
    analysis = results_core.analyze(runs)
    assert [f["test"] for f in analysis.flaky] == ["c::t"]
    assert analysis.flaky[0]["pass_rate"] == 0.5
    assert analysis.flaky[0]["runs"] == 4  # skipped execution excluded


def test_f17_skipped_does_not_satisfy_minimum_executions():
    analysis = results_core.analyze([_rec("passed", "1"), _rec("failed", "2"), _rec("skipped", "3")])
    assert analysis.flaky == []  # only 2 verdict executions


# ── F18: flaky bounds validation ─────────────────────────────────────────────────

_ONE_TEST_XML = '<testsuite><testcase classname="p" name="t"/></testsuite>'


@pytest.mark.parametrize("lo,hi", [(0.9, 0.1), (0.5, 0.5), (-0.1, 0.8), (0.2, 1.5)])
def test_f18_invalid_flaky_bounds_rejected(lo, hi):
    result = _run(_call_tool("analyze_test_results", {
        "junit_xml": _ONE_TEST_XML, "flaky_min": lo, "flaky_max": hi,
    }))
    assert result["error"] == "invalid_argument"
    assert "flaky" in result["message"]


def test_f18_valid_bounds_accepted():
    result = _run(_call_tool("analyze_test_results", {
        "junit_xml": _ONE_TEST_XML, "flaky_min": 0.0, "flaky_max": 1.0,
    }))
    assert "error" not in result


# ── F15 / F9 / F10 / F14: LocalIndex.search ──────────────────────────────────────

def test_f15_empty_query_is_invalid_argument(tmp_path):
    idx = _fake_index(tmp_path, {"methodologies/a.md": "# A\n\nrisk testing priority"})
    for q in ("", "   ", "\n\t"):
        result = idx.search(q)
        assert result["error"] == "invalid_argument"


def test_f15_empty_query_through_the_tool():
    result = _run(_call_tool("retrieve_qa_knowledge", {"query": "  "}))
    assert result["error"] == "invalid_argument"


def test_f9_low_relevance_returns_empty_chunks_note_and_best_score(tmp_path):
    idx = _fake_index(tmp_path, {"methodologies/a.md": "# A\n\nrisk testing priority risk"})
    # "banana" shares no vocabulary with the doc -> cosine 0.
    result = idx.search("banana", min_score=0.4)
    assert result["chunks"] == []
    assert result["low_relevance"] is True
    assert result["note"] == LOW_RELEVANCE_NOTE
    assert "own knowledge" in result["note"] and "PDF" in result["note"]
    assert result["best_score"] is not None and result["best_score"] < 0.4


def test_f9_relevant_query_is_not_flagged(tmp_path):
    idx = _fake_index(tmp_path, {"methodologies/a.md": "# A\n\nrisk testing priority risk"})
    result = idx.search("risk testing", min_score=0.4)
    assert result["chunks"] and result["low_relevance"] is False
    assert "note" not in result
    assert result["best_score"] == result["chunks"][0]["score"]


def test_f9_min_score_zero_disables_filtering(tmp_path):
    idx = _fake_index(tmp_path, {"methodologies/a.md": "# A\n\nrisk testing priority risk"})
    result = idx.search("banana", min_score=0.0)
    assert result["chunks"] and result["low_relevance"] is False


@pytest.mark.parametrize("bad", [-0.1, 1.5, "high", True])
def test_f9_invalid_min_score_rejected(tmp_path, bad):
    idx = _fake_index(tmp_path, {"methodologies/a.md": "# A\n\nrisk"})
    assert idx.search("risk", min_score=bad)["error"] == "invalid_argument"


def test_f9_tool_schema_exposes_min_score_default():
    async def _schema():
        async with create_connected_server_and_client_session(mcp_server.mcp._mcp_server) as client:
            await client.initialize()
            return (await client.list_tools()).tools

    tool = next(t for t in _run(_schema()) if t.name == "retrieve_qa_knowledge")
    prop = tool.inputSchema["properties"]["min_score"]
    assert prop["default"] == mcp_server.DEFAULT_MIN_SCORE == 0.40
    assert "ISTQB" in tool.description  # docstring says what the index does not cover


def test_f14_overlapping_chunks_of_one_source_are_deduped_and_backfilled(tmp_path):
    shared = "risk testing priority " * 30
    kb = {
        "methodologies/a.md": "# A\n\n" + shared,
        "methodologies/b.md": "# B\n\nrisk priority security apple banana cherry gdpr",
        "methodologies/c.md": "# C\n\nrisk gdpr security banana",
    }
    idx = _fake_index(tmp_path, kb)
    # Force two near-identical chunks from the same source.
    base = idx._chunks[0]
    dup = type(base)(text=base.text + " extra", source=base.source, category=base.category, title=base.title)
    idx._chunks.append(dup)
    idx._vectors.append(list(idx._vectors[0]))
    idx._norms.append(idx._norms[0])

    result = idx.search("risk testing priority", k=3)
    sources = [c["source"] for c in result["chunks"]]
    assert sources.count("methodologies/a.md") == 1, "near-duplicate same-source chunk must be dropped"
    assert len(result["chunks"]) == 3, "dedupe must backfill up to k"


def test_f14_distinct_chunks_of_one_source_are_kept(tmp_path):
    long_doc = "# L\n\n" + "\n\n".join(
        f"Section {i}: " + " ".join(f"word{i}x{j}" for j in range(160)) + " risk" for i in range(4))
    idx = _fake_index(tmp_path, {"methodologies/long.md": long_doc})
    result = idx.search("risk", k=20)
    assert len(result["chunks"]) == len(idx._chunks) > 1


# ── F11: citation filtering ──────────────────────────────────────────────────────

class _CitationIndex:
    """search() returns canned chunks regardless of the query."""
    kb_version = "test"

    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    def search(self, query, category=None, k=5, min_score=0.0):
        self.calls.append((query, min_score))
        return {"chunks": [c for c in self._chunks if c["score"] >= min_score][:k]}


_EU = {"source": "standards/eu_ai_act/EU_AI_Act_Overview.md", "category": "Standard", "score": 0.49}
_IEEE = {"source": "standards/IEEE_829.md", "category": "Standard", "score": 0.6}
_WEAK = {"source": "articles/x.md", "category": "Article", "score": 0.3}


def test_f11_regulation_sources_dropped_unless_allowed():
    idx = _CitationIndex([_EU, _IEEE, _WEAK])
    got = mcp_server._resolve_citations(idx, ["q1", "q2"], allow_regulation=False)
    assert [c["source"] for c in got] == [_IEEE["source"]]  # EU dropped, weak below min score, deduped
    got = mcp_server._resolve_citations(idx, ["q1"], allow_regulation=True)
    assert {c["source"] for c in got} == {_EU["source"], _IEEE["source"]}
    assert all(min_score == mcp_server._CITATION_MIN_SCORE for _, min_score in idx.calls)


def test_f11_generic_document_findings_do_not_cite_the_eu_ai_act(monkeypatch):
    idx = _CitationIndex([_EU, _IEEE])
    monkeypatch.setattr(mcp_server, "_index", idx)
    generic = "# Test Plan\n\nWe will test the checkout page on three browsers. " * 10
    result = _run(_call_tool("review_qa_document", {"document_text": generic, "doc_type": "test_plan"}))
    cited = {c["source"] for f in result["findings"] for c in f["kb_citations"]}
    assert result["findings"]
    assert _EU["source"] not in cited


def test_f11_ai_documents_may_cite_the_eu_ai_act(monkeypatch):
    idx = _CitationIndex([_EU, _IEEE])
    monkeypatch.setattr(mcp_server, "_index", idx)
    doc = "# Test Plan\n\nTesting our machine learning model under the EU AI Act. " * 10
    result = _run(_call_tool("review_qa_document", {"document_text": doc, "doc_type": "test_plan"}))
    cited = {c["source"] for f in result["findings"] for c in f["kb_citations"]}
    assert _EU["source"] in cited


# ── F19: input caps ──────────────────────────────────────────────────────────────

def test_f19_oversized_inputs_rejected_at_the_tool_boundary(monkeypatch):
    monkeypatch.setattr(mcp_server, "_index", _CitationIndex([]))
    big = "x" * (mcp_server.MAX_INPUT_CHARS + 1)
    for tool, args in [
        ("review_qa_document", {"document_text": big}),
        ("assess_qa_maturity", {"project_description": big}),
        ("retrieve_qa_knowledge", {"query": big}),
    ]:
        result = _run(_call_tool(tool, args))
        assert result["error"] == "invalid_argument", tool
        assert result["max_chars"] == mcp_server.MAX_INPUT_CHARS


def test_f19_analyze_test_results_run_list_is_capped(monkeypatch):
    monkeypatch.setattr(mcp_server, "_MAX_RUN_ENTRIES", 2)
    entries = [{"run_id": str(i), "xml": _ONE_TEST_XML} for i in range(3)]
    result = _run(_call_tool("analyze_test_results", {"junit_xml": entries}))
    assert result["error"] == "invalid_argument"


def test_f19_analyze_test_results_oversized_list_payload_rejected(monkeypatch):
    monkeypatch.setattr(mcp_server, "_MAX_RESULTS_INPUT_BYTES", 10)
    result = _run(_call_tool("analyze_test_results", {"junit_xml": [{"run_id": "1", "xml": _ONE_TEST_XML}]}))
    assert result["error"] == "invalid_argument"


# ── F21: background build ────────────────────────────────────────────────────────

def test_f21_background_build_builds_index_and_search_does_not_rebuild(tmp_path):
    kb = tmp_path / "kb"
    (kb / "methodologies").mkdir(parents=True)
    (kb / "methodologies" / "a.md").write_text("# A\n\nrisk testing", encoding="utf-8")
    builds = []
    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()):
        idx = LocalIndex(kb_dir=kb, cache_dir=tmp_path / "cache")
        original = idx._build_fresh

        def counting():
            builds.append(threading.current_thread().name)
            original()

        idx._build_fresh = counting
        idx.start_background_build()
        result = idx.search("risk")  # may race the builder; lock must prevent a second build
        for t in threading.enumerate():
            if t.name == "qai-index-build":
                t.join(timeout=10)
    assert result["chunks"]
    assert len(builds) == 1


def test_f21_main_starts_background_build_after_warmup_before_run(monkeypatch):
    from test_mcp_server import _FakeIndex  # noqa: PLC0415

    fake = _FakeIndex()
    monkeypatch.setattr(mcp_server, "_get_index", lambda: fake)
    monkeypatch.setattr(mcp_server.telemetry, "track_server_start", lambda: None)
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: fake.events.append("run"))
    mcp_server.main()
    assert fake.events == ["warmup", "background_build", "run"]


def test_f21_background_build_failure_never_breaks_startup(monkeypatch):
    class _Idx:
        def warmup_embedder(self):
            pass

        def start_background_build(self):
            raise RuntimeError("boom")

    ran = []
    monkeypatch.setattr(mcp_server, "_get_index", lambda: _Idx())
    monkeypatch.setattr(mcp_server.telemetry, "track_server_start", lambda: None)
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: ran.append(1))
    mcp_server.main()
    assert ran == [1]


# ── Real index calibration (skips when the model is unavailable) ────────────────

@pytest.fixture(scope="module")
def real_index():
    try:
        idx = LocalIndex()
        idx.warmup_embedder()
        idx._ensure_built()
    except Exception as exc:  # no model offline / no KB
        pytest.skip(f"real embedding model unavailable: {exc}")
    return idx


@pytest.mark.parametrize("query", ["how to cook pasta carbonara", "asdfgh qwerty zxcv",
                                   "weather in paris"])
def test_f9_real_index_off_topic_queries_are_flagged(real_index, query):
    result = real_index.search(query, min_score=mcp_server.DEFAULT_MIN_SCORE)
    assert result["low_relevance"] is True and result["chunks"] == []


@pytest.mark.parametrize("query", ["risk-based testing", "test pyramid", "exploratory testing charter",
                                   "OWASP top 10 injection"])
def test_f9_real_index_on_topic_queries_pass(real_index, query):
    result = real_index.search(query, min_score=mcp_server.DEFAULT_MIN_SCORE)
    assert result["low_relevance"] is False and result["chunks"]
