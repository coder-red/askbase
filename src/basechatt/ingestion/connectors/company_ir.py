"""Generic company investor-relations connector.

For each company in the configured universe with an ``ir_url``, discover and
fetch public investor-relations documents: annual reports, quarterly reports,
earnings releases and financial statements. Companies are read from
``config/companies.yaml`` so the universe can expand without code changes.
"""

from __future__ import annotations

from datetime import datetime

import yaml
from bs4 import BeautifulSoup

from basechatt.config.settings import settings
from basechatt.database.models import AuthorityLevel, DocumentType
from basechatt.ingestion.connectors.base import (
    ConnectorError,
    DiscoveredDocument,
    FetchedDocument,
    SourceConnector,
)
from basechatt.ingestion.registry import register
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.ingestion.company_ir")

DOC_HINTS = {
    "annual report": DocumentType.ANNUAL_REPORT,
    "annual report and accounts": DocumentType.ANNUAL_REPORT,
    "quarterly report": DocumentType.QUARTERLY_REPORT,
    "quarter": DocumentType.QUARTERLY_REPORT,
    "financial statement": DocumentType.FINANCIAL_STATEMENT,
    "financial statements": DocumentType.FINANCIAL_STATEMENT,
    "earnings": DocumentType.EARNINGS_RELEASE,
    "investor presentation": DocumentType.INVESTOR_PRESENTATION,
    "results": DocumentType.EARNINGS_RELEASE,
    "audited": DocumentType.FINANCIAL_STATEMENT,
    "press release": DocumentType.PRESS_RELEASE,
}


@register
class CompanyIRConnector(SourceConnector):
    code = "company_ir"
    name = "Nigerian Company Investor Relations"
    authority_level = AuthorityLevel.COMPANY_PRIMARY
    base_url = ""

    def _load_companies(self) -> list[dict]:
        try:
            with open(settings.companies_config, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            return data.get("companies", [])
        except FileNotFoundError:
            logger.warning("companies.yaml not found at %s", settings.companies_config)
            return []

    async def discover(self) -> list[DiscoveredDocument]:
        docs: list[DiscoveredDocument] = []
        for company in self._load_companies():
            ir_url = company.get("ir_url", "")
            if not ir_url:
                continue
            try:
                docs.extend(await self._discover_company(ir_url, company))
            except ConnectorError as e:
                logger.warning(
                    "Company IR discovery failed for %s (%s): %s",
                    company.get("ticker"),
                    ir_url,
                    e,
                )
        return docs

    async def _discover_company(
        self, ir_url: str, company: dict
    ) -> list[DiscoveredDocument]:
        try:
            resp = await self._http_get(ir_url)
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"Failed to fetch {ir_url}: {e}") from e
        if resp.status_code != 200:
            raise ConnectorError(f"HTTP {resp.status_code} from {ir_url}")

        soup = BeautifulSoup(resp.text, "lxml")
        docs: list[DiscoveredDocument] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(" ", strip=True).lower()
            if not text or len(text) < 4:
                continue
            url = self._absolute(ir_url, href)
            if url in seen or not url:
                continue
            doc_type = self._classify(text)
            if doc_type is None:
                # Also accept direct document links (pdf) even if anchor text is generic.
                if not (url.lower().endswith(".pdf") or "download" in url.lower()):
                    continue
                doc_type = DocumentType.OTHER
            seen.add(url)
            docs.append(
                DiscoveredDocument(
                    source_code=self.code,
                    external_id=url.split("/")[-1].lower() or url,
                    url=url,
                    title=a.get_text(" ", strip=True),
                    document_type=doc_type,
                    company_ticker=company.get("ticker"),
                    authority_level=self.authority_level,
                    metadata={"company_name": company.get("name", "")},
                )
            )
        return docs[:50]

    def _classify(self, text: str) -> DocumentType | None:
        for key, doc_type in DOC_HINTS.items():
            if key in text:
                return doc_type
        return None

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

    def _absolute(self, base: str, href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("#") or href.startswith("javascript"):
            return ""
        from urllib.parse import urljoin

        return urljoin(base, href)

    async def get_last_modified(self, doc: DiscoveredDocument) -> datetime | None:
        return None
