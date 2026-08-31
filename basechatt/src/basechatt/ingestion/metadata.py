"""Metadata extraction.

Extracts structured metadata (publication date, effective date, period, title,
section hierarchy) from parsed documents and raw text. Uses deterministic
heuristics first and never relies on the LLM for metadata that can be parsed
reliably.
"""

from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateparser

MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]

# Patterns commonly found in CBN communiques, reports, and press releases.
_DATE_PATTERNS = [
    r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December),\s+(\d{4})",
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
    r"(\d{4})-(\d{2})-(\d{2})",
    r"(\d{2})/(\d{2})/(\d{4})",
]


def extract_date(text: str) -> datetime | None:
    """Best-effort extraction of the first plausible date in text."""
    for pattern in _DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            raw = m.group(0)
            try:
                return dateparser.parse(raw, fuzzy=False, dayfirst=False)
            except (ValueError, OverflowError):
                continue
    return None


def extract_period(text: str) -> tuple[datetime | None, datetime | None]:
    """Extract a start/end period when a range ("2022 - 2024") is present."""
    m = re.search(r"((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})", text)
    if m:
        start_year = int(m.group(1))
        end_year = int(m.group(2))
        return datetime(start_year, 1, 1), datetime(end_year, 12, 31)
    return None, None


def classify_document_type(title: str) -> str:
    """Classify document type from title text. Returns a DocumentType value."""
    low = title.lower()
    mapping = [
        ("annual report", "annual_report"),
        ("quarterly", "quarterly_report"),
        ("quarter", "quarterly_report"),
        ("circular", "circular"),
        ("communique", "communique"),
        ("statistical bulletin", "statistical_bulletin"),
        ("economic report", "economic_report"),
        ("financial statement", "financial_statement"),
        ("investor presentation", "investor_presentation"),
        ("market bulletin", "market_announcement"),
        ("notice", "market_announcement"),
        ("earnings", "earnings_release"),
        ("press release", "press_release"),
        ("press briefing", "press_release"),
    ]
    for key, value in mapping:
        if key in low:
            return value
    return "other"


def extract_section_path(section: str, subsection: str) -> str:
    """Build a readable path from section + subsection for citations."""
    if section and subsection:
        return f"{section} / {subsection}"
    return section or subsection or ""
