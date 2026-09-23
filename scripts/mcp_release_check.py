"""Pre-release check for qai-consultant-mcp: runs everything up through (but
never including) the actual `twine upload`, per
docs/plans/2026-07-22-mcp-distribution-plan.md's human-gated-upload rule.
Also checks whether the locally-recorded version has actually reached PyPI,
closing the gap that let v3.5.0 sit unpublished for days with no error
anywhere (see CLAUDE.md's Gotchas).

Usage:
    python scripts/mcp_release_check.py --live-version   # PyPI vs. local version.py only
    python scripts/mcp_release_check.py --preflight      # tests/lint/mypy/bandit/build/twine-check/smoke-install
    python scripts/mcp_release_check.py --all            # both (default if no flag given)

Never runs `twine upload`. That step stays manual and human-approved.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import venv
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE_NAME = "qai-consultant-mcp"


def _local_version() -> str:
    text = (_REPO_ROOT / "src" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("Could not find __version__ in src/version.py")
    return match.group(1)


def check_live_version() -> int:
    local = _local_version()
    url = f"https://pypi.org/pypi/{_PACKAGE_NAME}/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as exc:
        print(f"Could not reach PyPI: {exc}", file=sys.stderr)
        return 1

    live = data["info"]["version"]
    print(f"local (src/version.py): {local}")
    print(f"live  (PyPI):           {live}")
    if local == live:
        print("MATCH: the local version is what's actually published.")
        return 0
    print("MISMATCH: local version has not reached PyPI yet - do not assume the tool surface is live.")
    return 1


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=_REPO_ROOT)


def run_preflight() -> int:
    gates = [
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:warnings"],
        [sys.executable, "-m", "ruff", "check", "src/", "tests/", "--ignore", "E501,E402,F401,W291,W293"],
        [sys.executable, "-m", "mypy", "src/"],
        [sys.executable, "-m", "bandit", "-r", "src/", "-ll"],
    ]
    for gate in gates:
        if _run(gate).returncode != 0:
            print(f"FAIL: {' '.join(gate)}", file=sys.stderr)
            return 1

    dist_dir = _REPO_ROOT / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if _run([sys.executable, "-m", "build"]).returncode != 0:
        return 1

    artifacts = [str(p) for p in dist_dir.glob("*")]
    if not artifacts:
        print("FAIL: build produced no artifacts in dist/", file=sys.stderr)
        return 1
    if _run(["twine", "check", *artifacts]).returncode != 0:
        return 1

    return _smoke_install(artifacts)


def _smoke_install(artifacts: list[str]) -> int:
    wheels = [a for a in artifacts if a.endswith(".whl")]
    if not wheels:
        print("No wheel found in dist/ to smoke-test.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        venv_dir = Path(tmp) / "smoke_venv"
        venv.create(venv_dir, with_pip=True)
        scripts_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
        pip = scripts_dir / ("pip.exe" if sys.platform == "win32" else "pip")

        install = subprocess.run([str(pip), "install", "--quiet", wheels[0]])
        if install.returncode != 0:
            print("FAIL: smoke-install of the built wheel failed.", file=sys.stderr)
            return 1

        entry = scripts_dir / ("qai-consultant-mcp.exe" if sys.platform == "win32" else "qai-consultant-mcp")
        if not entry.exists():
            print(f"FAIL: console script not found at {entry}", file=sys.stderr)
            return 1
        print(f"Smoke-install OK: {entry} exists in a clean venv.")
        print(
            "For the full stdio handshake / cold-start deadlock check against a real "
            "install, point scripts/verify_mcp_stdio_no_deadlock.py's StdioServerParameters "
            f"command at {entry} instead of src/mcp_server.py."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live-version", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if not (args.live_version or args.preflight or args.all):
        args.all = True

    exit_code = 0
    if args.live_version or args.all:
        exit_code = max(exit_code, check_live_version())
    if args.preflight or args.all:
        exit_code = max(exit_code, run_preflight())
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
