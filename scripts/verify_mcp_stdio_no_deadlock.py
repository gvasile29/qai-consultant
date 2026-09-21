"""Manual pre-release check: does the MCP server's first real tool call
deadlock on Windows? (See mcp_server.py's main() comment and
docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md,
section 5.) Launches the real server as a subprocess over piped stdio —
exactly how Claude Desktop/Claude Code launch it — and calls a real tool.
A hang past the timeouts below means the warmup-before-mcp.run() fix is
broken for the current embedding backend.

Run manually before every MCP release:
    python scripts/verify_mcp_stdio_no_deadlock.py
"""
import asyncio
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVER = _REPO_ROOT / "src" / "mcp_server.py"


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(_SERVER)])
    start = time.monotonic()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=90)
            print(f"initialize() returned in {time.monotonic() - start:.1f}s")

            result = await asyncio.wait_for(
                session.call_tool("retrieve_qa_knowledge", {"query": "risk-based testing", "k": 3}),
                timeout=60,
            )
            total = time.monotonic() - start
            if result.isError:
                print(f"FAIL: tool call returned isError=True after {total:.1f}s: {result}")
                return 1
            print(f"first retrieve_qa_knowledge call succeeded in {total:.1f}s total")

    print("PASS: no deadlock on first real tool call")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except asyncio.TimeoutError:
        print("FAIL: timed out waiting for a response — likely the loader-lock deadlock")
        exit_code = 1
    raise SystemExit(exit_code)
