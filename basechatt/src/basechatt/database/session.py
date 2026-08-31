"""Async SQLAlchemy engine, session factory, and schema bootstrap.

Connection pooling is enabled via the engine; the FastAPI dependency
``get_db`` yields a session scoped to one request/transaction.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from basechatt.config.settings import settings
from basechatt.database.models import Base
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.database")

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create the pgvector extension and all tables (development bootstrap).

    In a production environment you would use Alembic migrations instead. For
    tests and local development this bootstrap is convenient and correct.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # HNSW index for cosine vector search. Configured here (not in the model)
        # so that table creation succeeds before the extension exists.
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
                "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
            )
        )
    logger.info("database initialised")


async def init_models() -> None:
    """Alias used by tests / CLI when they want to recreate schema."""
    await init_db()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Standalone session context helper (non-request code)."""
    async with SessionLocal() as session:
        yield session
