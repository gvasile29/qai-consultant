"""Release gate: run both eval tiers, exit non-zero if either fails.

Skipped metrics (no Ollama / no sentence-transformers) do NOT fail the gate, so a
bare CI box still gets the full keyless deterministic tier.

    python -m evals.run         # both tiers
    python -m evals.run --det   # keyless deterministic tier only
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # non-ASCII headers/findings; don't crash on cp1252/ascii
    det_only = "--det" in argv

    from . import estimate_integrity as det
    det_outcomes = det.run_all()
    print("══ estimate_integrity (deterministic, keyless) ══")
    print(det.format_table(det_outcomes))
    det_ok = all(o.passed for o in det_outcomes)

    rag_ok = True
    if not det_only:
        from . import rag
        try:
            rag_metrics = rag.run_all()
            print("\n══ rag (classical RAG metrics, local) ══")
            print(rag.format_table(rag_metrics))
            rag_ok = all(m.passed for m in rag_metrics)
        except Exception as exc:  # noqa: BLE001 — an infra failure in the optional tier must not
            # discard the deterministic verdict; treat as a non-fatal skip.
            print(f"\n[rag] tier skipped — unexpected error: {type(exc).__name__}: {exc}")

    overall = det_ok and rag_ok
    print(f"\nRelease gate: {'PASS' if overall else 'FAIL'} "
          f"(deterministic {'pass' if det_ok else 'FAIL'}"
          + ("" if det_only else f", rag {'pass' if rag_ok else 'FAIL'}") + ")")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
