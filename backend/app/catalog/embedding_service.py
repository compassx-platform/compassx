"""LLM-connection-based embedding service for catalog semantic search.

Instead of a dedicated Voyage AI key, the system reuses the existing
LLMConnection infrastructure.  The administrator marks one LLM connection
with ``use_for_embedding = True``; that connection is used to generate
1536-dimensional embedding vectors.

Supported providers and their embedding endpoints:
  - openai / compatible / ollama: OpenAI Embeddings API
  - azure:                        Azure OpenAI Embeddings API
  - litellm:                      litellm.embedding()
  - gemini:                       Google genai embed_content()
  - anthropic:                    ❌ not supported (Anthropic has no embeddings API)

Configure in the UI:
  Agents → Connections → LLM Connections → ✓ "Use for Embeddings"

Dimension note:
  The vector_db.assets.embedding column is vector(1536).
  Your chosen embedding model must produce 1536-dim vectors.
  Recommended models:
    OpenAI   → text-embedding-3-small  (1536 dims)
    OpenAI   → text-embedding-ada-002  (1536 dims)
    Ollama   → nomic-embed-text        (768 dims — will fail dimension check)
    Azure    → text-embedding-3-small  (1536 dims)
    LiteLLM  → any provider embedding model via LiteLLM routing
    Gemini   → text-embedding-004      (768 dims — will fail dimension check)

  If you must use a 768-dim model, contact your administrator to run
  the alter-column migration to resize the vector column.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

EXPECTED_DIM = 1536  # matches vector_db.assets.embedding vector(1536)


def compose_embedding_text(
    object_type: str,
    object_name: str,
    description: str | None,
    content_summary: str | None,
) -> str:
    """Build the canonical embedding text string for a catalog object.

    - table / foreign_table: ``{name} — {description}. Columns: {summary}``
    - other types:           ``{name} — {description}``
    """
    if object_type in ("table", "foreign_table"):
        base = f"{object_name} — {description}" if description else object_name
        return f"{base}. Columns: {content_summary}" if content_summary else base
    return f"{object_name} — {description}" if description else object_name


def _get_embedding_connection():
    """Return the LLMConnection marked use_for_embedding, or None."""
    try:
        from app.database import AccountSessionLocal
        from app.models.agents import LLMConnection

        db = AccountSessionLocal()
        try:
            return db.query(LLMConnection).filter(
                LLMConnection.use_for_embedding == True  # noqa: E712
            ).first()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Could not query embedding LLM connection: %s", exc)
        return None


def _embed_openai(conn, text: str) -> Optional[list[float]]:
    """Embed via OpenAI / Ollama / compatible provider (sync)."""
    try:
        import openai
        import httpx
    except ImportError:
        logger.error("openai package not installed — run: pip install openai")
        return None

    from app.services.encryption import decrypt_field

    api_key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else "ollama"
    http_client = httpx.Client(trust_env=False)
    client = openai.OpenAI(
        api_key=api_key,
        base_url=conn.base_url or None,
        timeout=conn.timeout_s,
        http_client=http_client,
    )
    try:
        resp = client.embeddings.create(model=conn.model_name, input=text)
        return resp.data[0].embedding
    finally:
        client.close()
        http_client.close()


def _embed_azure(conn, text: str) -> Optional[list[float]]:
    """Embed via Azure OpenAI."""
    try:
        import openai
        import httpx
    except ImportError:
        logger.error("openai package not installed — run: pip install openai")
        return None

    from app.services.encryption import decrypt_field

    cfg = conn.config or {}
    api_key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else ""
    http_client = httpx.Client(trust_env=False)
    client = openai.AzureOpenAI(
        api_key=api_key,
        azure_endpoint=conn.base_url or "",
        api_version=cfg.get("api_version", "2024-02-01"),
        timeout=conn.timeout_s,
        http_client=http_client,
    )
    deployment = cfg.get("deployment_name", conn.model_name)
    try:
        resp = client.embeddings.create(model=deployment, input=text)
        return resp.data[0].embedding
    finally:
        client.close()
        http_client.close()


def _embed_litellm(conn, text: str) -> Optional[list[float]]:
    """Embed via LiteLLM (routes to 100+ providers)."""
    try:
        import litellm
    except ImportError:
        logger.error("litellm package not installed — run: pip install litellm")
        return None

    from app.services.encryption import decrypt_field

    api_key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else None
    cfg = conn.config or {}
    kwargs: dict = {"model": conn.model_name, "input": [text], **cfg}
    if api_key:
        kwargs["api_key"] = api_key
    if conn.base_url:
        kwargs["api_base"] = conn.base_url

    resp = litellm.embedding(**kwargs)
    return resp.data[0]["embedding"]


def _embed_gemini(conn, text: str) -> Optional[list[float]]:
    """Embed via Google Gemini (embed_content API)."""
    try:
        from google import genai
    except ImportError:
        logger.error("google-genai not installed — run: pip install google-genai")
        return None

    from app.services.encryption import decrypt_field
    import asyncio

    api_key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else ""
    client = genai.Client(api_key=api_key)

    async def _call():
        result = await client.aio.models.embed_content(
            model=conn.model_name,
            contents=text,
        )
        return result.embedding.values

    return asyncio.run(_call())


def get_embedding(text: str) -> Optional[list[float]]:
    """Generate a 1536-dim embedding vector using the designated LLM connection.

    Returns None if:
    - No connection is marked ``use_for_embedding``
    - The provider doesn't support embeddings (e.g. Anthropic)
    - The returned vector has the wrong dimension
    - Any API error occurs
    """
    conn = _get_embedding_connection()
    if conn is None:
        logger.warning(
            "No LLM connection is marked 'use_for_embedding'. "
            "Go to Agents → Connections → LLM Connections and tick "
            "'Use for Embeddings' on an embedding-capable connection."
        )
        return None

    from app.models.agents import LLMProvider

    try:
        provider = conn.provider
        if provider in (LLMProvider.openai, LLMProvider.ollama, LLMProvider.compatible):
            vector = _embed_openai(conn, text)
        elif provider == LLMProvider.azure:
            vector = _embed_azure(conn, text)
        elif provider == LLMProvider.litellm:
            vector = _embed_litellm(conn, text)
        elif provider == LLMProvider.gemini:
            vector = _embed_gemini(conn, text)
        elif provider == LLMProvider.anthropic:
            logger.error(
                "Anthropic does not offer an embeddings API. "
                "Select a different connection for embeddings (e.g. OpenAI, Ollama, LiteLLM)."
            )
            return None
        else:
            logger.error("Unsupported provider for embeddings: %s", provider)
            return None
    except Exception as exc:
        logger.error(
            "Embedding call failed (connection=%s, provider=%s): %s",
            conn.name,
            conn.provider,
            exc,
        )
        return None

    if vector is None:
        return None

    if len(vector) != EXPECTED_DIM:
        logger.error(
            "Embedding model '%s' returned %d dimensions, expected %d. "
            "Use a model that produces %d-dim vectors (e.g. text-embedding-3-small).",
            conn.model_name,
            len(vector),
            EXPECTED_DIM,
            EXPECTED_DIM,
        )
        return None

    return vector
