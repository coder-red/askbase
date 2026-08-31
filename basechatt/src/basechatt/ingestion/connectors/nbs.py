"""National Bureau of Statistics (NBS) connector.

Discovers and fetches public NBS statistical publications, primarily the
monthly Consumer Price Index (CPI) reports and related news releases.
Primary statistical authority source.
"""

from __future__ import annotations

import re
from datetime import date, datetime

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

logger = get_logger("basechatt.ingestion.nbs")

BASE_URL = "https://nigerianstat.gov.ng"
CPI_SEARCH_URL = "https://nigerianstat.gov.ng/elibrary/search/cpi"
MICRODATA_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials"


@register
class NBSConnector(SourceConnector):
    code = "nbs"
    name = "National Bureau of Statistics"
    authority_level = AuthorityLevel.PRIMARY_REGULATOR
    base_url = BASE_URL

    async def discover(self) -> list[DiscoveredDocument]:
        docs: list[DiscoveredDocument] = []
        try:
            docs.extend(await self._discover_cpi())
        except ConnectorError as e:
            logger.warning("NBS CPI discovery failed: %s", e)
        return docs

    async def _discover_cpi(self) -> list[DiscoveredDocument]:
        """Parse the CPI e-library search page (and pdfuploads pattern)."""
        docs: list[DiscoveredDocument] = []
        seen: set[str] = set()

        try:
            resp = await self._http_get(CPI_SEARCH_URL)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    title = a.get_text(" ", strip=True)
                    if not title or "cpi" not in title.lower():
                        continue
                    url = self._absolute(href)
                    if url in seen or not url:
                        continue
                    seen.add(url)
                    doc, ok = self._doc_from_title(title, url)
                    if ok:
                        docs.append(doc)
        except Exception as e:  # noqa: BLE001
            logger.warning("NBS CPI page parse error: %s", e)

        # Also try the direct pdfuploads naming convention for recent months.
        months = self._recent_months(6)
        month_names = {
            1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
            7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
            12: "December",
        }
        for m, y in months:
            month_name = month_names[m]
            url = f"{BASE_URL}/pdfuploads/CPI_{month_name}_{y}.pdf"
            if url in seen:
                continue
            seen.add(url)
            docs.append(
                DiscoveredDocument(
                    source_code=self.code,
                    external_id=f"cpi-{url.split('/')[-1].lower()}",
                    url=url,
                    title=f"Consumer Price Index {month_name} {y}",
                    document_type=DocumentType.STATISTICAL_BULLETIN,
                    published_at=datetime(y, m, 15),
                    authority_level=self.authority_level,
                    metadata={"indicator": "CPI"},
                )
            )

        # The pdfuploads URLs may 404 for months without a report; the pipeline
        # will skip failed fetches gracefully.
        return docs[:24]

    def _doc_from_title(self, title: str, url: str) -> tuple[DiscoveredDocument | None, bool]:
        months = (
            "January|February|March|April|May|June|July|August|September|"
            "October|November|December"
        )
        m = re.search(
            rf"({months})\s+(\d{{4}})", title, re.IGNORECASE
        )
        published: datetime | None = None
        if m:
            try:
                published = datetime.strptime(f"{m.group(1)} 1 {m.group(2)}", "%B %d %Y")
            except ValueError:
                published = None
        return (
            DiscoveredDocument(
                source_code=self.code,
                external_id=url.split("/")[-1].lower() or url,
                url=url,
                title=title,
                document_type=DocumentType.STATISTICAL_BULLETIN,
                published_at=published,
                authority_level=self.authority_level,
                metadata={"indicator": "CPI"},
            ),
            True,
        )

    def _recent_months(self, n: int) -> list[tuple[int, int]]:
        """Return (month, year) pairs for the last n months ending last month."""
        today = date.today()
        months: list[tuple[int, int]] = []
        if today.month == 1:
            y, m = today.year - 1, 12
        else:
            y, m = today.year, today.month - 1
        for _ in range(n):
            if m < 1:
                m = 12
                y -= 1
            months.append((m, y))
            m -= 1
        return months

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
