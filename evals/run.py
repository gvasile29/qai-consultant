"""Release gate: run the remaining eval tier (rag + local_index_parity),
exit non-zero if either fails.

The 4 deterministic "tier-1" checks (estimate_integrity, review_integrity,
results_integrity, maturity_integrity) moved to ordinary pytest tests
(tests/test_estimate_integrity.py etc.) in the 2026-09-17 CI/evals
simplification — they no longer need a separate runner or the --det flag
that used to select them. Both surviving modules already SKIP (not fail)
without the embedding stack / an LLM key, so no flag is needed to make this
safe to run on a keyless box.

    python -m evals.run
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # non-ASCII headers/findings; don't crash on cp1252/ascii

    from . import rag
    print("══ rag (classical RAG metrics, local) ══")
    try:
        rag_metrics = rag.run_all()
        print(rag.format_table(rag_metrics))
        rag_ok = all(m.passed for m in rag_metrics)
    except Exception as exc:  # noqa: BLE001 — infra failures already SKIP inside run_all;
        # an unexpected crash here fails the gate rather than passing silently.
        print(f"\n[rag] tier errored (did not run): {type(exc).__name__}: {exc}")
        rag_ok = False

    from . import local_index_parity
    print("\n══ local_index_parity (served LocalIndex vs. rag_golden.jsonl) ══")
    try:
        local_index_metrics = local_index_parity.run_all()
        print(local_index_parity.format_table(local_index_metrics))
        local_index_ok = all(m.passed for m in local_index_metrics)
    except Exception as exc:  # noqa: BLE001 — same rationale as the rag tier above
        print(f"\n[local_index_parity] tier errored (did not run): {type(exc).__name__}: {exc}")
        local_index_ok = False

    overall = rag_ok and local_index_ok
    print(f"\nRelease gate: {'PASS' if overall else 'FAIL'} "
          f"(rag {'pass' if rag_ok else 'FAIL'}"
          f", local_index_parity {'pass' if local_index_ok else 'FAIL'})")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
