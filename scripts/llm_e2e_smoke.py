"""End-to-end LLM smoke run: one full generate_all() pipeline against the real
providers, then content checks on what actually got saved.

Exists because stage badges going green proved nothing twice: v3.6.1 found
OpenRouter's auto-router answering a Risk Register prompt with a safety
classifier's "User Safety: safe", and ~3 weeks of Mistral 429s went unnoticed
because LLMClient silently fell back. Run this after any change to MISTRAL_MODEL,
OPENROUTER_MODELS, LLM_NUM_PREDICT, prompt builders, or the streaming/fallback code.

Usage:
    python scripts/llm_e2e_smoke.py                    # web_app template
    python scripts/llm_e2e_smoke.py --template automotive
    python scripts/llm_e2e_smoke.py --require-mistral  # fail if any call fell back

Costs one full generation (4 streamed docs + 1 narrative call) of the shared
daily quota. Needs MISTRAL_API_KEY / OPENROUTER_API_KEY / PINECONE_* in .env.
Exit 0 = all checks pass, 1 = a content check failed, 2 = could not run
(setup failed, or both providers failed and no LLM document was produced).
"""
import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

MIN_DOC_CHARS = 1500
MIN_RISK_ROWS = 3
GARBAGE_MARKERS = ("User Safety:", "I cannot help", "I can't help", "As an AI language model")
# Documents scored with the review rubric (core/review_core.py); the Risk Register and
# Effort Report are not Test Plan/Strategy-shaped, so the rubric does not apply.
REVIEWED_DOC_TYPES = {"strategy": "test_strategy", "test_plan": "test_plan"}
DOCS = (
    ("risk_register", "risk_path", "Risk Register"),
    ("effort_report", "effort_path", "Effort Report"),
    ("strategy", "strategy_path", "Test Strategy"),
    ("test_plan", "test_plan_path", "Test Plan"),
)


class _FallbackCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []
        self.both_failed = 0

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if msg.startswith("Both LLM providers failed"):
            self.both_failed += 1
        elif "OpenRouter" in msg or "not falling back" in msg:
            self.messages.append(msg)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # agent error messages carry emoji; don't crash on cp1252 pipes
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--template", default="web_app")
    parser.add_argument("--require-mistral", action="store_true")
    args = parser.parse_args()

    from qai_consultant.rag.agent import MISTRAL_MODEL, QAIAgent
    from qai_consultant.core.dialogue import ProjectContext
    from qai_consultant.compliance.doc_validation import consistency_problems, review_problems
    from qai_consultant.compliance.output_guards import lint_output
    from qai_consultant.core.risk_ledger import parse_risk_matrix
    from qai_consultant.generation.strategy_generator import StrategyGenerator
    from qai_consultant.generation.templates import TEMPLATES

    if args.template not in TEMPLATES:
        print(f"Unknown template {args.template!r}; choose from {sorted(TEMPLATES)}")
        return 2
    fields = {k: v for k, v in TEMPLATES[args.template].items() if k != "label"}
    context = ProjectContext(**fields)
    context_text = context.to_summary().lower()
    # Figures quoted verbatim from the KB are legitimate; the sanitizer exempts
    # them, so the gate must see the same corpus.
    knowledge_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in (_REPO_ROOT / "knowledge_base").rglob("*.md")
    )

    counter = _FallbackCounter()
    logging.getLogger("qai").addHandler(counter)

    print(f"Primary model: {MISTRAL_MODEL} | template: {args.template}")
    try:
        results = StrategyGenerator(QAIAgent()).generate_all(context)
    except Exception as e:  # noqa: BLE001 - report any setup/provider failure as "could not run"
        print(f"COULD NOT RUN: {type(e).__name__}: {e}")
        return 2

    # generate_all() isolates each step, so a provider outage arrives as empty
    # documents rather than an exception; report it as "could not run", not as
    # a content regression.
    if counter.both_failed and not any((results.get(k) or "").strip() for k, _, _ in DOCS if k != "effort_report"):
        print(f"COULD NOT RUN: both LLM providers failed {counter.both_failed} time(s); see logs/qai_consultant.log")
        return 2

    failures: list[str] = []
    for text_key, path_key, label in DOCS:
        text = results.get(text_key) or ""
        path = results.get(path_key)
        problems = []
        if len(text.strip()) < MIN_DOC_CHARS:
            problems.append(f"only {len(text.strip())} chars (< {MIN_DOC_CHARS})")
        hit = next((m for m in GARBAGE_MARKERS if m in text), None)
        if hit:
            problems.append(f"contains garbage marker {hit!r}")
        problems += lint_output(text, context_text, knowledge_text)
        if text_key in REVIEWED_DOC_TYPES and text.strip():
            problems += review_problems(text, REVIEWED_DOC_TYPES[text_key])
        if not path or not Path(path).is_file():
            problems.append("no saved file")
        elif len(Path(path).read_text(encoding="utf-8").strip()) < MIN_DOC_CHARS:
            problems.append("saved file is (near-)empty")
        status = "FAIL" if problems else "ok"
        print(f"  [{status}] {label}: {len(text)} chars -> {path}")
        failures += [f"{label}: {p}" for p in problems]

    rows = parse_risk_matrix(results.get("risk_register") or "")
    print(f"  [{'ok' if len(rows) >= MIN_RISK_ROWS else 'FAIL'}] Risk Matrix rows parsed: {len(rows)}")
    if len(rows) < MIN_RISK_ROWS:
        failures.append(f"Risk Matrix: {len(rows)} rows parsed (< {MIN_RISK_ROWS})")

    if not results.get("effort_data"):
        failures.append("effort_data missing")

    cross = consistency_problems(
        results.get("risk_register") or "", results.get("strategy") or "",
        results.get("test_plan") or "", results.get("effort_data"),
    )
    print(f"  [{'FAIL' if cross else 'ok'}] Cross-document consistency: {len(cross)} problem(s)")
    failures += [f"Consistency: {p}" for p in cross]

    print(f"  Fallback/stream warnings: {len(counter.messages)}")
    for msg in counter.messages:
        print(f"    - {msg[:200]}")
    if counter.messages and args.require_mistral:
        failures.append(f"{len(counter.messages)} call(s) did not stay on Mistral")

    if failures:
        print("\nFAILED:\n" + "\n".join(f"  - {f}" for f in failures))
        return 1
    print("\nAll checks passed. Still skim the saved files: these checks catch empty/garbage output, not bad advice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
