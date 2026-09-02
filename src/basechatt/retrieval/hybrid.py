"""Hybrid retrieval orchestrator.

Combines dense (pgvector) and lexical (PostgreSQL FTS) retrieval, fuses the
rankings with Reciprocal Rank Fusion, applies deterministic/LLM reranking, and
applies temporal constraints parsed from the query.

The router decides whether temporal filtering should be applied (an explicit
time span) versus a "latest" intent (sort by recency) versus an open full-range
search.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.config.settings import settings
from basechatt.observability.logging import get_logger
from basechatt.retrieval.dense import dense_search
from basechatt.retrieval.filters import RetrievalFilters
from basechatt.retrieval.fusion import rrf_fuse
from basechatt.retrieval.lexical import lexical_search
from basechatt.retrieval.reranker import ScoredResult, rerank
from basechatt.retrieval.temporal import TemporalSpec, parse_temporal

logger = get_logger("basechatt.retrieval.hybrid")


@dataclass
class HybridResponse:
    query: str
    results: list[ScoredResult]
    temporal: TemporalSpec
    sources: list[str]
    metadata: dict


async def hybrid_search(
    session: AsyncSession,
    query: str,
    top_k: int | None = None,
    filters: RetrievalFilters | None = None,
    query_embedding: list[float] | None = None,
) -> HybridResponse:
    cfg = settings
    top_k = top_k or cfg.reranker_top_n
    filters = filters or RetrievalFilters()

    # 1. Parse temporal intent from the query.
    temporal = parse_temporal(query)

    # 2. Apply temporal to filters.
    effective = _apply_temporal(filters, temporal)

    # 3. Dense + lexical retrieval.
    dense_k = int(top_k * cfg.semantic_weight)
    lex_k = int(top_k * cfg.lexical_weight)

    dense = await dense_search(
        session, query, top_k=dense_k, filters=effective, query_embedding=query_embedding
    )
    lexical = await lexical_search(session, query, top_k=lex_k, filters=effective)

    # 4. Fuse.
    fused = rrf_fuse(
        {"dense": dense, "lexical": lexical},
        weights={"dense": cfg.semantic_weight, "lexical": cfg.lexical_weight},
    )

    # 5. Rerank.
    scored = await rerank(fused, query, top_k, session=session)

    # 6. Filter by minimum quality threshold.
    min_score = cfg.min_retrieval_score
    scored = [r for r in scored if r.score >= min_score]

    sources = list(dict.fromkeys(r.chunk._retrieval.get("source_name", "") for r in scored))
    return HybridResponse(
        query=query,
        results=scored,
        temporal=temporal,
        sources=[s for s in sources if s],
        metadata={
            "dense_candidates": len(dense),
            "lexical_candidates": len(lexical),
            "fused_candidates": len(fused),
            "reranked": len(scored),
        },
    )


def _apply_temporal(filters: RetrievalFilters, temporal: TemporalSpec) -> RetrievalFilters:
    if temporal.mode == "all":
        return filters
    if temporal.mode == "latest":
        return filters.clone(before=None, after=None)
    return filters.clone(
        before=temporal.before if temporal.before else filters.before,
        after=temporal.after if temporal.after else filters.after,
    )
