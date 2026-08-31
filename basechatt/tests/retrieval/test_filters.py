"""Unit tests for retrieval filters, temporal parsing and RRF fusion."""

from __future__ import annotations

from datetime import datetime

from basechatt.retrieval.filters import RetrievalFilters
from basechatt.retrieval.fusion import rrf_fuse
from basechatt.retrieval.temporal import parse_temporal


class FakeChunk:
    def __init__(self, id: str, document_id: str) -> None:
        self.id = id
        self._retrieval = {"document_id": document_id}


def _item(chunk_id: str, document_id: str) -> object:
    return SimpleRankItem(chunk_id, document_id)


class SimpleRankItem:
    def __init__(self, chunk_id: str, document_id: str) -> None:
        self.chunk = FakeChunk(chunk_id, document_id)


class TestRetrievalFilters:
    def test_empty_by_default(self):
        assert RetrievalFilters().is_empty() is True

    def test_not_empty_when_populated(self):
        assert RetrievalFilters(source_code="cbn").is_empty() is False

    def test_as_dict_serializes_dates(self):
        f = RetrievalFilters(
            company_ticker="GTCO",
            after=datetime(2024, 1, 1),
            before=datetime(2024, 12, 31),
        )
        d = f.as_dict()
        assert d["company_ticker"] == "GTCO"
        assert d["after"] == "2024-01-01T00:00:00"
        assert d["before"] == "2024-12-31T00:00:00"

    def test_clone_overrides_and_keeps_rest(self):
        base = RetrievalFilters(source_code="cbn", company_ticker="GTCO")
        derived = base.clone(source_code="nbs")
        assert derived.source_code == "nbs"
        assert derived.company_ticker == "GTCO"
        assert base.source_code == "cbn"  # immutability


class TestTemporalParsing:
    def test_bare_year_sets_full_year_window(self):
        spec = parse_temporal("in 2023")
        assert spec.mode == "during"
        assert spec.after == datetime(2023, 1, 1)
        assert spec.before == datetime(2023, 12, 31, 23, 59, 59)

    def test_historical_kwarg_flips_to_before(self):
        spec = parse_temporal("GDP as of 2020")
        assert spec.mode == "before"
        assert spec.before == datetime(2020, 12, 31, 23, 59, 59)

    def test_between_years(self):
        spec = parse_temporal("between 2022 and 2024")
        assert spec.mode == "between"
        assert spec.after == datetime(2022, 1, 1)
        assert spec.before == datetime(2024, 12, 31, 23, 59, 59)

    def test_month_year_boundary(self):
        spec = parse_temporal("during December 2024")
        assert spec.mode == "during"
        assert spec.after == datetime(2024, 12, 1)
        # month point is not year-boundary, stays as anchor
        assert spec.before == datetime(2024, 12, 1)

    def test_latest_mode(self):
        spec = parse_temporal("what is the latest inflation figure")
        assert spec.mode == "latest"

    def test_none_returns_all(self):
        spec = parse_temporal("how did banks perform last year")
        assert spec.mode == "all"


class TestRRFFusion:
    def test_fuses_and_ranks(self):
        dense = [_item("a", "doc-a"), _item("b", "doc-b")]
        lexical = [_item("b", "doc-b"), _item("c", "doc-c"), _item("a", "doc-a")]
        fused = rrf_fuse({"dense": dense, "lexical": lexical})
        assert [r.chunk_id for r in fused] == ["b", "a", "c"]
        assert fused[0].document_id == "doc-b"
        assert fused[0].ranks == {"dense": 2, "lexical": 1}

    def test_single_list_preserves_order(self):
        fused = rrf_fuse({"dense": [_item("x", "doc-x"), _item("y", "doc-y")]})
        assert [r.chunk_id for r in fused] == ["x", "y"]

    def test_empty_input(self):
        assert rrf_fuse({}) == []
