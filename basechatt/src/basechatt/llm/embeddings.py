"""Embedding providers.

Groq exposes an OpenAI-compatible embeddings endpoint (``POST
/openai/v1/embeddings`` with ``nomic-embed-text-v1.5``). A mock provider is
used for tests/offline so ingestion can be exercised without an API key.
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from basechatt.config.settings import Settings, settings
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.llm.embeddings")


class EmbeddingProvider(ABC):
    """Interface for producing dense embedding vectors."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        ...

    @abstractmethod
    def cache_key(self, text: str) -> str:
        ...


class GroqEmbeddingProvider(EmbeddingProvider):
    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self._client: AsyncOpenAI | None = None

    def _client_or_raise(self) -> AsyncOpenAI:
        if self._client is None:
            key = self.cfg.groq_api_key or os.getenv("GROQ_API_KEY")
            if not key:
                raise RuntimeError(
                    "Groq API key is not configured. Set BASECHATT_GROQ_API_KEY "
                    "or GROQ_API_KEY, or configure a different embedding provider."
                )
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=self.cfg.groq_base_url,
            )
        return self._client

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._client_or_raise()
        # nomic-embed-text v1.5 has a strong instruction prefix; we use the
        # plain "search_document" prefix for document chunks.
        inputs = [self._prepend(text) for text in texts]
        resp = await client.embeddings.create(
            model=self.cfg.groq_embedding_model,
            input=inputs,
            encoding_format="float",
        )
        # Responses may come back out of order; sort by index.
        data = sorted(resp.data, key=lambda d: d.index)
        return [list(d.embedding) for d in data]

    def _prepend(self, text: str) -> str:
        # nomic-embed-text recommends task instructions; keep it lightweight.
        return text

    async def embed_text(self, text: str) -> list[float]:
        out = await self.embed_batch([text])
        return out[0]

    @property
    def dim(self) -> int:
        return self.cfg.embedding_dim

    def cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic pseudo-embedding for tests/offline runs.

    Produces stable 768-d vectors from the text hash so retrieval tests can run
    without any external call.
    """

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim

    async def embed_text(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [
            float((digest[i % len(digest)] % 200) / 100.0 - 1.0)
            for i in range(self._dim)
        ]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(t) for t in texts]

    @property
    def dim(self) -> int:
        return self._dim

    def cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
