"""Embedding and index worker.

Embeds documents' chunks in batches (with an embedding cache), then bulk-inserts
them into PostgreSQL. Only chunks that changed are (re)embedded — the pipeline
deletes the previous version's chunks and re-embeds the new version's chunks.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.config.settings import settings
from basechatt.database.models import DocumentChunk, ProcessingStatus
from basechatt.database.repositories import DocumentVersionRepository
from basechatt.llm.factory import get_embedding_provider
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.workers.indexing")


class EmbeddingCache:
    """Redis-backed embedding cache keyed by text hash.

    Falls back to an in-memory dict when Redis is unavailable.
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._mem: dict[str, list[float]] = {}

    async def _ensure_redis(self) -> aioredis.Redis | None:
        if not settings.use_redis:
            return None
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(settings.redis_url)
                await self._redis.ping()
            except Exception:  # noqa: BLE001
                self._redis = None
                logger.warning("Redis unavailable; using in-memory embedding cache")
        return self._redis

    async def get(self, key: str) -> list[float] | None:
        if key in self._mem:
            return self._mem[key]
        r = await self._ensure_redis()
        if r is not None:
            raw = await r.get(key)
            if raw:
                import json

                try:
                    vec = json.loads(raw)
                except Exception:  # noqa: BLE001
                    vec = None
                if vec:
                    self._mem[key] = vec
                    return vec
        return None

    async def set(self, key: str, vec: list[float]) -> None:
        self._mem[key] = vec
        r = await self._ensure_redis()
        if r is not None:
            import contextlib
            import json

            with contextlib.suppress(Exception):
                await r.set(key, json.dumps(vec), ex=settings.embedding_cache_ttl)


_cache = EmbeddingCache()


async def embed_and_index_version(
    session: AsyncSession,
    version_id: str,
) -> int:
    """Embed and persist all chunks of a version. Returns chunk count."""
    version_repo = DocumentVersionRepository(session)
    version = await version_repo.get(version_id)
    if version is None:
        return 0

    # Fetch existing chunks for this version.
    stmt = select(DocumentChunk).where(DocumentChunk.version_id == version_id)
    res = await session.execute(stmt)
    chunks = list(res.scalars().all())
    if not chunks:
        await version_repo.set_status(version_id, ProcessingStatus.COMPLETED)
        return 0

    provider = get_embedding_provider()

    # Get already-embedded chunks (from cache) and embed the rest in batches.
    pending: list[DocumentChunk] = []
    to_embed: list[str] = []

    for chunk in chunks:
        key = provider.cache_key(chunk.text)
        vec = await _cache.get(key)
        if vec is not None:
            chunk.embedding = vec
        else:
            pending.append(chunk)
            to_embed.append(chunk.text)

    if to_embed:
        batch_size = settings.embedding_batch_size
        for i in range(0, len(to_embed), batch_size):
            batch_texts = to_embed[i : i + batch_size]
            batch_chunks = pending[i : i + batch_size]
            try:
                vectors = await provider.embed_batch(batch_texts)
            except Exception as e:  # noqa: BLE001
                logger.error("embedding batch failed for version %s: %s", version_id, e)
                await version_repo.set_status(version_id, ProcessingStatus.FAILED)
                return 0
            for chunk, vec in zip(batch_chunks, vectors, strict=True):
                chunk.embedding = vec
                await _cache.set(provider.cache_key(chunk.text), vec)

    await session.flush()
    await version_repo.set_status(version_id, ProcessingStatus.COMPLETED)
    logger.info("indexed %d chunks for version %s", len(chunks), version_id)
    return len(chunks)
