"""PreToolUse hook: block Claude from editing files that must not be hand-edited.

- .env / .env.*        live API keys (Mistral, OpenRouter, Pinecone)
- src/_theme_fonts.py  generated base64 font data; manual edits get overwritten

Exit code 2 blocks the tool call and shows the reason to Claude.
"""

import json
import sys
from pathlib import PurePath

ENV_EXAMPLE = ".env.example"
GENERATED = {"_theme_fonts.py"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    name = PurePath(file_path.replace("\\", "/")).name
    if (name == ".env" or name.startswith(".env.")) and name != ENV_EXAMPLE:
        print(f"Blocked: {name} holds live API keys. Ask the user to edit it themselves.", file=sys.stderr)
        return 2
    if name in GENERATED:
        print(f"Blocked: {name} is generated. Regenerate it instead of hand-editing.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
