"""Verification of generated answers against their cited evidence.

Provides both a deterministic suite of checks and an optional LLM-based verdict
pass. Every answer is verified (rule-based) before it is returned; the LLM pass
is a stricter second opinion used by the API when the provider is available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from basechatt.agents.state import Answer, Evidence
from basechatt.llm.base import LLMProvider
from basechatt.observability.logging import get_logger
from basechatt.verification import VERIFIER_SYSTEM

logger = get_logger("basechatt.verification")


@dataclass
class VerificationResult:
    verdict: str  # supported | partial | unsupported | unverifiable
    issues: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    score: float = 0.0
    checks: dict = field(default_factory=dict)
    llm_verdict: str | None = None


async def verify_answer(
    answer: Answer,
    evidence: list[Evidence],
    provider: LLMProvider | None = None,
    run_llm: bool = True,
) -> VerificationResult:
    checks = {
        "has_evidence": len(evidence) > 0,
        "has_citations": len(answer.citations) > 0,
        "citations_traceable": _all_citations_traceable(answer, evidence),
        "has_number_claims": bool(_number_claims(answer.text)),
        "mentions_uncertainty": bool(
            re.search(
                r"\b(uncertain|insufficient|approx|~|may\b|cannot|unable|not available)\b",
                answer.text,
                re.I,
            )
        ),
    }

    issues: list[str] = []
    if not checks["has_evidence"]:
        issues.append("answer produced with no retrieved evidence")
    if not checks["has_citations"]:
        issues.append("answer contains no citations")
    if not checks["citations_traceable"]:
        issues.append("some citations are not traceable to evidence")
    if not answer.text.strip():
        issues.append("answer is empty")

    verdict, score = _deterministic_verdict(checks, issues)

    result = VerificationResult(
        verdict=verdict, issues=issues, score=score, checks=checks
    )

    if run_llm and provider is not None and evidence:
        llm_verdict = await _llm_verdict(provider, answer, evidence)
        result.llm_verdict = llm_verdict.get("verdict")
        merged = _merge_verdicts(result.verdict, llm_verdict.get("verdict"))
        result.verdict = merged
        result.issues.extend(llm_verdict.get("issues", []))
        result.missing.extend(llm_verdict.get("missing", []))

    answer.is_satisfactory = result.verdict in {"supported", "partial"}
    return result


def _deterministic_verdict(checks: dict, issues: list[str]) -> tuple[str, float]:
    if not checks["has_evidence"]:
        return ("unverifiable", 0.0)
    if not checks["has_citations"]:
        return ("unverifiable", 0.1)
    traceable = checks["citations_traceable"] and checks["has_evidence"]
    if not traceable:
        return ("unsupported", 0.2)
    if checks["has_number_claims"] and checks["mentions_uncertainty"]:
        return ("partial", 0.6)
    return ("supported", 0.95)


def _all_citations_traceable(answer: Answer, evidence: list[Evidence]) -> bool:
    known = {ev.source_url for ev in evidence}
    if not known:
        return False
    traceable = 0
    for c in answer.citations:
        if c.get("source_url") and c["source_url"] in known:
            traceable += 1
    return traceable >= max(1, len(answer.citations) // 2)


def _number_claims(text: str) -> list[str]:
    return re.findall(
        r"\d[\d,]*\.?\d*\s*(?:%|percent|bn|million|billion|naira|trn|₦|k|M|%)", text
    )


async def _llm_verdict(
    provider: LLMProvider, answer: Answer, evidence: list[Evidence]
) -> dict:
    evidence_block = "\n\n".join(
        f"[{i+1}] {e.title} ({e.source_code}): {e.text[:700]}"
        for i, e in enumerate(evidence)
    )
    user = (
        f"DRAFT ANSWER:\n{answer.text}\n\n"
        f"CITATIONS:\n{answer.citations}\n\n"
        f"EVIDENCE:\n{evidence_block}"
    )
    try:
        resp = await provider.chat(VERIFIER_SYSTEM, user, json_mode=True)
        return _parse_verdict(resp.text)
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM verification failed: %s", e)
        return {"verdict": "unverified"}


def _parse_verdict(text: str) -> dict:
    import json

    try:
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start : end + 1])
    except Exception:  # noqa: BLE001
        if "supported" in text:
            return {"verdict": "supported"}
        if "partial" in text:
            return {"verdict": "partial"}
        if "unsupported" in text:
            return {"verdict": "unsupported"}
        return {"verdict": "unverifiable"}


def _merge_verdicts(det: str, llm: str | None) -> str:
    if not llm or llm == "unverified":
        return det
    order = ["supported", "partial", "unsupported", "unverifiable"]
    return det if order.index(det) <= order.index(llm) else llm
