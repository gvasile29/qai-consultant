"""
QAI Consultant — Knowledge Base Ingestion Script
Loads all documents from knowledge_base/ into a local ChromaDB vector store.

Run this once after cloning, and again whenever you add new files to knowledge_base/.
For automatic re-ingestion of new files, the KnowledgeBaseWatcher (knowledge_watcher.py)
handles incremental updates while the app is running.

Supported file types: .pdf, .md, .txt
Output: chroma_db/ (ChromaDB persistent store)
"""

import os
import sys
import nltk

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# Download required NLTK data silently
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("averaged_perceptron_tagger_eng", quiet=True)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
CHROMA_DIR = BASE_DIR / "chroma_db"

# ── Supported file types ───────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {
    ".pdf": PyPDFLoader,
    ".md": TextLoader,
    ".txt": TextLoader,
}

# ── Source metadata mapping ────────────────────────────────────────────────────
SOURCE_CATEGORIES = {
    "standards": "Standard",
    "methodologies": "Methodology",
    "articles": "Article",
    "expert_knowledge": "Expert Knowledge",
}

# ── Batch size for embedding ───────────────────────────────────────────────────
BATCH_SIZE = 100


def get_source_category(file_path: Path) -> str:
    """Determine source category based on folder structure."""
    for part in file_path.parts:
        if part in SOURCE_CATEGORIES:
            return SOURCE_CATEGORIES[part]
    return "General"


def load_documents(knowledge_base_dir: Path) -> list:
    """Recursively load all supported documents from the knowledge base."""
    documents = []
    skipped = []

    for file_path in knowledge_base_dir.rglob("*"):
        if file_path.is_symlink():  # skip symlinks — cycles would loop forever
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if file_path.name.startswith("."):
            continue

        loader_class = SUPPORTED_EXTENSIONS[file_path.suffix.lower()]
        try:
            loader = loader_class(str(file_path))
            docs = loader.load()

            category = get_source_category(file_path)
            for doc in docs:
                doc.metadata["source"] = str(file_path.relative_to(knowledge_base_dir))
                doc.metadata["category"] = category
                doc.metadata["filename"] = file_path.name

            documents.extend(docs)
            print(f"  ✅ Loaded: {file_path.relative_to(knowledge_base_dir)}")

        except Exception as e:
            skipped.append(file_path.name)
            print(f"  ⚠️  Skipped: {file_path.name} — {e}")

    return documents, skipped


def split_documents(documents: list) -> list:
    """Split documents into chunks suitable for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n---", "\n\n", "\n", " "],
    )
    return splitter.split_documents(documents)


def create_vector_store(chunks: list, chroma_dir: Path) -> Chroma:
    """Create and persist a ChromaDB vector store using batch processing."""
    print("\n🔄 Loading embedding model (this may take a moment on first run)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )

    # Process first batch to create the collection
    print(f"🔄 Creating vector store — processing {len(chunks)} chunks in batches of {BATCH_SIZE}...")
    
    first_batch = chunks[:BATCH_SIZE]
    vector_store = Chroma.from_documents(
        documents=first_batch,
        embedding=embeddings,
        persist_directory=str(chroma_dir),
        collection_name="qai_knowledge_base",
    )

    # Process remaining batches
    remaining = chunks[BATCH_SIZE:]
    total_batches = (len(remaining) // BATCH_SIZE) + 1
    
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 2
        print(f"  📦 Batch {batch_num}/{total_batches + 1} — {len(batch)} chunks")
        vector_store.add_documents(batch)

    vector_store.persist()
    return vector_store


def main():
    print("=" * 60)
    print("  QAI Consultant — Knowledge Base Ingestion")
    print("=" * 60)
    print(f"\n📂 Knowledge base path: {KNOWLEDGE_BASE_DIR}")
    print(f"💾 Vector store path:   {CHROMA_DIR}\n")

    # Step 1 — Load documents
    print("📄 Loading documents...")
    documents, skipped = load_documents(KNOWLEDGE_BASE_DIR)
    print(f"\n✅ Loaded {len(documents)} document(s)")
    if skipped:
        print(f"⚠️  Skipped {len(skipped)} file(s): {', '.join(skipped)}")

    if not documents:
        print("\n❌ No documents found. Check your knowledge_base/ folder.")
        return

    # Step 2 — Split into chunks
    print("\n✂️  Splitting documents into chunks...")
    chunks = split_documents(documents)
    print(f"✅ Created {len(chunks)} chunk(s)")

    # Step 3 — Create vector store in batches
    vector_store = create_vector_store(chunks, CHROMA_DIR)
    print(f"\n✅ Vector store saved to: {CHROMA_DIR}")

    # Step 4 — Sanity check
    print("\n🔍 Running sanity check...")
    results = vector_store.similarity_search("test strategy", k=3)
    print(f"✅ Sanity check passed — found {len(results)} relevant chunk(s) for 'test strategy'")
    for i, result in enumerate(results, 1):
        print(f"   {i}. [{result.metadata.get('category', 'N/A')}] {result.metadata.get('filename', 'N/A')}")

    print("\n🎉 Ingestion complete! QAI Consultant knowledge base is ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()
