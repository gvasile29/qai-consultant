"""
Tests for src/templates.py — project quick-start templates.

Covers:
1.  TEMPLATES contains exactly 4 entries
2.  Every template has all 11 required dialogue keys
3.  Every template has a non-empty 'label' field
4.  No template field value is empty or whitespace-only
5.  TEMPLATE_OPTIONS has 5 entries (None + 4 templates)
6.  First TEMPLATE_OPTIONS entry is the "Start from scratch" sentinel (key=None)
7.  TEMPLATE_OPTIONS keys match TEMPLATES keys
8.  team_qa_size and team_dev_size are numeric strings
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from templates import TEMPLATES, TEMPLATE_OPTIONS

REQUIRED_KEYS = {
    "project_name", "project_description", "project_type", "tech_stack",
    "methodology", "timeline", "team_qa_size", "team_dev_size",
    "known_risks", "existing_automation", "compliance_requirements",
}


def test_templates_has_four_entries():
    assert len(TEMPLATES) == 4, f"Expected 4 templates, got {len(TEMPLATES)}"


def test_all_templates_have_required_keys():
    for key, tmpl in TEMPLATES.items():
        missing = REQUIRED_KEYS - set(tmpl.keys())
        assert not missing, f"Template '{key}' missing keys: {missing}"


def test_all_templates_have_label():
    for key, tmpl in TEMPLATES.items():
        assert tmpl.get("label"), f"Template '{key}' has empty or missing 'label'"


def test_no_template_field_is_empty():
    for key, tmpl in TEMPLATES.items():
        for field in REQUIRED_KEYS:
            val = tmpl.get(field, "")
            assert val and val.strip(), (
                f"Template '{key}' field '{field}' is empty or whitespace"
            )


def test_template_options_length():
    assert len(TEMPLATE_OPTIONS) == 5, (
        f"Expected 5 TEMPLATE_OPTIONS (None + 4), got {len(TEMPLATE_OPTIONS)}"
    )


def test_template_options_first_is_sentinel():
    label, key = TEMPLATE_OPTIONS[0]
    assert key is None, "First TEMPLATE_OPTIONS entry should have key=None"
    assert label, "First TEMPLATE_OPTIONS entry should have a non-empty label"


def test_template_options_keys_match_templates():
    option_keys = {key for _, key in TEMPLATE_OPTIONS if key is not None}
    assert option_keys == set(TEMPLATES.keys()), (
        f"TEMPLATE_OPTIONS keys {option_keys} don't match TEMPLATES keys {set(TEMPLATES.keys())}"
    )


def test_team_sizes_are_numeric_strings():
    for key, tmpl in TEMPLATES.items():
        qa = tmpl["team_qa_size"]
        dev = tmpl["team_dev_size"]
        assert qa.isdigit(), f"Template '{key}' team_qa_size '{qa}' is not a numeric string"
        assert dev.isdigit(), f"Template '{key}' team_dev_size '{dev}' is not a numeric string"


if __name__ == "__main__":
    tests = [
        ("TEMPLATES has 4 entries", test_templates_has_four_entries),
        ("All templates have required keys", test_all_templates_have_required_keys),
        ("All templates have label", test_all_templates_have_label),
        ("No template field is empty", test_no_template_field_is_empty),
        ("TEMPLATE_OPTIONS has 5 entries", test_template_options_length),
        ("First option is sentinel (None key)", test_template_options_first_is_sentinel),
        ("TEMPLATE_OPTIONS keys match TEMPLATES", test_template_options_keys_match_templates),
        ("Team sizes are numeric strings", test_team_sizes_are_numeric_strings),
    ]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
