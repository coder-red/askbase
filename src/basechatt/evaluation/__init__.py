"""Evaluation package: metrics + harness for reproducible quality assessment."""

from basechatt.evaluation.harness import QuestionResult, run_evaluation
from basechatt.evaluation.metrics import (
    aggregate,
    f1_at_k,
    mrr,
    precision_at_k,
    recall_at_k,
    source_coverage,
    token_f1,
)

__all__ = [
    "QuestionResult",
    "run_evaluation",
    "aggregate",
    "f1_at_k",
    "mrr",
    "precision_at_k",
    "recall_at_k",
    "source_coverage",
    "token_f1",
]
