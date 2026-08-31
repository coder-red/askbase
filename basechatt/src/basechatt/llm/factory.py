"""Factory functions that construct LLM and embedding providers from settings."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from basechatt.config.settings import Settings, settings

if TYPE_CHECKING:
    from basechatt.llm.base import LLMProvider
    from basechatt.llm.embeddings import EmbeddingProvider


@lru_cache
def get_llm_provider(cfg: Settings | None = None) -> LLMProvider:
    cfg = cfg or settings
    from basechatt.llm.providers import GroqProvider, MockProvider, OpenAIProvider

    mapping = {
        "groq": GroqProvider,
        "openai": OpenAIProvider,
        "mock": MockProvider,
    }
    cls = mapping.get(cfg.llm_provider, MockProvider)
    return cls(cfg)


@lru_cache
def get_embedding_provider(cfg: Settings | None = None) -> EmbeddingProvider:
    cfg = cfg or settings
    from basechatt.llm.embeddings import GroqEmbeddingProvider, MockEmbeddingProvider

    # Explicit offline mode: deterministic local vectors, no API required.
    if cfg.embedding_provider == "mock":
        return MockEmbeddingProvider(dim=cfg.embedding_dim)
    if cfg.embedding_provider == "openai_compat":
        return _OpenAICompatEmbeddingProvider(cfg)
    # Backward-compatible default: Groq embeddings when the LLM provider is
    # Groq; OpenAI-compatible embeddings for openai; mock otherwise (tests).
    if cfg.llm_provider == "openai" and cfg.openai_api_key:
        return _OpenAICompatEmbeddingProvider(cfg)
    if cfg.llm_provider == "mock":
        return MockEmbeddingProvider(dim=cfg.embedding_dim)
    return GroqEmbeddingProvider(cfg)


class _OpenAICompatEmbeddingProvider:
    """Minimal OpenAI-compatible embeddings wrapper (text-embedding-3-small)."""

    def __init__(self, cfg: Settings) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=cfg.openai_api_key)
        self._model = "text-embedding-3-small"
        self._dim = 1536

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.embeddings.create(model=self._model, input=texts)
        data = sorted(resp.data, key=lambda d: d.index)
        return [list(d.embedding) for d in data]

    async def embed_text(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    @property
    def dim(self) -> int:
        return self._dim

    def cache_key(self, text: str) -> str:
        import hashlib

        return hashlib.sha256(text.encode("utf-8")).hexdigest()
