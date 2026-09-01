"""Research agent node implementations.

Each function is a LangGraph node that reads/mutates ``ResearchState``. The
nodes are deliberately deterministic where possible: the LLM drafts the prose,
but citation extraction and the satisfaction check are rule-based so outputs are
verifiable and reproducible.
"""

from __future__ import annotations

import re
import time

from basechatt.agents.prompts import (
    SYSTEM_RESEARCHER,
    SYSTEM_VERIFIER,
    build_user_prompt,
)
from basechatt.agents.state import Answer, Evidence, ResearchState
from basechatt.llm.factory import get_llm_provider
from basechatt.observability.logging import get_logger
from basechatt.retrieval.filters import RetrievalFilters
from basechatt.retrieval.hybrid import hybrid_search
from basechatt.search.web import needs_web_search, search_web

logger = get_logger("basechatt.agents.tools")

PLAN = """1. Retrieve authoritative evidence covering the question's subject and period.
2. Form an answer strictly from the evidence.
3. Verify every cited fact against its source.
4. State confidence and any uncertainty explicitly."""


def _evidence_from_retrieval(hr) -> list[Evidence]:
    out: list[Evidence] = []
    for sr in hr.results:
        meta = sr.chunk._retrieval or {}
        out.append(
            Evidence(
                chunk_id=sr.chunk.id,
                document_id=meta.get("document_id", ""),
                title=meta.get("title", ""),
                source_code=meta.get("source_code", ""),
                source_name=meta.get("source_name", ""),
                authority_level=meta.get("authority_level", ""),
                text=sr.chunk.text[: 2400],
                published_at=(
                    meta.get("published_at").isoformat()
                    if isinstance(meta.get("published_at"), __import__("datetime").datetime)
                    else None
                ),
                source_url=meta.get("source_url", ""),
                score=sr.score,
            )
        )
    return out


async def retrieve_node(state: ResearchState) -> ResearchState:
    filters = RetrievalFilters()
    if state.company_ticker:
        filters.company_ticker = state.company_ticker
    if state.source_code:
        filters.source_code = state.source_code
    hr = await hybrid_search(state.session, state.query, filters=filters)
    state.retrieval = hr
    state.metadata["evidence_count"] = len(hr.results)
    return state


async def web_search_node(state: ResearchState) -> ResearchState:
    """Search the live web for current information not in the local index."""
    local_count = state.metadata.get("evidence_count", 0)
    query = state.query
    if state.company_ticker:
        query = f"{query} {state.company_ticker}"

    use_web = await needs_web_search(query, local_count)
    state.metadata["web_search_triggered"] = use_web
    if not use_web:
        return state

    logger.info("web search triggered: %r", query)
    response = await search_web(query, max_results=6)
    state.web_evidence = [
        Evidence(
            chunk_id=f"web-{i}",
            document_id=f"web-{i}",
            title=r.title,
            source_code="web",
            source_name="Web Search",
            authority_level="WEB",
            text=r.snippet,
            source_url=r.url,
            score=0.5,
        )
        for i, r in enumerate(response.results)
    ]
    state.metadata["web_result_count"] = len(response.results)
    return state


async def answer_node(state: ResearchState) -> ResearchState:
    local_evidence = _evidence_from_retrieval(state.retrieval) if state.retrieval and state.retrieval.results else []
    web_evidence = state.web_evidence or []
    evidence = local_evidence + web_evidence

    if not evidence:
        state.answer = Answer(
            text="No evidence in the index or web for that yet. Try syncing the sources (`basechatt sync`) or rephrasing the question.",
            is_satisfactory=False,
            evidence=[],
            confidence=0.0,
        )
        return state

    provider = get_llm_provider()
    web_note = ""
    if web_evidence:
        web_note = (
            "\n\nNote: some evidence below comes from a live web search and may not be "
            "authoritative; prefer local indexed sources where they cover the question."
        )
    user = build_user_prompt(state.query, evidence, plan=PLAN) + web_note
    started = time.perf_counter()
    try:
        resp = await provider.chat(SYSTEM_RESEARCHER, user)
    except Exception as e:  # noqa: BLE001
        logger.exception("LLM answer failed: %s", e)
        state.answer = Answer(
            text="The answer could not be generated because the language model "
                 "request failed. Please review the evidence index and try again.",
            is_satisfactory=False,
            evidence=evidence,
            confidence=0.0,
        )
        return state

    answer_text = resp.text
    citations = _extract_citations(answer_text, evidence)

    # Deterministic health checks.
    checks = _health_checks(answer_text, evidence)
    satisfactory = (
        checks["uses_citations"]
        and not checks["no_evidence"]
        and checks["number_claims"] <= len(citations) * 2 + 2
    )

    # Clean LLM artifacts: replace double-question-marks that the LLM uses
    # to render the Nigerian Naira sign (₦) when its tokenizer can't encode it.
    answer_text = _clean_naira(answer_text)

    state.answer = Answer(
        text=answer_text,
        is_satisfactory=satisfactory,
        evidence=evidence,
        confidence=_confidence(answer_text, resp),
        citations=citations,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    state.metadata["local_evidence_count"] = len(local_evidence)
    state.metadata["web_evidence_count"] = len(web_evidence)
    return state


async def verify_node(state: ResearchState) -> ResearchState:
    """Optional LLM verification pass over the draft answer's citations."""
    answer = state.answer
    if not answer or not answer.citations:
        return state
    provider = get_llm_provider()
    evidence_block = "\n\n".join(
        f"[{i+1}] {e.title}: {e.text[:800]}" for i, e in enumerate(answer.evidence)
    )
    user = (
        f"DRAFT ANSWER:\n{answer.text}\n\n"
        f"CITATIONS:\n{answer.citations}\n\n"
        f"EVIDENCE:\n{evidence_block}"
    )
    try:
        resp = await provider.chat(SYSTEM_VERIFIER, user, json_mode=True)
        verdict = _parse_verdict(resp.text)
        answer.is_satisfactory = verdict.get("verdict") in {
            "supported", "partial"
        }
        state.metadata["verify_verdict"] = verdict
    except Exception as e:  # noqa: BLE001
        logger.warning("verification LLM call failed: %s", e)
        state.metadata["verify_verdict"] = {"verdict": "unverified"}
    return state


def _extract_citations(text: str, evidence: list[Evidence]) -> list[dict]:
    """Map inline [n] markers to evidence to build structured citations."""
    if not evidence:
        return []
    indexes = set()
    for m in re.finditer(r"\[(\d{1,3})\]", text):
        idx = int(m.group(1))
        if 1 <= idx <= len(evidence):
            indexes.add(idx)
    citations = []
    seen = set()
    for idx in sorted(indexes):
        ev = evidence[idx - 1]
        if ev.source_url in seen:
            continue
        seen.add(ev.source_url)
        citations.append(ev.to_citation())
    # If the model omitted markers, still list the top evidence as citations so
    # the user has a source trail (the verifier flags unsupported claims).
    for ev in evidence[:5]:
        if ev.source_url not in seen:
            citations.append(ev.to_citation())
            seen.add(ev.source_url)
        if len(citations) >= 8:
            break
    return citations


def _health_checks(text: str, evidence: list[Evidence]) -> dict:
    cites = bool(re.search(r"\[\d{1,3}\]", text))
    number_claims = len(
        re.findall(r"\d[\d,]*\.?\d*\s*(?:%|percent|bn|million|billion|naira|₦|trn)", text)
    )
    no_evidence = len(evidence) == 0
    return {
        "uses_citations": cites,
        "no_evidence": no_evidence,
        "number_claims": number_claims,
    }


def _confidence(text: str, resp) -> float:
    """Heuristic confidence from citation density and hedging language."""
    marker_count = len(re.findall(r"\[\d{1,3}\]", text))
    hedges = len(
        re.findall(r"\b(uncertain|approximately|likely|may|estimate|insufficient)\b", text)
    )
    base = min(0.9, 0.4 + 0.08 * marker_count)
    return max(0.1, round(base - 0.05 * hedges, 2))


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


def _clean_naira(text: str) -> str:
    """Replace LLM artifacts for the Nigerian Naira sign (₦) with the correct character.

    Groq/LLaMA tokenizers struggle with ₦ (U+20A6) and often emit literal
    'N' or '??' placeholders instead. We reverse those substitutions.
    Also strip any stray Unicode replacement characters (U+FFFD).
    """
    if not text:
        return text
    text = text.replace("\ufffd", "")
    text = re.sub(r"(\d+)\s*N(\d)", r"\1₦\2", text)  # "10 N 5" / "10N5" → "10₦5"
    text = re.sub(r"(\d+)\s*\?\?(\d)", r"\1₦\2", text)  # "10??5" → "10₦5"
    text = re.sub(r"\?\s+(\d)", r"₦\1", text)  # "? 5" → "₦5"
    return text
