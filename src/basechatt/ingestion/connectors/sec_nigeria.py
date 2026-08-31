"""Securities and Exchange Commission Nigeria (SEC Nigeria) connector.

Discovers and fetches public SEC Nigeria publications: circulars to market
participants, statistical bulletins, annual reports and market publications.
Primary regulator source for the capital market.
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

logger = get_logger("basechatt.ingestion.sec_nigeria")

BASE_URL = "https://sec.gov.ng"
CIRCULARS_URL = "https://www.sec.gov.ng/for-investors/keep-track-of-circulars/"
STAT_BULLETIN_URL = "https://sec.gov.ng/for-operators/keep-track-of-capital-market-data/statistical-bulletin/"
ANNUAL_REPORTS_URL = "https://www.sec.gov.ng/about/resources/annual-reports/"


@register
class SECNigeriaConnector(SourceConnector):
    code = "sec_nigeria"
    name = "Securities and Exchange Commission Nigeria"
    authority_level = AuthorityLevel.PRIMARY_REGULATOR
    base_url = BASE_URL

    async def discover(self) -> list[DiscoveredDocument]:
        docs: list[DiscoveredDocument] = []
        for label, url, doc_type in (
            ("circular", CIRCULARS_URL, DocumentType.CIRCULAR),
            ("statistical-bulletin", STAT_BULLETIN_URL, DocumentType.STATISTICAL_BULLETIN),
            ("annual-report", ANNUAL_REPORTS_URL, DocumentType.ANNUAL_REPORT),
        ):
            try:
                docs.extend(await self._discover_page(url, doc_type, label))
            except ConnectorError as e:
                logger.warning("SEC Nigeria %s discovery failed: %s", label, e)
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
            if not self._looks_like_doc(href, label):
                continue
            url = self._absolute(href)
            if url in seen:
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
        return docs[:30]

    def _looks_like_doc(self, href: str, label: str) -> bool:
        low = href.lower()
        if label == "circular":
            return "circular" in low or "pdf" in low
        if label == "statistical-bulletin":
            return "statistical" in low or "xlsx" in low or "pdf" in low
        if label == "annual-report":
            return "annual" in low or "pdf" in low
        return False

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
        host = "www.sec.gov.ng"
        return f"https://{host}/" + href.lstrip("/")

    async def get_last_modified(self, doc: DiscoveredDocument) -> datetime | None:
        return None
