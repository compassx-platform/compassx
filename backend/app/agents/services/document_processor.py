"""Document processing pipeline: upload → parse → chunk → embed → pgvector.

Supported file types: PDF (.pdf), Word (.docx), Excel (.xlsx), CSV (.csv), JSON (.json), plain text (.txt, .md), Images (.png, .jpg, .jpeg, .webp, .gif, .svg).
"""

from __future__ import annotations

import io
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.agents import DocumentStatus, RagChunk, RagDocument

logger = logging.getLogger(__name__)

_CHUNK_CHARS = 2048    # ≈ 512 tokens at ~4 chars/token
_OVERLAP_CHARS = 200   # ≈ 50 tokens overlap
_EMBEDDING_DIM = 768
_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"

# Module-level model cache — loaded once on first use
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(_MODEL_NAME)
            logger.info("Loaded embedding model: %s", _MODEL_NAME)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. RAG embeddings will be zero vectors. "
                "Run: pip install sentence-transformers"
            )
    return _embedding_model


def embed_text(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings. Returns list of 768-dim float lists."""
    model = _get_embedding_model()
    if model is None:
        return [[0.0] * _EMBEDDING_DIM for _ in texts]
    return model.encode(texts, show_progress_bar=False).tolist()


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_CHARS, len(text))
        chunks.append(text[start:end])
        start += _CHUNK_CHARS - _OVERLAP_CHARS
    return [c for c in chunks if c.strip()]


def parse_document(content: bytes, mime_type: str, filename: str) -> str:
    """Extract plain text from a document."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if mime_type in ("text/plain", "text/markdown", "text/csv", "application/json") or ext in ("txt", "md", "csv", "json"):
        return content.decode("utf-8", errors="replace")

    if mime_type in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",) or ext in ("xlsx", "xls"):
        try:
            import pandas as pd
            df_dict = pd.read_excel(io.BytesIO(content), sheet_name=None)
            sheets_text = []
            for sheet_name, df in df_dict.items():
                sheets_text.append(f"--- Sheet: {sheet_name} ---\n" + df.to_csv(index=False))
            return "\n\n".join(sheets_text)
        except Exception:
            return content.decode("utf-8", errors="replace")

    if mime_type == "application/pdf" or ext == "pdf":
        try:
            import pypdf
            from app.nova.services.attachment_service import _post_process_pdf_text
            reader = pypdf.PdfReader(io.BytesIO(content))
            num_pages = len(reader.pages)
            pages_text = []
            page_summaries = []
            for idx, page in enumerate(reader.pages):
                p_text = ""
                try:
                    p_text = page.extract_text(extraction_mode="layout") or ""
                except Exception:
                    p_text = page.extract_text() or ""
                p_text = _post_process_pdf_text(p_text)
                first_line = next((line.strip() for line in p_text.splitlines() if line.strip() and not line.startswith("===")), f"Page {idx + 1}")
                page_summaries.append(f"  - Page {idx + 1} of {num_pages}: {first_line[:90]}")
                pages_text.append(f"=== Page {idx + 1} of {num_pages} ===\n" + p_text)
            outline = "Document Outline / Page Index:\n" + "\n".join(page_summaries)
            return f"[PDF Document: {filename} | Total Pages: {num_pages}]\n{outline}\n\n" + "\n\n".join(pages_text)
        except ImportError:
            raise RuntimeError("pypdf not installed. Run: pip install pypdf")

    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) or ext == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError("python-docx not installed. Run: pip install python-docx")

    if mime_type.startswith("image/") or ext in ("png", "jpg", "jpeg", "webp", "gif", "svg"):
        return f"[Image Document: {filename} ({mime_type or f'image/{ext}'}) | Size: {len(content)} bytes]\n[Visual image file attached to session]"

    raise ValueError(f"Unsupported file type: {mime_type or ext}")


def process_document(doc_id: int, content: bytes, mime_type: str, filename: str, db: Session) -> None:
    """Full processing pipeline — called as a background task.

    Updates rag_documents.status on completion or failure.
    """
    doc = db.query(RagDocument).filter(RagDocument.id == doc_id).first()
    if not doc:
        return

    try:
        # 1. Parse
        full_text = parse_document(content, mime_type, filename)
        if not full_text.strip():
            raise ValueError("Document appears to be empty or unreadable")

        # 2. Chunk
        chunks = chunk_text(full_text)
        if not chunks:
            raise ValueError("No text chunks extracted")

        # 3. Embed
        embeddings = embed_text(chunks)

        # 4. Store chunks with embeddings via raw SQL (pgvector syntax)
        for idx, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
            # Insert chunk row
            result = db.execute(
                text(
                    "INSERT INTO ai.rag_chunks (document_id, chunk_index, content) "
                    "VALUES (:doc_id, :idx, :content) RETURNING id"
                ),
                {"doc_id": doc_id, "idx": idx, "content": chunk_text_val},
            )
            chunk_id = result.scalar()

            # Update embedding (pgvector requires casting)
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            db.execute(
                text("UPDATE ai.rag_chunks SET embedding = CAST(:emb AS public.vector) WHERE id = :id"),
                {"emb": embedding_str, "id": chunk_id},
            )

        doc.status = DocumentStatus.ready
        doc.chunk_count = len(chunks)
        db.commit()

        logger.info("Successfully processed doc %s: %d chunks embedded", doc_id, len(chunks))

    except Exception as exc:
        logger.error("Document processing failed for doc %s: %s", doc_id, exc, exc_info=True)
        db.rollback()
        doc = db.query(RagDocument).filter(RagDocument.id == doc_id).first()
        if doc:
            doc.status = DocumentStatus.failed
            doc.error = str(exc)
            db.commit()


def search_documents(query: str, top_k: int, db: Session) -> list[dict[str, Any]]:
    """Semantic search over uploaded documents using pgvector cosine similarity."""
    model = _get_embedding_model()
    if model is None:
        return []

    query_embedding = embed_text([query])[0]
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    rows = db.execute(
        text("""
            SELECT rc.content, rc.chunk_index, rd.filename,
                   1 - (rc.embedding <=> CAST(:emb AS public.vector)) AS similarity
            FROM ai.rag_chunks rc
            JOIN ai.rag_documents rd ON rd.id = rc.document_id
            WHERE rd.status = 'ready'
            ORDER BY rc.embedding <=> CAST(:emb AS public.vector)
            LIMIT :top_k
        """),
        {"emb": embedding_str, "top_k": top_k},
    ).fetchall()

    return [
        {
            "content": row.content,
            "filename": row.filename,
            "chunk_index": row.chunk_index,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]
