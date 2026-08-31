"""Central Bank of Nigeria (CBN) connector.

Discovers and fetches public CBN documents: monetary policy communiques,
decisions, and press statements. Primary regulator source.
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

logger = get_logger("basechatt.ingestion.cbn")

BASE_URL = "https://www.cbn.gov.ng"
DECISIONS_URL = "https://www.cbn.gov.ng/MonetaryPolicy/decisions.html"
COMMUNIQUES_URL = "https://www.cbn.gov.ng/MonetaryPolicy/Communiques.html"
PUBLICATIONS_URL = "https://www.cbn.gov.ng/Documents/"


@register
class CBNConnector(SourceConnector):
    code = "cbn"
    name = "Central Bank of Nigeria"
    authority_level = AuthorityLevel.PRIMARY_REGULATOR
    base_url = BASE_URL

    async def discover(self) -> list[DiscoveredDocument]:
        docs: list[DiscoveredDocument] = []
        try:
            docs.extend(await self._discover_monetary_policy())
        except ConnectorError as e:
            logger.warning("CBN monetary policy discovery failed: %s", e)
        try:
            docs.extend(await self._discover_circulars())
        except ConnectorError as e:
            logger.warning("CBN circular discovery failed: %s", e)
        return docs

    async def _discover_monetary_policy(self) -> list[DiscoveredDocument]:
        """Parse the monetary policy decisions page for communique PDFs."""
        try:
            resp = await self._http_get(DECISIONS_URL)
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"Failed to fetch {DECISIONS_URL}: {e}") from e
        if resp.status_code != 200:
            raise ConnectorError(f"HTTP {resp.status_code} from {DECISIONS_URL}")

        soup = BeautifulSoup(resp.text, "lxml")
        docs: list[DiscoveredDocument] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            if not title:
                continue
            if any(k in title.lower() for k in ("communique", "monetary policy", "decision")):
                url = self._absolute(href)
                if url in seen or not url:
                    continue
                seen.add(url)
                ext_id = url.split("/")[-1].lower() or url
                docs.append(
                    DiscoveredDocument(
                        source_code=self.code,
                        external_id=ext_id,
                        url=url,
                        title=title,
                        document_type=DocumentType.COMMUNIQUE,
                        authority_level=self.authority_level,
                        metadata={"category": "monetary-policy"},
                    )
                )
        return docs

    async def _discover_circulars(self) -> list[DiscoveredDocument]:
        """Discover circular PDFs by following the CBN circular index pages."""
        index_urls = [
            "https://www.cbn.gov.ng/circulars.html",
            "https://www.cbn.gov.ng/BSDCircularsNEW.html",
            "https://www.cbn.gov.ng/policycirculars.html",
        ]
        docs: list[DiscoveredDocument] = []
        seen: set[str] = set()
        for index_url in index_urls:
            try:
                resp = await self._http_get(index_url)
            except Exception as e:  # noqa: BLE001
                logger.warning("CBN circular index %s failed: %s", index_url, e)
                continue
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                title = a.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                url = self._absolute(href)
                # Only real documents: PDFs or CBN /Out/ document paths.
                if ".pdf" not in url.lower() and "/out/" not in url.lower():
                    continue
                if url in seen:
                    continue
                seen.add(url)
                docs.append(
                    DiscoveredDocument(
                        source_code=self.code,
                        external_id=url.split("/")[-1].lower() or url,
                        url=url,
                        title=title,
                        document_type=DocumentType.CIRCULAR,
                        authority_level=self.authority_level,
                        metadata={"category": "circular"},
                    )
                )
            # Respect the source: keep the crawl shallow to avoid heavy loads.
        return docs[:30]

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
        if href.startswith("/"):
            return BASE_URL + href
        return BASE_URL + "/" + href

    async def get_last_modified(self, doc: DiscoveredDocument) -> datetime | None:
        # CBN pages do not expose Last-Modified reliably; rely on content hash.
        return None
