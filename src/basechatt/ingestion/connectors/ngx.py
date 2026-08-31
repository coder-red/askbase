"""Nigerian Exchange Group (NGX) connector.

Discovers and fetches public NGX disclosures: corporate announcements, market
bulletins and listed-company financial information. Primary exchange source.
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

logger = get_logger("basechatt.ingestion.ngx")

BASE_URL = "https://ngxgroup.com"
DISCLOSURES_URL = "https://ngxgroup.com/exchange/data/corporate-disclosures/"
FINANCIAL_INFO_URL = "https://ngxgroup.com/financial-information/"
LISTED_COMPANIES_URL = "https://ngxgroup.com/exchange/trade/equities/listed-companies/"


@register
class NGXConnector(SourceConnector):
    code = "ngx"
    name = "Nigerian Exchange Group"
    authority_level = AuthorityLevel.PRIMARY_EXCHANGE
    base_url = BASE_URL

    async def discover(self) -> list[DiscoveredDocument]:
        docs: list[DiscoveredDocument] = []
        for label, url, doc_type in (
            ("disclosure", DISCLOSURES_URL, DocumentType.MARKET_ANNOUNCEMENT),
            ("financial", FINANCIAL_INFO_URL, DocumentType.FINANCIAL_STATEMENT),
        ):
            try:
                docs.extend(await self._discover_page(url, doc_type, label))
            except ConnectorError as e:
                logger.warning("NGX %s discovery failed: %s", label, e)
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
            if not self._looks_like_doc(url):
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

    def _looks_like_doc(self, url: str) -> bool:
        low = url.lower()
        return any(
            token in low
            for token in (
                "disclosure",
                "market",
                "bulletin",
                "financial",
                "annual",
                ".pdf",
                "notice",
                "earnings",
            )
        )

    async def fetch(self, doc: DiscoveredDocument) -> FetchedDocument:
        try:
            resp = await self._http_get(doc.url)
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"Failed to fetch {doc.url}: {e}") from e
        if resp.status_code != 200:
            raise ConnectorError(f"HTTP {resp.status_code} downloading {doc.url}")
        mime = resp.headers.get("content-type", "").split(";")[0] or "application/octet-stream"
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
