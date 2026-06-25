"""
QAI Consultant — Core Agent
Connects to Ollama (LLM) and ChromaDB (knowledge base) and provides RAG query functionality.
"""

import os
import ollama
from ollama import Client as OllamaClient
from pathlib import Path

# Disable ChromaDB telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def _get_secret(key: str) -> str:
    """Lookup order: Streamlit secrets → os.environ (populated by .env via python-dotenv)."""
    from dotenv import load_dotenv
    load_dotenv()
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    val = os.environ.get(key)
    if val:
        return val
    raise ValueError(
        f"Missing required secret: '{key}'. "
        "Add it to .env (local dev) or Streamlit Cloud secrets (deployed)."
    )


# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_MODEL     = "mistral:7b-instruct-q4_0"   # quantized: ~3x faster than float16 on CPU
EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_RESULTS    = 5
RAG_K_GENERATION = 5        # chunks for Risk Register + Test Strategy prompts (was hardcoded 8)
GENERATION_TIMEOUT = 300    # real HTTP wall-clock timeout (seconds) — passed to httpx

# ── LLM Generation Parameters ──────────────────────────────────────────────────
LLM_NUM_CTX     = 4096   # context window tokens (Mistral default: 32768 → 8x memory reduction)
LLM_NUM_PREDICT = 1500   # max output tokens (default: unlimited → runaway generation)
LLM_TEMPERATURE = 0.1    # near-deterministic sampling (Mistral default: 0.8)

# ── Ollama Client (real HTTP timeout via httpx, not silently-ignored options key) ─
_ollama_client = OllamaClient(timeout=GENERATION_TIMEOUT)


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class QAIConnectionError(Exception):
    """Raised when Ollama is not running or not reachable."""
    pass


class QAIModelError(Exception):
    """Raised when the required Ollama model is not available."""
    pass


class QAIKnowledgeBaseError(Exception):
    """Raised when ChromaDB is missing, empty, or corrupt."""
    pass


# ── Agent ──────────────────────────────────────────────────────────────────────

class QAIAgent:
    """
    Core agent that connects to Ollama (LLM) and ChromaDB (RAG knowledge base).
    Provides knowledge retrieval and LLM generation capabilities.

    Raises:
        QAIConnectionError: If Ollama is not running.
        QAIModelError: If the required model is not pulled.
        QAIKnowledgeBaseError: If ChromaDB is missing or empty.
    """

    def __init__(self):
        self.vector_store = None
        self.embeddings = None
        self._load_knowledge_base()
        self._check_ollama()

    def _load_knowledge_base(self):
        """
        Load the ChromaDB vector store from disk.

        Raises:
            QAIKnowledgeBaseError: If chroma_db/ is missing or empty.
        """
        if not CHROMA_DIR.exists():
            msg = (
                "\n❌ Knowledge base not found!\n\n"
                f"   Expected: {CHROMA_DIR}\n\n"
                "   Build it with:\n"
                "     python src/ingest.py\n\n"
                "   This will take 5-10 minutes on first run."
            )
            logger.error(f"ChromaDB directory not found: {CHROMA_DIR}")
            raise QAIKnowledgeBaseError(msg)

        logger.info("Loading knowledge base from ChromaDB...")
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
            )
            self.vector_store = Chroma(
                persist_directory=str(CHROMA_DIR),
                embedding_function=self.embeddings,
                collection_name="qai_knowledge_base",
            )
            count = self.vector_store._collection.count()
            if count == 0:
                msg = (
                    "\n❌ Knowledge base is empty!\n\n"
                    "   ChromaDB exists but contains no chunks.\n\n"
                    "   Add files to knowledge_base/ then run:\n"
                    "     python src/ingest.py"
                )
                logger.error("ChromaDB collection is empty (0 chunks)")
                raise QAIKnowledgeBaseError(msg)

            logger.info(f"Knowledge base loaded: {count} chunks")

        except QAIKnowledgeBaseError:
            raise
        except Exception as e:
            msg = (
                f"\n❌ Knowledge base failed to load!\n\n"
                f"   Error: {e}\n\n"
                "   Try rebuilding it:\n"
                "     python src/ingest.py"
            )
            logger.error(f"ChromaDB load failed: {e}")
            raise QAIKnowledgeBaseError(msg)

    def _check_ollama(self):
        """
        Verify Ollama is running and the required model is available.

        Raises:
            QAIConnectionError: If Ollama is not running.
            QAIModelError: If the required model is not pulled.
        """
        try:
            models_response = ollama.list()
            available = [m["name"] for m in models_response.get("models", [])]
        except Exception as e:
            msg = (
                "\n❌ Ollama is not running!\n\n"
                "   Start Ollama with:\n"
                "     ollama serve\n\n"
                "   Then pull the model:\n"
                f"     ollama pull {OLLAMA_MODEL}\n\n"
                "   Install Ollama: https://ollama.ai"
            )
            logger.error(f"Ollama connection failed: {e}")
            raise QAIConnectionError(msg)

        if not any(OLLAMA_MODEL in m for m in available):
            available_str = ", ".join(available) if available else "none"
            msg = (
                f"\n❌ Model '{OLLAMA_MODEL}' not found in Ollama!\n\n"
                f"   Pull it with:\n"
                f"     ollama pull {OLLAMA_MODEL}\n\n"
                f"   Models available on your system: {available_str}"
            )
            logger.error(f"Model '{OLLAMA_MODEL}' not found. Available: {available_str}")
            raise QAIModelError(msg)

        logger.info(f"Ollama ready — model: {OLLAMA_MODEL}")

    def retrieve_knowledge(self, query: str, k: int = TOP_K_RESULTS) -> list:
        """
        Retrieve relevant knowledge chunks from ChromaDB.

        Args:
            query: The search query string.
            k: Number of chunks to retrieve. Default: TOP_K_RESULTS.

        Returns:
            List of LangChain Document objects with page_content and metadata.
        """
        logger.debug(f"RAG query (k={k}): {query[:80]}...")
        results = self.vector_store.similarity_search(query, k=k)
        logger.debug(f"Retrieved {len(results)} chunks")
        return results

    def format_knowledge_context(self, chunks: list) -> str:
        """
        Format retrieved chunks into a context string for the LLM prompt.

        Args:
            chunks: List of Document objects from retrieve_knowledge().

        Returns:
            Formatted string with source headers and content.
        """
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            category = chunk.metadata.get("category", "General")
            filename = chunk.metadata.get("filename", "Unknown")
            context_parts.append(
                f"[Source {i} — {category}: {filename}]\n{chunk.page_content}"
            )
        return "\n\n---\n\n".join(context_parts)

    def ask(self, prompt: str, system_prompt: str = None) -> str:
        """
        Send a prompt to Ollama and return the generated response.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt for persona/role.

        Returns:
            The LLM response string.

        Raises:
            QAIConnectionError: If Ollama becomes unavailable during generation.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Sending prompt to Ollama ({len(prompt)} chars)...")
        try:
            response = _ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                options={
                    "num_ctx":     LLM_NUM_CTX,
                    "num_predict": LLM_NUM_PREDICT,
                    "temperature": LLM_TEMPERATURE,
                },
            )
            content = response["message"]["content"]
            logger.debug(f"Response received ({len(content)} chars)")
            return content
        except Exception as e:
            msg = (
                f"\n❌ Generation failed!\n\n"
                f"   Error: {e}\n\n"
                "   Make sure Ollama is still running:\n"
                "     ollama serve"
            )
            logger.error(f"Ollama generation failed: {e}")
            raise QAIConnectionError(msg)

    def ask_streaming(self, prompt: str, system_prompt: str = None):
        """
        Stream a prompt to Ollama, yielding text chunks as they arrive.

        Enables real-time display of LLM output while generation is in progress.
        Uses the same model parameters as ask() for consistency.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt for persona/role.

        Yields:
            str: Incremental content chunks from the LLM.

        Raises:
            QAIConnectionError: If Ollama becomes unavailable during generation.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Streaming prompt to Ollama ({len(prompt)} chars)...")
        try:
            stream = _ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                stream=True,
                options={
                    "num_ctx":     LLM_NUM_CTX,
                    "num_predict": LLM_NUM_PREDICT,
                    "temperature": LLM_TEMPERATURE,
                },
            )
            for chunk in stream:
                content = chunk["message"]["content"]
                if content:
                    yield content
        except Exception as e:
            msg = (
                f"\n❌ Generation failed!\n\n"
                f"   Error: {e}\n\n"
                "   Make sure Ollama is still running:\n"
                "     ollama serve"
            )
            logger.error(f"Ollama streaming generation failed: {e}")
            raise QAIConnectionError(msg)

    def ask_with_rag(self, query: str, system_prompt: str = None) -> tuple:
        """
        Answer a query using RAG — retrieve relevant knowledge first,
        then generate a response grounded in the retrieved context.

        Args:
            query: The user query string.
            system_prompt: Optional system prompt for persona/role.

        Returns:
            Tuple of (response_str, sources_list).
        """
        chunks = self.retrieve_knowledge(query)
        context = self.format_knowledge_context(chunks)

        rag_prompt = f"""Use the following QA knowledge base excerpts to inform your response.
Always base your recommendations on established QA methodologies and best practices.

KNOWLEDGE BASE CONTEXT:
{context}

USER QUERY:
{query}
"""
        response = self.ask(rag_prompt, system_prompt=system_prompt)

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
