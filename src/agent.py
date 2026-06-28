"""
QAI Consultant — Core Agent
Connects to Mistral API (LLM) and Pinecone (knowledge base) and provides RAG query functionality.
"""

import os
from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from pinecone import Pinecone
from logger import get_logger, setup_logging
from mistralai.client import Mistral
from openai import OpenAI

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


# ── LLM Client Adapter ─────────────────────────────────────────────────────────

class LLMClient:
    """
    Thin adapter: Mistral API primary, OpenRouter fallback.
    chat() and chat(stream=True) have identical call sites regardless of provider.
    """

    def __init__(self, mistral_api_key: str, openrouter_api_key: str):
        self._mistral = Mistral(api_key=mistral_api_key)
        self._openrouter = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key,
        )

    def chat(self, messages: list, stream: bool = False):
        """
        Send messages to Mistral; fall back to OpenRouter on any error.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            stream: If True, returns a generator yielding text chunks.

        Returns:
            str (stream=False) or generator of str (stream=True).

        Raises:
            QAIConnectionError: If both providers fail.
        """
        if stream:
            return self._chat_stream(messages)
        return self._chat_once(messages)

    def _chat_once(self, messages: list) -> str:
        try:
            response = self._mistral.chat.complete(
                model=MISTRAL_MODEL,
                messages=messages,
                max_tokens=LLM_NUM_PREDICT,
                temperature=LLM_TEMPERATURE,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Mistral failed ({e}), falling back to OpenRouter")

        try:
            response = self._openrouter.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                max_tokens=LLM_NUM_PREDICT,
                temperature=LLM_TEMPERATURE,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise QAIConnectionError(
                f"\n❌ LLM generation failed!\n\n"
                f"   Both Mistral API and OpenRouter are unavailable.\n"
                f"   Last error: {e}\n\n"
                "   Check your API keys in .env or Streamlit secrets."
            )

    def _chat_stream(self, messages: list):
        try:
            stream = self._mistral.chat.stream(
                model=MISTRAL_MODEL,
                messages=messages,
                max_tokens=LLM_NUM_PREDICT,
                temperature=LLM_TEMPERATURE,
            )
            for event in stream:
                content = event.data.choices[0].delta.content
                if content:
                    yield content
            return
        except Exception as e:
            logger.warning(f"Mistral streaming failed ({e}), falling back to OpenRouter")

        try:
            stream = self._openrouter.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                max_tokens=LLM_NUM_PREDICT,
                temperature=LLM_TEMPERATURE,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            raise QAIConnectionError(
                f"\n❌ LLM streaming failed!\n\n"
                f"   Both Mistral API and OpenRouter are unavailable.\n"
                f"   Last error: {e}\n\n"
                "   Check your API keys in .env or Streamlit secrets."
            )


# ── Config ─────────────────────────────────────────────────────────────────────
MISTRAL_MODEL    = "mistral-small-latest"
OPENROUTER_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_RESULTS    = 5
RAG_K_GENERATION = 5        # chunks for Risk Register + Test Strategy prompts
PINECONE_NAMESPACE = "knowledge-base"   # must match PINECONE_NAMESPACE in ingest.py

# ── LLM Generation Parameters ──────────────────────────────────────────────────
LLM_NUM_PREDICT = 1500      # max output tokens — prevents runaway generation
LLM_TEMPERATURE = 0.1       # near-deterministic


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class QAIConnectionError(Exception):
    """Raised when LLM API keys are missing or both providers fail."""
    pass


class QAIModelError(Exception):
    """Legacy — no longer raised by v2.0 agent. Kept for import compatibility."""
    pass


class QAIKnowledgeBaseError(Exception):
    """Raised when Pinecone index is empty, unreachable, or API key is missing."""
    pass


# ── Agent ──────────────────────────────────────────────────────────────────────

class QAIAgent:
    """
    Core agent that connects to Mistral API (LLM) and Pinecone (RAG knowledge base).
    Provides knowledge retrieval and LLM generation capabilities.

    Raises:
        QAIConnectionError: If LLM API keys are missing or both providers fail.
        QAIKnowledgeBaseError: If Pinecone index is empty or unreachable.
    """

    def __init__(self):
        self._index = None
        self.embeddings = None
        self._llm_client = None
        self._load_knowledge_base()
        self._check_llm()

    def _load_knowledge_base(self):
        """
        Connect to Pinecone index and verify it has vectors.

        Raises:
            QAIKnowledgeBaseError: If Pinecone is unreachable or index is empty.
        """
        try:
            api_key = _get_secret("PINECONE_API_KEY")
            index_name = _get_secret("PINECONE_INDEX_NAME")
            pc = Pinecone(api_key=api_key)
            self._index = pc.Index(index_name)
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
            )
            stats = self._index.describe_index_stats()
            count = stats.total_vector_count
            if count == 0:
                msg = (
                    "\n❌ Knowledge base is empty!\n\n"
                    "   Pinecone index exists but contains no vectors.\n\n"
                    "   Build it with:\n"
                    "     python src/ingest.py"
                )
                logger.error("Pinecone index is empty (0 vectors)")
                raise QAIKnowledgeBaseError(msg)
            logger.info(f"Pinecone knowledge base loaded: {count} vectors in index '{index_name}'")
        except QAIKnowledgeBaseError:
            raise
        except Exception as e:
            msg = (
                f"\n❌ Knowledge base failed to load!\n\n"
                f"   Error: {e}\n\n"
                "   Check your PINECONE_API_KEY and PINECONE_INDEX_NAME,\n"
                "   then rebuild with:\n"
                "     python src/ingest.py"
            )
            logger.error(f"Pinecone load failed: {e}")
            raise QAIKnowledgeBaseError(msg)

    def _check_llm(self):
        """Initialise LLMClient — validates API keys are present."""
        try:
            self._llm_client = LLMClient(
                mistral_api_key=_get_secret("MISTRAL_API_KEY"),
                openrouter_api_key=_get_secret("OPENROUTER_API_KEY"),
            )
            logger.info("LLMClient ready — Mistral primary, OpenRouter fallback")
        except ValueError as e:
            raise QAIConnectionError(str(e))

    def retrieve_knowledge(self, query: str, k: int = TOP_K_RESULTS) -> list:
        """
        Retrieve relevant knowledge chunks from Pinecone.

        Args:
            query: The search query string.
            k: Number of chunks to retrieve. Default: TOP_K_RESULTS.

        Returns:
            List of Document objects with page_content and metadata.
        """
        logger.debug(f"RAG query (k={k}): {query[:80]}...")
        try:
            query_embedding = self.embeddings.embed_query(query)
            results = self._index.query(
                vector=query_embedding,
                top_k=k,
                namespace=PINECONE_NAMESPACE,
                include_metadata=True,
            )
            chunks = [
                Document(
                    page_content=match.metadata.get("text", ""),
                    metadata={
                        "source": match.metadata.get("source", ""),
                        "category": match.metadata.get("category", ""),
                        "filename": match.metadata.get("filename", ""),
                    },
                )
                for match in results.matches
            ]
            logger.debug(f"Retrieved {len(chunks)} chunks")
            return chunks
        except Exception as exc:
            raise QAIKnowledgeBaseError(f"Knowledge base query failed: {exc}") from exc

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
        Send a prompt to the LLM and return the generated response.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt for persona/role.

        Returns:
            The LLM response string.

        Raises:
            QAIConnectionError: If both LLM providers fail.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Sending prompt to LLM ({len(prompt)} chars)...")
        content = self._llm_client.chat(messages)
        content = content or ""
        logger.debug(f"Response received ({len(content)} chars)")
        return content

    def ask_streaming(self, prompt: str, system_prompt: str = None):
        """
        Stream a prompt to the LLM, yielding text chunks as they arrive.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt for persona/role.

        Yields:
            str: Incremental content chunks from the LLM.

        Raises:
            QAIConnectionError: If both LLM providers fail.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Streaming prompt to LLM ({len(prompt)} chars)...")
        yield from self._llm_client.chat(messages, stream=True)

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
