"""Shim so `python src/cli.py` keeps working; real code: qai_consultant.cli."""
from qai_consultant.cli import main

if __name__ == "__main__":
    main()
