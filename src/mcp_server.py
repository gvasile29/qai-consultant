"""Shim so `python src/mcp_server.py` keeps working; real code: qai_consultant.mcp.server."""
from qai_consultant.mcp.server import main

if __name__ == "__main__":
    main()
