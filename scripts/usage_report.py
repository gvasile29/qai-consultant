"""Usage report for QAI Consultant: Streamlit app metrics + MCP adoption.

Same numbers the landing page's adoption strip shows (src/qai_consultant/observability/adoption_metrics.py),
in full detail:

Streamlit side (needs PINECONE_API_KEY / PINECONE_INDEX_NAME in .env, the same
index the live app writes to):
  - visits (one per browser session)
  - generation runs (sum of usage_guard's daily usage_global_<date> counters)
  - downloads per document and format (.md / .pdf)
  - "Was this Test Strategy useful?" feedback: yes / partially / no

MCP side (keyless):
  - qai-consultant-mcp PyPI downloads, mirrors excluded (pypistats keeps
    ~180 days). Includes installs that came via the MCP registry and Glama,
    which publish no install counts of their own. Also counts CI and bots.
  - GitHub stars/forks, MCP registry published versions
  - per-tool usage: see the PostHog project (telemetry on by default since
    v3.7.0); not pulled here, it needs a personal API key.

Usage:
    python scripts/usage_report.py            # everything
    python scripts/usage_report.py --mcp      # keyless sources only
    python scripts/usage_report.py --app      # Streamlit only
    python scripts/usage_report.py --json     # machine-readable output
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qai_consultant.observability.adoption_metrics import (  # noqa: E402 - needs src/ on sys.path first
    fetch_app_metrics,
    fetch_github_metrics,
    fetch_pypi_metrics,
    fetch_registry_metrics,
)


def _print_app(app: dict) -> None:
    print("Streamlit app (quality-ai-consultant.streamlit.app)")
    print(f"  Visits:            {app['visits']:,}")
    print(f"  Generation runs:   {app['generation_runs']:,} "
          f"(since {app['generation_runs_since']}, {app['generation_run_days']} active days)")
    print("  Downloads:              .md    .pdf")
    for doc, by_fmt in app["downloads"].items():
        print(f"    {doc:<20} {by_fmt['md']:>5} {by_fmt['pdf']:>7}")
    tot = app["downloads_total"]
    print(f"    {'TOTAL':<20} {tot['md']:>5} {tot['pdf']:>7}")
    fb = app["feedback"]
    pct = app["feedback_useful_pct"]
    print(f"  Feedback:          yes {fb['yes']}, partially {fb['partially']}, no {fb['no']}"
          + (f"  ({pct}% useful or partially useful)" if pct is not None else ""))


def _print_pypi(pypi: dict) -> None:
    print(f"MCP package ({pypi['package']} on PyPI, mirrors excluded)")
    print(f"  Downloads since {pypi['since']}: {pypi['downloads_total']:,}")
    print(f"  Last month: {pypi['last_month']:,}   last week: {pypi['last_week']:,}   last day: {pypi['last_day']:,}")


def _print_github(gh: dict) -> None:
    print(f"GitHub ({gh['repo']}): {gh['stars']} stars, {gh['forks']} forks")


def _print_registry(reg: dict) -> None:
    print(f"MCP registry ({reg['name']}): {reg['versions_published']} versions published, "
          f"latest {reg['latest_version']}")


SECTIONS = (
    ("app", fetch_app_metrics, _print_app, "app"),
    ("pypi", fetch_pypi_metrics, _print_pypi, "mcp"),
    ("github", fetch_github_metrics, _print_github, "mcp"),
    ("registry", fetch_registry_metrics, _print_registry, "mcp"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app", action="store_true", help="Streamlit metrics only")
    parser.add_argument("--mcp", action="store_true", help="keyless MCP/PyPI/GitHub/registry metrics only")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()
    wanted = {"app", "mcp"} if args.app == args.mcp else ({"app"} if args.app else {"mcp"})

    report, failed = {}, False
    for name, fetch, _printer, group in SECTIONS:
        if group not in wanted:
            continue
        try:
            report[name] = fetch()
        except Exception as exc:
            report[name] = {"error": str(exc)}
            failed = True

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, _fetch, printer, _group in SECTIONS:
            if name not in report:
                continue
            if "error" in report[name]:
                print(f"{name}: FAILED - {report[name]['error']}")
            else:
                printer(report[name])
            print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
