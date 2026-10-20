"""Keep skills/qai-consultant/SKILL.md in sync with the MCP server's contract.

The skill is published outside this repo and tells agents which tools and
prompts to call, so a renamed tool or a changed default must fail CI here
instead of shipping a skill that points at tools that no longer exist.
Parses src/qai_consultant/mcp/server.py with ast so the test needs none of the server's
runtime dependencies.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL = (ROOT / "skills" / "qai-consultant" / "SKILL.md").read_text(encoding="utf-8")
SERVER = ast.parse((ROOT / "src" / "qai_consultant" / "mcp" / "server.py").read_text(encoding="utf-8"))


def _registered(kind: str) -> dict[str, ast.FunctionDef]:
    """Functions decorated with @mcp.<kind>(), keyed by name."""
    found = {}
    for node in SERVER.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == kind
            ):
                found[node.name] = node
    return found


TOOLS = _registered("tool")
PROMPTS = _registered("prompt")


def _defaults(fn: ast.FunctionDef) -> dict[str, object]:
    args = fn.args.args
    defaults = fn.args.defaults
    pairs = zip(args[len(args) - len(defaults):], defaults)
    return {a.arg: ast.literal_eval(d) for a, d in pairs}


def test_every_tool_and_prompt_is_documented():
    for name in [*TOOLS, *PROMPTS]:
        assert f"`{name}" in SKILL, f"{name} is registered on the server but missing from SKILL.md"


def test_every_documented_tool_heading_exists():
    headings = re.findall(r"^### (\w+)\(", SKILL, flags=re.MULTILINE)
    assert headings, "expected one '### tool_name(...)' heading per tool"
    for name in headings:
        assert name in TOOLS, f"SKILL.md documents {name}, which is not an @mcp.tool()"


def test_documented_signatures_match_server():
    for name, params in re.findall(r"^### (\w+)\((.*)\)\s*$", SKILL, flags=re.MULTILINE):
        if params.strip() == "...":
            continue
        fn = TOOLS[name]
        real = [a.arg for a in fn.args.args]
        documented = [p.split("=")[0].strip() for p in params.split(",") if p.strip()]
        assert documented == real, f"{name}: SKILL.md says {documented}, server has {real}"
        real_defaults = _defaults(fn)
        for p in params.split(","):
            if "=" in p:
                key, value = (s.strip() for s in p.split("=", 1))
                assert real_defaults[key] == ast.literal_eval(value), f"{name}.{key} default drifted"


def test_skill_has_no_em_dash():
    assert "—" not in SKILL
