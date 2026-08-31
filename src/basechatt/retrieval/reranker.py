"""Result reranking.

Two strategies:

* ``deterministic`` (default): scores each hit on authority level, freshness
  (recency of publication) and lexical overlap with the query. No model cost,
  fully reproducible, handles Groq's lack of a cross-encoder.
* ``llm``: optionally uses the chat model to judge relevance (bound by the
  batching budget). Used only when explicitly enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from basechatt.config.settings import settings
from basechatt.observability.logging import get_logger
from basechatt.retrieval.fusion import FusedResult

logger = get_logger("basechatt.retrieval.reranker")

AUTHORITY_WEIGHT = {
    "PRIMARY_REGULATOR": 1.0,
    "PRIMARY_EXCHANGE": 0.95,
    "COMPANY_PRIMARY": 0.85,
    "REGULATOR": 0.9,
    "GOVERNMENT": 0.7,
    "THIRD_PARTY": 0.5,
}

# Freshness half-life: a document loses half its bonus significance beyond
# ~18 months old.
FRESHNESS_HALF_LIFE_SECONDS = 18 * 30 * 24 * 3600


@dataclass
class ScoredResult:
    chunk: Any
    score: float
    reasons: dict[str, float] = field(default_factory=dict)


async def rerank(
    fused: list[FusedResult],
    query: str,
    top_k: int,
    strategy: str | None = None,
    session=None,
) -> list[ScoredResult]:
    strat = (strategy or settings.reranker_strategy).lower()
    if strat == "llm" and session is not None:
        return await _rerank_llm(fused, query, top_k, session)
    return _rerank_deterministic(fused, query, top_k)


def _rerank_deterministic(
    fused: list[FusedResult], query: str, top_k: int
) -> list[ScoredResult]:
    q_terms = set(_tokens(query.lower()))
    today = datetime.now(UTC)

    scored: list[ScoredResult] = []
    for item in fused:
        meta = item.chunk._retrieval or {}
        authority = meta.get("authority_level", "THIRD_PARTY")
        authority_bonus = AUTHORITY_WEIGHT.get(authority, 0.4)

        published_at = meta.get("published_at")
        freshness = 0.0
        if isinstance(published_at, datetime):
            age = (today - published_at.replace(tzinfo=UTC)).total_seconds()
            freshness = 0.5 ** (max(age, 0) / FRESHNESS_HALF_LIFE_SECONDS)

        # Lexical overlap of the chunk's beginning with the query.
        chunk_terms = set(_tokens(item.chunk.text.lower())) & q_terms
        overlap = len(q_terms & chunk_terms) / max(len(q_terms), 1)

        score = (
            0.45 * item.score
            + 0.30 * authority_bonus
            + 0.15 * freshness
            + 0.10 * overlap
        )
        scored.append(
            ScoredResult(
                chunk=item.chunk,
                score=score,
                reasons={
                    "fusion": round(item.score, 4),
                    "authority": round(authority_bonus, 3),
                    "freshness": round(freshness, 3),
                    "lexical_overlap": round(overlap, 3),
                },
            )
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]


async def _rerank_llm(
    fused: list[FusedResult], query: str, top_k: int, session
):
    from basechatt.llm.factory import get_llm_provider

    provider = get_llm_provider()
    batch = fused[: settings.reranker_top_n]
    results: list[ScoredResult] = []
    for item in batch:
        texts = item.chunk.text[: settings.max_evidence_chars]
        system = "You are a relevance judge. Reply with a single number 0-10."
        prompt = (
            "Score how relevant this excerpt is to the user's research query "
            "on a scale of 0-10. Reply with only a number.\n\n"
            f"QUERY: {query}\n\nEXCERPT:\n{texts}"
        )
        try:
            resp = await provider.chat(system, prompt, max_tokens=5, temperature=0.0)
            value = _parse_score(resp.text)
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM rerank failed for a hit: %s", e)
            value = 5.0
        results.append(
            ScoredResult(
                chunk=item.chunk, score=value / 10.0, reasons={"llm_score": value}
            )
        )
    # Keep the LLM-only ordering for the (small) batch, then interleave the rest
    # by their fused score to avoid dropping strong evidence.
    results.sort(key=lambda r: r.score, reverse=True)
    rest = fused[len(batch):]
    rest_scored = [
        ScoredResult(chunk=i.chunk, score=i.score, reasons={"fusion": i.score})
        for i in rest
    ]
    combined = results + rest_scored
    combined.sort(key=lambda r: r.score, reverse=True)
    return combined[:top_k]


def _parse_score(text: str) -> float:
    import re

    m = re.search(r"(\d+(?:\.\d+)?)", text or "")
    if not m:
        return 5.0
    val = float(m.group(1))
    return max(0.0, min(10.0, val))


def _tokens(s: str) -> list[str]:
    import re

    return [t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2]
