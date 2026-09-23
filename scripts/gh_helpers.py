"""Small `gh` CLI wrapper replacing the ad hoc `python3 -c "import json,sys; ..."`
one-liners that had accumulated in .claude/settings.local.json for parsing PR
lists, workflow run lists, and a PR's head SHA. Requires the `gh` CLI to be
authenticated already (`gh auth status`).

Usage:
    python scripts/gh_helpers.py list-prs [--state open|closed|all] [--limit N]
    python scripts/gh_helpers.py workflow-runs [--workflow NAME] [--branch BRANCH] [--limit N]
    python scripts/gh_helpers.py pr-head-sha PR_NUMBER
"""
import argparse
import json
import subprocess
import sys


def _gh_json(args: list[str]) -> object:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    return json.loads(result.stdout)


def list_prs(state: str, limit: int) -> int:
    prs = _gh_json([
        "pr", "list", "--state", state, "--limit", str(limit),
        "--json", "number,title,author,isDraft,url",
    ])
    for pr in prs:
        print(
            f"PR #{pr['number']}: {pr['title']} | "
            f"author: {pr['author']['login']} | draft: {pr['isDraft']} | url: {pr['url']}"
        )
    return 0


def workflow_runs(workflow: str | None, branch: str | None, limit: int) -> int:
    args = ["run", "list", "--limit", str(limit), "--json", "status,conclusion,headSha,createdAt,workflowName"]
    if workflow:
        args += ["--workflow", workflow]
    if branch:
        args += ["--branch", branch]
    runs = _gh_json(args)
    for run in runs:
        print(f"{run['status']} {run['conclusion']} {run['headSha'][:7]} {run['createdAt']} ({run['workflowName']})")
    return 0


def pr_head_sha(pr_number: str) -> int:
    pr = _gh_json(["pr", "view", pr_number, "--json", "headRefOid"])
    print(pr["headRefOid"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-prs")
    p_list.add_argument("--state", default="open", choices=["open", "closed", "all"])
    p_list.add_argument("--limit", type=int, default=30)

    p_runs = sub.add_parser("workflow-runs")
    p_runs.add_argument("--workflow", default=None)
    p_runs.add_argument("--branch", default=None)
    p_runs.add_argument("--limit", type=int, default=10)

    p_sha = sub.add_parser("pr-head-sha")
    p_sha.add_argument("pr_number")

    args = parser.parse_args()

    if args.command == "list-prs":
        return list_prs(args.state, args.limit)
    if args.command == "workflow-runs":
        return workflow_runs(args.workflow, args.branch, args.limit)
    if args.command == "pr-head-sha":
        return pr_head_sha(args.pr_number)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
