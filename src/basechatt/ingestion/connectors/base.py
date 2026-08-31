"""Connector base classes and shared data structures."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from basechatt.database.models import AuthorityLevel, DocumentType
from basechatt.config.settings import settings


@dataclass
class DiscoveredDocument:
    """A document a connector discovered, not yet fetched/parsed."""

    source_code: str
    external_id: str
    url: str
    title: str
    document_type: DocumentType
    published_at: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    company_ticker: str | None = None
    effective_date: datetime | None = None
    authority_level: AuthorityLevel = AuthorityLevel.SECONDARY
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchedDocument:
    """The raw bytes + metadata of a document to be stored & processed."""

    discovered: DiscoveredDocument
    content: bytes
    mime_type: str = "application/octet-stream"
    filename: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class ConnectorError(Exception):
    """Raised for connector-level failures (HTTP, parse, rate limit)."""


class SourceConnector(ABC):
    """Interface every BaseChatt data connector must implement.

    ``discover`` returns the set of documents that exist at the source.
    ``fetch`` returns the raw bytes for a discovered document. ``get_content_hash``
    is used for deduplication/versioning, and ``get_last_modified`` helps with
    incremental syncs.
    """

    code: str = ""
    name: str = ""
    authority_level: AuthorityLevel = AuthorityLevel.SECONDARY

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    @abstractmethod
    async def discover(self) -> list[DiscoveredDocument]:
        ...

    @abstractmethod
    async def fetch(self, doc: DiscoveredDocument) -> FetchedDocument:
        ...

    async def get_last_modified(self, doc: DiscoveredDocument) -> datetime | None:
        return None

    @staticmethod
    def get_content_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _user_agent(self) -> str:
        return "BaseChattResearch (research agent; respectful of rate limits)"

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=settings.backoff_base, min=1, max=30),
        reraise=True,
    )
    async def _http_get(self, url: str, **kwargs: Any) -> httpx.Response:
        timeout = httpx.Timeout(
            settings.http_timeout, connect=10.0, pool=10.0
        )
        kwargs.setdefault("timeout", timeout)
        client = self.client or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": self._user_agent()},
            follow_redirects=True,
        )
        if self.client is None:
            try:
                return await client.get(url, **kwargs)
            finally:
                await client.aclose()
        return await client.get(url, **kwargs)
