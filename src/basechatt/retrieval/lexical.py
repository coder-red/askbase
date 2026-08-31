"""Lexical (full-text) retrieval over PostgreSQL FTS."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.database.models import DocumentChunk
from basechatt.database.repositories import ChunkRepository
from basechatt.retrieval.filters import RetrievalFilters


@dataclass
class LexicalResult:
    chunk: DocumentChunk
    score: float

    @property
    def document_id(self) -> str:
        return self.chunk._retrieval.get("document_id", "")


async def lexical_search(
    session: AsyncSession,
    query: str,
    top_k: int = 20,
    filters: RetrievalFilters | None = None,
) -> list[LexicalResult]:
    filters = filters or RetrievalFilters()
    repo = ChunkRepository(session)
    rows = await repo.lexical_search(
        query,
        limit=top_k,
        company_id=filters.company_id,
        document_type=filters.document_type,
        source_code=filters.source_code,
        before=filters.before,
        after=filters.after,
        min_authority=filters.authority_level,
        required_term=filters.text,
    )
    return [LexicalResult(chunk=chunk, score=score) for chunk, score in rows]
