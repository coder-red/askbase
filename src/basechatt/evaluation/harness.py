"""Evaluation harness.

Runs a corpus of curated evaluation questions through the research pipeline and
measures retrieval quality (recall@k / MRR) and answer faithfulness (token-F1,
source coverage), then writes an aggregate ``EvaluationResult`` row.

Used by ``basechatt eval`` to give a reproducible quality signal without a
human grader.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.agents.graphs import run_research
from basechatt.agents.state import ResearchState
from basechatt.config.settings import Settings
from basechatt.database.models import EvaluationQuestion, EvaluationResult
from basechatt.evaluation.metrics import (
    aggregate,
    mrr,
    recall_at_k,
    source_coverage,
    token_f1,
)
from basechatt.llm.factory import get_llm_provider
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.evaluation.harness")


@dataclass
class QuestionResult:
    question: str
    category: str
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mrr: float = 0.0
    f1: float = 0.0
    source_coverage: float = 0.0
    verdict: str = ""
    answer: str = ""
    error: str = ""


async def run_evaluation(
    session: AsyncSession,
    provider: str = "default",
    limit: int | None = None,
    persist: bool = True,
) -> dict:
    """Evaluate the pipeline over the curated question corpus.

    ``provider`` selects which settings slice to use: "default" (the configured
    provider), or "mock" to run without any external API calls.
    """
    cfg = (
        Settings(llm_provider="mock", environment="test")
        if provider == "mock"
        else Settings()
    )
    llm = get_llm_provider(cfg)

    stmt = select(EvaluationQuestion).order_by(EvaluationQuestion.id)
    if limit:
        stmt = stmt.limit(limit)
    res = await session.execute(stmt)
    questions = list(res.scalars().all())

    results: list[QuestionResult] = []
    for q in questions:
        r = await _evaluate_one(session, q, llm)
        results.append(r or QuestionResult(question=q.question, category=q.category))

    agg = {
        "recall@5": aggregate("recall@5", [x.recall_at_5 for x in results]),
        "recall@10": aggregate("recall@10", [x.recall_at_10 for x in results]),
        "mrr": aggregate("mrr", [x.mrr for x in results]),
        "f1": aggregate("f1", [x.f1 for x in results]),
        "source_coverage": aggregate(
            "source_coverage", [x.source_coverage for x in results]
        ),
    }
    summary = {
        "questions_evaluated": len(results),
        "supported_count": sum(1 for x in results if x.verdict == "supported"),
    }

    if persist:
        import hashlib

        rid = hashlib.sha256(f"{cfg.llm_provider}:{len(results)}".encode()).hexdigest()[:16]
        existing = (
            await session.execute(
                select(EvaluationResult).where(
                    EvaluationResult.id == rid, EvaluationResult.method == cfg.llm_provider
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.metrics = {"aggregate": agg, "summary": summary}
        else:
            session.add(
                EvaluationResult(
                    id=rid,
                    method=cfg.llm_provider,
                    metrics={"aggregate": agg, "summary": summary},
                )
            )
        await session.commit()

    return {
        "aggregate": agg,
        "summary": summary,
        "per_question": [
            {
                "question": x.question,
                "category": x.category,
                "recall@5": x.recall_at_5,
                "recall@10": x.recall_at_10,
                "mrr": x.mrr,
                "f1": x.f1,
                "source_coverage": x.source_coverage,
                "verdict": x.verdict,
            }
            for x in results
        ],
    }


async def _evaluate_one(session, q, llm) -> QuestionResult | None:
    state = ResearchState(query=q.question, session=session)
    try:
        finished = await run_research(state)
        answer = finished.answer
        evidence = answer.evidence if answer else []
        retrieved_docs = [ev.document_id for ev in evidence]
        relevant_docs = set(q.relevant_document_ids or [])
        relevant_ids = set(q.relevant_chunk_ids or [])
        cited_docs = {c.get("source_url") for c in (answer.citations if answer else [])}
        return QuestionResult(
            question=q.question,
            category=q.category,
            recall_at_5=recall_at_k(relevant_ids, retrieved_docs, 5),
            recall_at_10=recall_at_k(relevant_ids, retrieved_docs, 10),
            mrr=mrr(relevant_ids, retrieved_docs),
            f1=token_f1(q.expected_answer or "", answer.text if answer else ""),
            source_coverage=source_coverage(relevant_docs, cited_docs),
            verdict=(
                "supported"
                if (answer and answer.is_satisfactory)
                else "not_satisfactory"
            ),
            answer=(answer.text[:200] if answer else ""),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("evaluation error for %s: %s", q.question, e)
        return QuestionResult(
            question=q.question, category=q.category, error=str(e), verdict="error"
        )
