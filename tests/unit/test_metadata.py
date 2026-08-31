"""Unit tests for deterministic metadata extraction."""

from __future__ import annotations

from datetime import datetime

from basechatt.ingestion.metadata import (
    classify_document_type,
    extract_date,
    extract_period,
    extract_section_path,
)


def test_extract_date_iso():
    assert extract_date("Published 2024-03-31 in Lagos") == datetime(2024, 3, 31)


def test_extract_date_named_month():
    assert extract_date("Adopted on December 12, 2024") == datetime(2024, 12, 12)


def test_extract_date_day_first_form():
    assert extract_date("dated 12 January, 2024") == datetime(2024, 1, 12)


def test_extract_date_missing():
    assert extract_date("no dates here") is None


def test_extract_period_range():
    start, end = extract_period("covering 2022 - 2024")
    assert start == datetime(2022, 1, 1)
    assert end == datetime(2024, 12, 31)


def test_extract_period_en_dash():
    start, end = extract_period("FY2020 \u2013 2023")
    assert start.year == 2020
    assert end.year == 2023


def test_extract_period_none():
    assert extract_period("single 2024 year only") == (None, None)


def test_classify_document_type():
    assert classify_document_type("2024 Annual Report") == "annual_report"
    assert classify_document_type("Q3 2024 earnings call transcript") == "earnings_release"
    assert classify_document_type("Press release on rates") == "press_release"
    assert classify_document_type("Something unknown") == "other"


def test_extract_section_path():
    assert extract_section_path("Financial Statements", "Income Statement") == (
        "Financial Statements / Income Statement"
    )
    assert extract_section_path("", "Notes") == "Notes"
    assert extract_section_path("", "") == ""
