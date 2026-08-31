"""Unit tests for the evaluation metrics."""

from __future__ import annotations

from basechatt.evaluation.metrics import (
    aggregate,
    f1_at_k,
    mrr,
    precision_at_k,
    recall_at_k,
    source_coverage,
    token_f1,
)


class TestRetrievalMetrics:
    def test_recall_at_k_hits(self):
        assert recall_at_k({"a", "b"}, ["a", "x", "y", "b"], k=3) == 0.5
        assert recall_at_k({"a"}, ["a"], k=1) == 1.0
        assert recall_at_k({"a"}, ["none"], k=5) == 0.0

    def test_recall_empty_relevant_is_zero(self):
        assert recall_at_k(set(), ["a"], k=5) == 0.0

    def test_precision_at_k(self):
        assert precision_at_k({"a", "b"}, ["a", "x"], k=2) == 0.5

    def test_f1_at_k(self):
        # p=0.5, r=0.5 -> f1 = 0.5
        assert f1_at_k({"a", "b"}, ["a", "x"], k=2) == 0.5
        # all relevant retrieved at k -> f1 = 1.0
        assert f1_at_k({"a", "b"}, ["a", "b", "x"], k=2) == 1.0

    def test_mrr_first_relevant_rank(self):
        assert mrr({"b"}, ["a", "b", "c"]) == 0.5
        assert mrr({"x"}, ["a", "b"]) == 0.0

    def test_mrr_rank_one(self):
        assert mrr({"a"}, ["a", "b", "c"]) == 1.0


class TestAnswerMetrics:
    def test_token_f1_perfect_overlap(self):
        assert token_f1("access holdings gross earnings", "access holdings gross earnings") == 1.0

    def test_token_f1_no_overlap(self):
        assert token_f1("inflation rate", "banana harvest") == 0.0

    def test_token_f1_partial(self):
        f = token_f1("real gdp growth 2024", "gdp growth was strong")
        assert 0.0 < f < 1.0

    def test_token_f1_empty_actual(self):
        assert token_f1("anything", "") == 0.0

    def test_source_coverage(self):
        assert source_coverage({"a", "b"}, ["a", "x"]) == 0.5
        assert source_coverage({"a"}, []) == 0.0
        assert source_coverage(set(), ["a"]) == 0.0

    def test_aggregate(self):
        stats = aggregate("recall@5", [0.5, 1.0, 0.0])
        assert stats["count"] == 3
        assert stats["mean"] == 0.5
        assert stats["min"] == 0.0
        assert stats["max"] == 1.0

    def test_aggregate_empty_values(self):
        stats = aggregate("f1", [])
        assert stats["count"] == 0
        assert stats["mean"] == 0.0
