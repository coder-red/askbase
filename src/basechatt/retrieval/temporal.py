"""Temporal retrieval.

Parses natural-language temporal expressions into structured date filters so
"before 2024", "between 2022 and 2024", "latest", "as of 2023" map to concrete
``before``/``after`` windows. Historical queries must not accidentally pull
newer evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from dateutil import parser as dateparser

MONTHS_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


@dataclass
class TemporalSpec:
    mode: str = "all"  # all | latest | before | after | between | during | since | on
    before: datetime | None = None
    after: datetime | None = None
    year: int | None = None
    raw: str = ""

    def apply(self, before=None, after=None) -> TemporalSpec:
        if before is not None:
            self.before = self.before or before
        if after is not None:
            self.after = self.after or after
        return self


LATEST_WORDS = ["latest", "most recent", "current", "newest", "recently", "as of now", "now"]
HISTORICAL_WORDS = ["historical", "previously", "in the past", "earlier", "older", "then"]


def parse_temporal(query: str) -> TemporalSpec:
    """Extract a time constraint from a query string."""
    q = " " + query.lower().strip() + " "
    spec = TemporalSpec(raw=query)

    # Mode: latest / current
    if any(w in q for w in ("latest ", "most recent ", "current ", "newest ", "as of now")):
        spec.mode = "latest"

    # "between X and Y"
    m = re.search(r"between\s+(.+?)\s+and\s+(.+?)(\s|$)", q)
    if m:
        start = _parse_date_token(m.group(1))
        end = _parse_date_token(m.group(2))
        if start and end:
            spec.mode = "between"
            spec.after = start
            spec.before = _end_of_period(end)
            return spec

    # "during X", "in X" (year/period bounds -> the whole period)
    m = re.search(r"(?:during|in)\s+(?:the\s+)?(.+?)(?:,|\.|;|$)", q)
    if m:
        period = _parse_date_token(m.group(1))
        if period:
            spec.mode = "during"
            spec.after = period
            spec.before = _end_of_period(period)
            return spec

    # "before X"
    m = re.search(r"before\s+(.+?)(?:,|\.|;|$)", q)
    if m:
        boundary = _parse_date_token(m.group(1))
        if boundary:
            spec.mode = "before"
            spec.before = boundary
            return spec

    # "after X" / "since X" (from X onward)
    m = re.search(r"(?:after|since|from)\s+(.+?)(?:,|\.|;|$)", q)
    if m:
        anchor = _parse_date_token(m.group(1))
        if anchor:
            spec.mode = "after"
            spec.after = anchor
            return spec

    # bare year e.g. "in 2023" or "2023"
    m = re.search(r"\b((?:19|20)\d{2})\b", q)
    if m:
        year = int(m.group(1))
        spec.mode = "during"
        spec.year = year
        spec.after = datetime(year, 1, 1)
        spec.before = datetime(year, 12, 31, 23, 59, 59)
        if "prior" in q or "historical" in q or "as of" in q:
            spec.mode = "before"
            spec.after = None
            spec.before = datetime(year, 12, 31, 23, 59, 59)
        return spec

    return spec


def _parse_date_token(token: str) -> datetime | None:
    token = token.strip().rstrip(",")
    # "December 2024"
    m = re.match(r"([a-z]+)\s+((?:19|20)\d{2})", token)
    if m and m.group(1) in MONTHS_MAP:
        return datetime(int(m.group(2)), MONTHS_MAP[m.group(1)], 1)
    # bare year
    m = re.match(r"^((?:19|20)\d{2})$", token)
    if m:
        return datetime(int(m.group(1)), 1, 1)
    # generic parseable date
    try:
        return dateparser.parse(token, fuzzy=False)
    except (ValueError, OverflowError, TypeError):
        return None


def _end_of_period(dt: datetime) -> datetime:
    if (dt.month, dt.day) == (1, 1):
        # year boundary -> end of that year

        return datetime(dt.year, 12, 31, 23, 59, 59)
    return dt
