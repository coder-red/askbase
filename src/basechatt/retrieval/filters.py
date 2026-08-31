"""Metadata filters for retrieval.

A typed, validated filter object covering the dimensions retrieval supports:
company, source, document type, authority, date range, period and text.
Passing a populated filter restricts dense, lexical and hybrid retrieval
consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RetrievalFilters:
    company_id: str | None = None
    company_ticker: str | None = None
    source_code: str | None = None
    document_type: str | None = None  # matches DocumentType.value
    authority_level: str | None = None  # matches AuthorityLevel.value
    before: datetime | None = None
    after: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    text: str | None = None  # additional required term (lexical)

    def is_empty(self) -> bool:
        return not any(
            [
                self.company_id, self.company_ticker, self.source_code,
                self.document_type, self.authority_level, self.before,
                self.after, self.period_start, self.period_end, self.text,
            ]
        )

    def as_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "company_ticker": self.company_ticker,
            "source_code": self.source_code,
            "document_type": self.document_type,
            "authority_level": self.authority_level,
            "before": self.before.isoformat() if self.before else None,
            "after": self.after.isoformat() if self.after else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "text": self.text,
        }

    def clone(
        self,
        company_id=None, company_ticker=None, source_code=None,
        document_type=None, authority_level=None, before=None,
        after=None, period_start=None, period_end=None, text=None,
    ) -> RetrievalFilters:
        return RetrievalFilters(
            company_id=company_id if company_id is not None else self.company_id,
            company_ticker=company_ticker if company_ticker is not None else self.company_ticker,
            source_code=source_code if source_code is not None else self.source_code,
            document_type=document_type if document_type is not None else self.document_type,
            authority_level=(
                authority_level
                if authority_level is not None
                else self.authority_level
            ),
            before=before if before is not None else self.before,
            after=after if after is not None else self.after,
            period_start=period_start if period_start is not None else self.period_start,
            period_end=period_end if period_end is not None else self.period_end,
            text=text if text is not None else self.text,
        )
