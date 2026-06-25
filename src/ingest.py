"""
QAI Consultant — Knowledge Base Ingestion Script (v2.0)
Loads all documents from knowledge_base/ and pushes vectors to Pinecone.

Run once locally before deploying:
    python src/ingest.py

Requires env vars (in .env or shell):
    PINECONE_API_KEY
    PINECONE_INDEX_NAME
"""

import os
import sys
import nltk

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from pinecone import Pinecone

# Download required NLTK data silently
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("averaged_perceptron_tagger_eng", quiet=True)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

# ── Config ─────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PINECONE_NAMESPACE = "knowledge-base"
UPSERT_BATCH_SIZE = 100

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


def get_source_category(file_path: Path) -> str:
    for part in file_path.parts:
        if part in SOURCE_CATEGORIES:
            return SOURCE_CATEGORIES[part]
    return "General"


def load_documents(knowledge_base_dir: Path) -> tuple:
    documents = []
    skipped = []
    for file_path in knowledge_base_dir.rglob("*"):
        if file_path.is_symlink():
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
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n---", "\n\n", "\n", " "],
    )
    return splitter.split_documents(documents)


def upsert_to_pinecone(chunks: list, index) -> int:
    """Embed all chunks and upsert to Pinecone in batches. Returns total vectors upserted."""
    print("\n🔄 Loading embedding model...")
    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )

    texts = [chunk.page_content for chunk in chunks]
    print(f"🔄 Generating embeddings for {len(texts)} chunks...")
    embeddings = embeddings_model.embed_documents(texts)

    total_upserted = 0
    total_batches = (len(chunks) + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE

    for batch_num, i in enumerate(range(0, len(chunks), UPSERT_BATCH_SIZE), 1):
        batch_chunks = chunks[i:i + UPSERT_BATCH_SIZE]
        batch_embeddings = embeddings[i:i + UPSERT_BATCH_SIZE]

        vectors = []
        for j, (chunk, embedding) in enumerate(zip(batch_chunks, batch_embeddings)):
            vectors.append({
                "id": f"chunk_{i + j}",
                "values": embedding,
                "metadata": {
                    "text": chunk.page_content,
                    "source": chunk.metadata.get("source", ""),
                    "category": chunk.metadata.get("category", ""),
                    "filename": chunk.metadata.get("filename", ""),
                },
            })

        print(f"  📦 Upserting batch {batch_num}/{total_batches} — {len(vectors)} vectors")
        index.upsert(vectors=vectors, namespace=PINECONE_NAMESPACE)
        total_upserted += len(vectors)

    return total_upserted


def main():
    print("=" * 60)
    print("  QAI Consultant — Knowledge Base Ingestion (v2.0 Pinecone)")
    print("=" * 60)

    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "qai-consultant")
    if not api_key:
        print("\n❌ PINECONE_API_KEY not set. Add it to .env or your environment.")
        sys.exit(1)

    print(f"\n📂 Knowledge base path: {KNOWLEDGE_BASE_DIR}")
    print(f"🌲 Pinecone index: {index_name} / namespace: {PINECONE_NAMESPACE}\n")

    # Step 1 — Load documents
    print("📄 Loading documents...")
    documents, skipped = load_documents(KNOWLEDGE_BASE_DIR)
    print(f"\n✅ Loaded {len(documents)} document(s)")
    if skipped:
        print(f"⚠️  Skipped {len(skipped)} file(s): {', '.join(skipped)}")
    if not documents:
        print("\n❌ No documents found. Check your knowledge_base/ folder.")
        sys.exit(1)

    # Step 2 — Split into chunks
    print("\n✂️  Splitting documents into chunks...")
    chunks = split_documents(documents)
    print(f"✅ Created {len(chunks)} chunk(s)")

    # Step 3 — Connect to Pinecone
    print("\n🌲 Connecting to Pinecone...")
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    print(f"✅ Connected to index '{index_name}'")

    # Step 4 — Clear existing vectors and upsert fresh
    print(f"\n🗑️  Clearing existing vectors in namespace '{PINECONE_NAMESPACE}'...")
    index.delete(delete_all=True, namespace=PINECONE_NAMESPACE)

    total = upsert_to_pinecone(chunks, index)
    print(f"\n✅ Upserted {total} vectors to Pinecone")

    # Step 5 — Sanity check
    print("\n🔍 Running sanity check...")
    embeddings_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )
    query_embedding = embeddings_model.embed_query("test strategy")
    results = index.query(
        vector=query_embedding,
        top_k=3,
        namespace=PINECONE_NAMESPACE,
        include_metadata=True,
    )
    if not results.matches:
        print("⚠️  Sanity check: 0 results returned — Pinecone may still be indexing. Wait a few seconds and retry.")
    else:
        print(f"✅ Sanity check passed — top {len(results.matches)} results for 'test strategy':")
        for i, match in enumerate(results.matches, 1):
            print(f"   {i}. [{match.metadata.get('category', 'N/A')}] {match.metadata.get('filename', 'N/A')} (score: {match.score:.3f})")

    print("\n🎉 Ingestion complete! Pinecone knowledge base is ready.")
    print("=" * 60)


if __name__ == "__main__":
    main()
