"""FMDQ Exchange connector.

Discovers and fetches public FMDQ publications: benchmark methodologies
(NAFEX/NIBOR/NITTY), market notices, and benchmark-related documents.
Primary market-data source.
"""

from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from basechatt.database.models import AuthorityLevel, DocumentType
from basechatt.ingestion.connectors.base import (
    ConnectorError,
    DiscoveredDocument,
    FetchedDocument,
    SourceConnector,
)
from basechatt.ingestion.registry import register
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.ingestion.fmdq")

BASE_URL = "https://fmdqgroup.com"
BENCHMARKS_URL = "https://fmdqgroup.com/exchange/market-data/benchmarks/"
MARKET_NOTICES_URL = "https://fmdqgroup.com/exchange/derivatives-market-notice/market-notices/"


@register
class FMDQConnector(SourceConnector):
    code = "fmdq"
    name = "FMDQ Securities Exchange"
    authority_level = AuthorityLevel.PRIMARY_EXCHANGE
    base_url = BASE_URL

    async def discover(self) -> list[DiscoveredDocument]:
        docs: list[DiscoveredDocument] = []
        for label, url, doc_type in (
            ("benchmark", BENCHMARKS_URL, DocumentType.GUIDELINE),
            ("market-notice", MARKET_NOTICES_URL, DocumentType.MARKET_ANNOUNCEMENT),
        ):
            try:
                docs.extend(await self._discover_page(url, doc_type, label))
            except ConnectorError as e:
                logger.warning("FMDQ %s discovery failed: %s", label, e)
        return docs

    async def _discover_page(
        self, page_url: str, doc_type: DocumentType, label: str
    ) -> list[DiscoveredDocument]:
        try:
            resp = await self._http_get(page_url)
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"Failed to fetch {page_url}: {e}") from e
        if resp.status_code != 200:
            raise ConnectorError(f"HTTP {resp.status_code} from {page_url}")

        soup = BeautifulSoup(resp.text, "lxml")
        docs: list[DiscoveredDocument] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 4:
                continue
            url = self._absolute(href)
            if url in seen or not url:
                continue
            low = url.lower()
            if not ("benchmark" in low or "methodology" in low or "notice" in low or ".pdf" in low):
                continue
            seen.add(url)
            docs.append(
                DiscoveredDocument(
                    source_code=self.code,
                    external_id=url.split("/")[-1].lower() or url,
                    url=url,
                    title=title,
                    document_type=doc_type,
                    authority_level=self.authority_level,
                    metadata={"category": label},
                )
            )
        return docs[:40]

    async def fetch(self, doc: DiscoveredDocument) -> FetchedDocument:
        try:
            resp = await self._http_get(doc.url)
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"Failed to fetch {doc.url}: {e}") from e
        if resp.status_code != 200:
            raise ConnectorError(f"HTTP {resp.status_code} downloading {doc.url}")
        mime = resp.headers.get("content-type", "").split(";")[0] or "application/pdf"
        filename = doc.url.split("/")[-1].split("?")[0] or "document"
        return FetchedDocument(
            discovered=doc,
            content=resp.content,
            mime_type=mime,
            filename=filename,
        )

    def _absolute(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return BASE_URL + ("/" + href.lstrip("/") if href else "")

    async def get_last_modified(self, doc: DiscoveredDocument) -> datetime | None:
        return None
