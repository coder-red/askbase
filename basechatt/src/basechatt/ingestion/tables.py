"""Table normalization.

Tables are first-class data. ``row`` above is a parsed 2-D grid; this module
turns it into (a) the stored headers/rows, (b) a searchable normalized-text
representation, and (c) detects units/currency where possible.
"""

from __future__ import annotations

from basechatt.database.models import TableRecord
from basechatt.ingestion.parser import ParsedTable


def normalize_table(table: ParsedTable, document_id: str, version_id: str) -> TableRecord:
    """Build a persisted TableRecord for a parsed table.

    The normalized text representation joins headers + rows in a flat,
    search-friendly string while retaining the structured rows/lists.
    """
    headers = table.headers or []
    rows = table.rows or []

    text_parts: list[str] = []
    if table.title:
        text_parts.append(table.title)
    if headers:
        text_parts.append(" | ".join(headers))
    for row in rows:
        text_parts.append(" | ".join(row))
    normalized = "\n".join(text_parts)

    units, currency = _detect_units_currency(headers, rows)

    return TableRecord(
        document_id=document_id,
        version_id=version_id,
        page=table.page,
        section=table.section,
        title=table.title,
        headers=headers,
        rows=rows,
        units=units,
        currency=currency,
        normalized_text=normalized,
        raw_text=normalized,
    )


_CURRENCY_MAP = {
    "NGN": "NGN", "N": "NGN", "naira": "NGN", "₦": "NGN",
    "USD": "USD", "$": "USD", "US$": "USD",
    "GBP": "GBP", "£": "GBP", "EUR": "EUR", "€": "EUR",
}
_UNIT_MAP = {
    "N'000": "thousands", "₦'000": "thousands", "'000": "thousands",
    "N'm": "millions", "₦'m": "millions", "N'million": "millions",
    "million": "millions", "millions": "millions", "N'bn": "billions",
    "N'billion": "billions", "billion": "billions", "₦b": "billions",
    "₦'bn": "billions", "%": "percent", "bps": "basis-points",
}


def _detect_units_currency(headers: list[str], rows: list[list[str]]) -> tuple[str, str]:
    haystack = " ".join(headers) + " " + " ".join(c for r in rows for c in r)
    # Look for unit markers early in the header row.
    for token, normalized in _UNIT_MAP.items():
        if token.lower() in haystack.lower():
            units = normalized
            break
    else:
        units = ""

    currency = ""
    for token, code in _CURRENCY_MAP.items():
        if token in haystack or token.lower() in haystack.lower():
            currency = code
            break
    return units, currency


def table_summary(table: TableRecord) -> str:
    """Short human-readable summary used for citations/evidence display."""
    lines = []
    if table.title:
        lines.append(table.title)
    if table.headers:
        lines.append(" | ".join(table.headers))
    for row in table.rows[:10]:
        lines.append(" | ".join(row))
    return "\n".join(lines)
