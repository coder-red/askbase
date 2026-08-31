"""Re-embed every existing chunk with the active embedding provider (Jina).

Updates the pgvector ``embedding`` column in place so retrieval uses real
semantic vectors instead of the previous mock vectors. Safe to run anytime;
idempotent (it computes fresh vectors regardless of prior stored values).

Usage: python reembed_all.py
"""

import asyncio
import sys

from sqlalchemy import select, update, func

from basechatt.config.settings import settings
from basechatt.database.session import SessionLocal
from basechatt.database.models import DocumentChunk
from basechatt.llm.factory import get_embedding_provider


async def main() -> None:
    provider = get_embedding_provider()
    print(f"provider={type(provider).__name__} dim={provider.dim}")

    # Flush the Redis/in-memory embedding cache so stale (mock) vectors are not reused.
    from basechatt.workers.indexing import _cache

    _cache._mem.clear()
    r = await _cache._ensure_redis()
    if r is not None:
        try:
            await r.flushdb()
            print("flushed redis embedding cache")
        except Exception as e:  # noqa: BLE001
            print("redis flush skipped:", e)
    else:
        print("no redis; cleared in-memory cache")

    async with SessionLocal() as session:
        total = (
            await session.execute(
                select(func.count()).select_from(DocumentChunk)
            )
        ).scalar()
        stmt = select(
            DocumentChunk.id, DocumentChunk.text
        ).where(DocumentChunk.embedding.is_not(None))
        rows = list((await session.execute(stmt)).all())
        print(f"total chunks in db={total}, chunks with embedding={len(rows)}")

        done = 0
        batch = []
        batch_ids = []
        for cid, text in rows:
            batch.append(text)
            batch_ids.append(cid)
            if len(batch) >= settings.embedding_batch_size:
                await _embed_batch(session, provider, batch_ids, batch)
                done += len(batch)
                batch, batch_ids = [], []
                if done % 512 == 0:
                    print(f"  embedded {done}/{len(rows)}")
        if batch:
            await _embed_batch(session, provider, batch_ids, batch)
            done += len(batch)

        await session.commit()
        print(f"DONE: embedded {done} chunks")


async def _embed_batch(session, provider, ids, texts) -> None:
    try:
        vectors = await provider.embed_batch(texts)
    except Exception as e:  # noqa: BLE001
        print("  embed batch failed:", e)
        return
    for cid, vec in zip(ids, vectors, strict=True):
        await session.execute(
            update(DocumentChunk)
            .where(DocumentChunk.id == cid)
            .values(embedding=vec)
        )


if __name__ == "__main__":
    asyncio.run(main())
