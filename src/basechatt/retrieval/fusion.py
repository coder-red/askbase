"""Reciprocal Rank Fusion.

Merges ranked lists from heterogeneous retriever families (dense vector scores,
dt-lexical tfidf scores, FTS ranks) into a single ordering without needing to
calibrate their score distributions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RRF_K = 60.0


@dataclass
class FusedResult:
    chunk_id: str
    document_id: str
    score: float
    ranks: dict[str, int]
    chunk: Any = None


def rrf_fuse(
    rank_lists: dict[str, list[Any]],
    weights: dict[str, float] | None = None,
    k: float = RRF_K,
) -> list[FusedResult]:
    """Fuse multiple ranked lists of items that expose a ``document_id``-like
    key (via ``_retrieval``) plus a ``chunk.id``.

    ``rank_lists`` maps a retriever name to its ordered results (objects with
    ``.chunk.id`` and ``.chunk._retrieval['document_id']``).

    Returns fused results sorted by fused score descending.
    """
    weights = weights or {name: 1.0 for name in rank_lists}
    accumulator: dict[str, dict] = {}

    for name, items in rank_lists.items():
        w = weights.get(name, 1.0)
        for rank, item in enumerate(items, start=1):
            chunk = item.chunk
            cid = chunk.id
            if cid not in accumulator:
                acc = accumulator[cid] = {
                    "score": 0.0,
                    "ranks": {},
                    "chunk": chunk,
                    "document_id": chunk._retrieval.get("document_id", ""),
                }
            else:
                acc = accumulator[cid]
            acc["score"] += w * (1.0 / (k + rank))
            acc["ranks"][name] = rank

    fused = [
        FusedResult(
            chunk_id=cid,
            document_id=acc["document_id"],
            score=acc["score"],
            ranks=acc["ranks"],
            chunk=acc["chunk"],
        )
        for cid, acc in accumulator.items()
    ]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused
