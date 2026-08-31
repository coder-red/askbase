"""Evaluation metrics.

Quantifies retrieval quality and answer faithfulness:

* Retrieval: recall@k (are relevant chunks retrieved) and MRR.
* Answer: cosine/factoid similarity to the expected answer, and rating
  coverage (does the answer reference the right source documents).

All metrics are deterministic given the same inputs so evaluation runs are
reproducible.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence


def recall_at_k(relevant: set[str], retrieved: Sequence[str], k: int | None = None) -> float:
    if k:
        retrieved = list(retrieved)[:k]
    if not relevant:
        return 0.0
    hit = len(set(retrieved) & relevant) / len(relevant)
    return round(hit, 4)


def precision_at_k(relevant: set[str], retrieved: Sequence[str], k: int | None = None) -> float:
    if k:
        retrieved = list(retrieved)[:k]
    if not retrieved:
        return 0.0
    return round(len(set(retrieved) & relevant) / len(retrieved), 4)


def mrr(relevant: set[str], retrieved: Sequence[str]) -> float:
    for i, item in enumerate(retrieved, start=1):
        if item in relevant:
            return round(1.0 / i, 4)
    return 0.0


def f1_at_k(relevant: set[str], retrieved: Sequence[str], k: int | None = None) -> float:
    p = precision_at_k(relevant, retrieved, k)
    r = recall_at_k(relevant, retrieved, k)
    if p + r == 0:
        return 0.0
    return round(2 * p * r / (p + r), 4)


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def token_f1(expected: str, actual: str) -> float:
    e = tokenize(expected)
    a = tokenize(actual)
    if not e or not a:
        return 0.0
    overlap = len(e & a)
    if overlap == 0:
        return 0.0
    p = overlap / len(a)
    r = overlap / len(e)
    return round(2 * p * r / (p + r), 4)


def source_coverage(relevant_docs: set[str], cited_docs: Iterable[str]) -> float:
    """Fraction of the relevant source documents cited by the answer."""
    if not relevant_docs:
        return 0.0
    cited = set(cited_docs)
    return round(len(relevant_docs & cited) / len(relevant_docs), 4)


def aggregate(metric: str, values: list[float]) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }
