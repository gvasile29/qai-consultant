"""Every surface of the maturity assessment must handle the not_a_qa_description status, not render an empty level-0 result."""
from pathlib import Path

from qai_consultant.core.maturity_core import STATUS_NOT_QA, assess_maturity

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_non_qa_text_yields_the_status_the_surfaces_check_for():
    result = assess_maturity(
        "Mix flour and water, add salt, let the dough rest overnight, then bake at 230 degrees until golden brown "
        "and the crust crackles when you tap it. Serve warm with butter and a little honey, and keep any leftovers "
        "wrapped in a clean cloth so the loaf stays soft for the next morning."
    )
    assert result.status == STATUS_NOT_QA
    assert result.stats["reason"]


def test_streamlit_and_cli_branch_on_the_status():
    for rel in ("src/app.py", "src/qai_consultant/cli.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "STATUS_NOT_QA" in text and "result.status == STATUS_NOT_QA" in text, rel
