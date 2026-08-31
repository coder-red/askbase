"""Dense (vector) retrieval over pgvector.

Uses cosine similarity against the latest version of each document, with
optional metadata filters.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.database.models import DocumentChunk
from basechatt.database.repositories import ChunkRepository
from basechatt.llm.factory import get_embedding_provider
from basechatt.observability.logging import get_logger
from basechatt.retrieval.filters import RetrievalFilters

logger = get_logger("basechatt.retrieval.dense")


@dataclass
class DenseResult:
    chunk: DocumentChunk
    score: float

    @property
    def document_id(self) -> str:
        return self.chunk._retrieval.get("document_id", "")


async def dense_search(
    session: AsyncSession,
    query: str,
    top_k: int = 20,
    filters: RetrievalFilters | None = None,
    query_embedding: list[float] | None = None,
) -> list[DenseResult]:
    """Return top-k dense results for a query."""
    filters = filters or RetrievalFilters()
    if query_embedding is None:
        provider = get_embedding_provider()
        query_embedding = await provider.embed_text(query)

    repo = ChunkRepository(session)
    rows = await repo.vector_search(
        query_embedding,
        limit=top_k,
        company_id=filters.company_id or (None),
        document_type=filters.document_type,
        source_code=filters.source_code,
        before=filters.before,
        after=filters.after,
        min_authority=filters.authority_level,
    )
    return [DenseResult(chunk=chunk, score=score) for chunk, score in rows]
