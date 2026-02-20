"""
QAI Consultant — Core Agent
Connects to Ollama (LLM) and ChromaDB (knowledge base) and provides RAG query functionality.
"""

import os
import ollama
from pathlib import Path

# Disable ChromaDB telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_MODEL = "mistral"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_RESULTS = 5


class QAIAgent:
    def __init__(self):
        self.vector_store = None
        self.embeddings = None
        self._load_knowledge_base()
        self._check_ollama()

    def _load_knowledge_base(self):
        """Load the ChromaDB vector store."""
        if not CHROMA_DIR.exists():
            raise FileNotFoundError(
                f"Knowledge base not found at {CHROMA_DIR}. "
                "Please run 'python src/ingest.py' first."
            )

        print("🔄 Loading knowledge base...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
        )
        self.vector_store = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=self.embeddings,
            collection_name="qai_knowledge_base",
        )
        print("✅ Knowledge base loaded")

    def _check_ollama(self):
        """Verify Ollama is running and the model is available."""
        try:
            models = ollama.list()
            available = [m["name"] for m in models.get("models", [])]
            if not any(OLLAMA_MODEL in m for m in available):
                raise RuntimeError(
                    f"Model '{OLLAMA_MODEL}' not found in Ollama. "
                    f"Run: ollama pull {OLLAMA_MODEL}"
                )
            print(f"✅ Ollama ready — using model: {OLLAMA_MODEL}")
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect to Ollama. Make sure it's running.\n"
                f"Error: {e}"
            )

    def retrieve_knowledge(self, query: str, k: int = TOP_K_RESULTS) -> list:
        """Retrieve relevant knowledge chunks from the knowledge base."""
        results = self.vector_store.similarity_search(query, k=k)
        return results

    def format_knowledge_context(self, chunks: list) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            category = chunk.metadata.get("category", "General")
            filename = chunk.metadata.get("filename", "Unknown")
            context_parts.append(
                f"[Source {i} — {category}: {filename}]\n{chunk.page_content}"
            )
        return "\n\n---\n\n".join(context_parts)

    def ask(self, prompt: str, system_prompt: str = None) -> str:
        """Send a prompt to Ollama and return the response."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages,
        )
        return response["message"]["content"]

    def ask_with_rag(self, query: str, system_prompt: str = None) -> tuple:
        """
        Ask a question using RAG — retrieve relevant knowledge first,
        then generate a response using the retrieved context.
        Returns (response, sources)
        """
        # Retrieve relevant knowledge
        chunks = self.retrieve_knowledge(query)
        context = self.format_knowledge_context(chunks)

        # Build RAG prompt
        rag_prompt = f"""Use the following QA knowledge base excerpts to inform your response.
Always base your recommendations on established QA methodologies and best practices.

KNOWLEDGE BASE CONTEXT:
{context}

USER QUERY:
{query}
"""
        response = self.ask(rag_prompt, system_prompt=system_prompt)

        # Extract unique sources
        sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in chunks
        })

        return response, sources


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    agent = QAIAgent()

    print("\n🧪 Testing RAG query...\n")
    response, sources = agent.ask_with_rag(
        "What should a Test Strategy include for a web application?"
    )

    print("📋 Response:")
    print(response)
    print("\n📚 Sources used:")
    for s in sources:
        print(f"  - {s}")
