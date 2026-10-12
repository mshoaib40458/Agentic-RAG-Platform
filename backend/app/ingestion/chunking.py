"""Chunking via LlamaIndex's ``SentenceSplitter`` (SRS FR-010).

Documents are chunked page-by-page so each chunk retains its source page number
for citation. A minimal fallback splitter keeps ingestion working if LlamaIndex
is unavailable at runtime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.ingestion.extractors import ExtractedDocument

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Chunk:
    index: int
    text: str
    page: int | None
    token_count: int | None


def _estimate_tokens(text: str) -> int:
    # Approximation: whitespace-delimited words. Adequate for analytics, not billing.
    return len(text.split())


def _split_with_llamaindex(texts_pages: list[tuple[int | None, str]]) -> list[Chunk]:
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Document as LlamaDocument

    settings = get_settings()
    splitter = SentenceSplitter(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )

    chunks: list[Chunk] = []
    for page_number, text in texts_pages:
        if not text.strip():
            continue
        page_doc = LlamaDocument(text=text, metadata={"page": page_number})
        for node in splitter.get_nodes_from_documents([page_doc]):
            content = node.get_content().strip()
            if not content:
                continue
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=content,
                    page=page_number,
                    token_count=_estimate_tokens(content),
                )
            )
    return chunks


def _split_fallback(texts_pages: list[tuple[int | None, str]]) -> list[Chunk]:
    """Word-window splitter used only if LlamaIndex cannot be imported."""
    settings = get_settings()
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    step = max(size - overlap, 1)

    chunks: list[Chunk] = []
    for page_number, text in texts_pages:
        words = text.split()
        if not words:
            continue
        for start in range(0, len(words), step):
            window = words[start : start + size]
            if not window:
                break
            content = " ".join(window)
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=content,
                    page=page_number,
                    token_count=len(window),
                )
            )
    return chunks


def chunk_document(extracted: ExtractedDocument) -> list[Chunk]:
    texts_pages = [(page.page_number, page.text) for page in extracted.pages]
    try:
        return _split_with_llamaindex(texts_pages)
    except ImportError:
        logger.warning("llamaindex_unavailable_using_fallback_splitter")
        return _split_fallback(texts_pages)
