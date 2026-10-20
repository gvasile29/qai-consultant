"""Shim so `python src/ingest.py` keeps working; real code: qai_consultant.rag.ingest."""
from qai_consultant.rag.ingest import main

if __name__ == "__main__":
    main()
