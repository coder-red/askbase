"""Environment + Pydantic settings for BaseChatt."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Central configuration object loaded from env / .env.

    Every value can be overridden by an environment variable prefixed with
    ``BASECHATT_`` (see ``SettingsConfigDict``). Never load secrets directly;
    never commit a real ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_prefix="BASECHATT_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BaseChatt"
    debug: bool = False
    environment: str = "development"

    #################################################
    # LLM provider. Default is Groq (fast, free tier).
    # Supported: groq | openai | anthropic | mock
    #################################################
    llm_provider: Literal["groq", "openai", "anthropic", "mock"] = "groq"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_chat_model: str = "llama-3.3-70b-versatile"
    groq_embedding_model: str = "nomic-embed-text-v1.5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048

    #################################################
    # Embedding provider: groq | openai_compat | mock
    # "mock" = deterministic offline vectors (no API needed)
    #################################################
    embedding_provider: Literal["groq", "openai_compat", "mock"] = "groq"

    #################################################
    # Embeddings (via provider API, $0 free tier)
    #################################################
    embedding_model: str = "nomic-embed-text-v1.5"
    embedding_dim: int = 768  # nomic-embed-text v1.5 outputs 768-d vectors
    embedding_batch_size: int = 32
    embedding_cache_ttl: int = 3600

    #################################################
    # Reranker strategy
    # "deterministic"  : lexical + authority + freshness heuristics (no LLM)
    # "llm"            : LLM judges candidate relevance
    #################################################
    reranker_strategy: Literal["deterministic", "llm"] = "deterministic"

    #################################################
    # Database
    #################################################
    database_url: str = "postgresql+asyncpg://basechatt:basechatt@localhost:5433/basechatt"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    #################################################
    # Redis
    #################################################
    redis_url: str = "redis://localhost:6380/0"
    use_redis: bool = True

    #################################################
    # Retrieval
    #################################################
    dense_top_k: int = 20
    lexical_top_k: int = 20
    fusion_limit: int = 40
    reranker_top_n: int = 8
    rrf_k: int = 60
    semantic_weight: float = 0.6
    lexical_weight: float = 0.4

    #################################################
    # Chunking
    #################################################
    chunk_size: int = 700
    chunk_overlap: int = 100

    #################################################
    # Ingestion / sync
    #################################################
    cbn_sync_hours: int = 6
    nbs_sync_hours: int = 12
    sec_nigeria_sync_hours: int = 6
    ngx_sync_hours: int = 6
    fmdq_sync_hours: int = 12
    company_ir_sync_hours: int = 24
    worker_concurrency: int = 4
    http_timeout: float = 60.0
    max_retries: int = 3
    backoff_base: float = 1.5

    #################################################
    # Security
    #################################################
    api_key: str = ""
    max_query_length: int = 4000
    max_evidence_chars: int = 8000
    rate_limit_per_minute: int = 60

    #################################################
    # Paths
    #################################################
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    companies_config: Path = Field(default=PROJECT_ROOT / "config" / "companies.yaml")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def tables_dir(self) -> Path:
        return self.data_dir / "tables"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
