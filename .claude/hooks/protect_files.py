"""PreToolUse hook: block Claude from editing files that must not be hand-edited.

- .env / .env.*        live API keys (Mistral, OpenRouter, Pinecone)
- src/qai_consultant/ui/_theme_fonts.py  generated base64 font data; manual edits get overwritten

Names are normalized the way Windows resolves them (case-insensitive, trailing
dots/spaces dropped, NTFS alternate-data-stream suffix ignored) so `.ENV`,
`.env ` or `.env::$DATA` cannot slip past. Fails closed on an unreadable payload.
Shell tools (Bash/PowerShell) are not covered; this guards the file-edit tools.

Exit code 2 blocks the tool call and shows the reason to Claude.
"""

import json
import re
import sys

ENV_EXAMPLE = ".env.example"
GENERATED = {"_theme_fonts.py"}


def normalized_name(file_path: str) -> str:
    name = re.split(r"[\\/]", file_path)[-1]
    name = name.split(":", 1)[0]  # NTFS alternate data stream, e.g. ".env::$DATA"
    return name.rstrip(". ").casefold()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool_input = payload.get("tool_input") or {}
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    except (json.JSONDecodeError, AttributeError):
        print("Blocked: protect_files hook could not parse the tool payload.", file=sys.stderr)
        return 2
    name = normalized_name(file_path)
    if (name == ".env" or name.startswith(".env.")) and name != ENV_EXAMPLE:
        print(f"Blocked: {name} holds live API keys. Ask the user to edit it themselves.", file=sys.stderr)
        return 2
    if name in GENERATED:
        print(f"Blocked: {name} is generated. Regenerate it instead of hand-editing.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
