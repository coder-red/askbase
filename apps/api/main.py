"""BaseChatt FastAPI application.

Exposes the research agent, ingestion syncs, the document/company index and
health/metrics endpoints over HTTP. Run with ``uvicorn apps.api.main:app
--reload`` (or ``make run``).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from apps.api.web import chat_page
from basechatt.agents.graphs import run_research
from basechatt.agents.state import ResearchState
from basechatt.config.settings import settings
from basechatt.database.models import (
    DocumentType,
    EvaluationResult,
)
from basechatt.database.repositories import (
    CompanyRepository,
    DocumentRepository,
    SourceRepository,
)
from basechatt.database.session import SessionLocal
from basechatt.observability import metrics
from basechatt.observability.logging import configure_logging, get_logger
from basechatt.security.auth import validate_api_key
from basechatt.security.ratelimit import limiter
from basechatt.security.sanitize import sanitize_query
from basechatt.tools import calculations
from basechatt.verification import persist_citations, verify_answer
from basechatt.workers.scheduled import sync_source, sync_sources, sync_status

configure_logging()
logger = get_logger("basechatt.api")

app = FastAPI(
    title=f"{settings.app_name} API",
    description="AI financial research agent for Nigeria.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
API_PREFIX = "/api/v1"


# ---------------------------------------------------------------------------
# Security / rate limiting
# ---------------------------------------------------------------------------


def _client_key(request: Request) -> str:
    key = request.headers.get("X-API-Key")
    if key:
        return f"key:{key}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


async def require_auth(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> None:
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    if not limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="rate limit exceeded")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    company_ticker: str | None = None
    source_code: str | None = None


class SyncRequest(BaseModel):
    source_codes: list[str] | None = None


class CalculateRequest(BaseModel):
    current: float
    previous: float = 0.0
    years: float | None = None
    operation: str = Field(
        "growth", pattern="^(growth|yoy|cagr|margin|ratio|compare)$"
    )


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    provider: str
    database: str


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _answer_payload(state: ResearchState) -> dict[str, Any]:
    answer = state.answer
    assert answer is not None
    import dataclasses
    sources_raw = state.retrieval.sources if state.retrieval else []
    sources = [dataclasses.asdict(s) if dataclasses.is_dataclass(s) and not isinstance(s, dict) else s for s in sources_raw]
    return {
        "query": state.query,
        "answer": answer.text,
        "is_satisfactory": answer.is_satisfactory,
        "confidence": answer.confidence,
        "uncertainty": answer.uncertainty,
        "elapsed_ms": round(answer.elapsed_ms, 1),
        "citations": answer.citations,
        "evidence": [asdict(e) for e in answer.evidence],
        "follow_up_queries": answer.follow_up_queries,
        "sources": sources,
    }


def _document_payload(doc) -> dict[str, Any]:
    return {
        "id": doc.id,
        "document_type": doc.document_type,
        "title": doc.title,
        "source_url": doc.source_url,
        "external_id": doc.external_id,
        "published_at": doc.published_at,
        "period_start": doc.period_start,
        "period_end": doc.period_end,
        "authority_level": doc.authority_level,
        "company_id": doc.company_id,
        "source_id": doc.source_id,
    }


def _company_payload(company) -> dict[str, Any]:
    return {
        "id": company.id,
        "ticker": company.ticker,
        "ngx_symbol": company.ngx_symbol,
        "name": company.name,
        "sector": company.sector,
        "ir_url": company.ir_url,
    }


def _source_payload(source) -> dict[str, Any]:
    return {
        "id": source.id,
        "code": source.code,
        "name": source.name,
        "authority_level": str(source.authority_level),
        "base_url": source.base_url,
        "is_primary": source.is_primary,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    db = "unreachable"
    try:
        async with SessionLocal() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
            db = "ok"
    except Exception as e:  # noqa: BLE001
        logger.warning("health check: database unreachable: %s", e)
    return HealthResponse(
        status="ok" if db == "ok" else "degraded",
        app=settings.app_name,
        environment=settings.environment,
        provider=settings.llm_provider,
        database=db,
    )


@app.post(f"{API_PREFIX}/query", tags=["research"], dependencies=[Depends(require_auth)])
async def query(body: QueryRequest) -> dict[str, Any]:
    query_text = sanitize_query(body.query)
    if query_text is None:
        raise HTTPException(status_code=400, detail="query rejected or empty")

    with metrics.Timer("api.query.latency"):
        async with SessionLocal() as session:
            state = ResearchState(
                query=query_text,
                session=session,
                company_ticker=body.company_ticker,
                source_code=body.source_code,
            )
            try:
                state = await run_research(state)
            except Exception as e:  # noqa: BLE001
                logger.exception("research failed: %s", e)
                raise HTTPException(status_code=500, detail="research failed") from e
            if state.answer is None:
                raise HTTPException(status_code=500, detail="no answer produced")

            verdict = await verify_answer(state.answer, state.answer.evidence)
            try:
                await persist_citations(session, state.answer)
            except Exception as e:  # noqa: BLE001
                logger.warning("citation persistence failed: %s", e)

    metrics.increment("api.query.requests")
    payload = _answer_payload(state)
    payload["verdict"] = asdict(verdict)
    return payload


@app.get(f"{API_PREFIX}/sync/status", tags=["ingestion"], dependencies=[Depends(require_auth)])
async def get_sync_status() -> dict[str, Any]:
    async with SessionLocal() as session:
        return await sync_status(session)


@app.post(f"{API_PREFIX}/sync", tags=["ingestion"], dependencies=[Depends(require_auth)])
async def run_sync(body: SyncRequest) -> dict[str, Any]:
    async with SessionLocal() as session:
        results = await sync_sources(session, body.source_codes)
    return {"results": results}


@app.post(
    f"{API_PREFIX}/sync/{{source}}",
    tags=["ingestion"],
    dependencies=[Depends(require_auth)],
)
async def run_single_sync(source: str) -> dict[str, Any]:
    async with SessionLocal() as session:
        result = await sync_source(session, source)
    return {"source": source, "result": result}


@app.get(f"{API_PREFIX}/documents", tags=["index"], dependencies=[Depends(require_auth)])
async def list_documents(
    source_code: str | None = None,
    company_id: str | None = None,
    document_type: DocumentType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    async with SessionLocal() as session:
        repo = DocumentRepository(session)
        docs = await repo.list_documents(
            source_code=source_code,
            company_id=company_id,
            document_type=document_type,
            limit=limit,
            offset=offset,
        )
        total = len(docs)
        return {
            "count": total,
            "limit": limit,
            "offset": offset,
            "documents": [_document_payload(d) for d in docs],
        }


@app.get(f"{API_PREFIX}/companies", tags=["index"], dependencies=[Depends(require_auth)])
async def list_companies() -> dict[str, Any]:
    async with SessionLocal() as session:
        companies = await CompanyRepository(session).list_all()
    return {
        "count": len(companies),
        "companies": [_company_payload(c) for c in companies],
    }


@app.get(f"{API_PREFIX}/sources", tags=["index"], dependencies=[Depends(require_auth)])
async def list_sources() -> dict[str, Any]:
    async with SessionLocal() as session:
        sources = await SourceRepository(session).list_all()
    return {"count": len(sources), "sources": [_source_payload(s) for s in sources]}


@app.get(f"{API_PREFIX}/metrics", tags=["ops"], dependencies=[Depends(require_auth)])
async def get_metrics() -> dict[str, Any]:
    return metrics.summary()


@app.post(
    f"{API_PREFIX}/calculate",
    tags=["tools"],
    dependencies=[Depends(require_auth)],
)
async def calculate(body: CalculateRequest) -> dict[str, Any]:
    fn = {
        "growth": calculations.calculate_growth,
        "yoy": calculations.calculate_yoy,
        "margin": calculations.calculate_margin,
        "ratio": calculations.calculate_ratio,
        "compare": calculations.compare_periods,
    }[body.operation]
    if body.operation == "cagr":
        result = calculations.calculate_cagr(
            body.current, body.previous, body.years or 1
        )
    else:
        result = fn(body.current, body.previous)
    return result.to_dict()


@app.get(
    f"{API_PREFIX}/evaluation/results",
    tags=["evaluation"],
    dependencies=[Depends(require_auth)],
)
async def evaluation_results() -> dict[str, Any]:
    from sqlalchemy import select

    async with SessionLocal() as session:
        res = (
            await session.execute(
                select(EvaluationResult).order_by(EvaluationResult.created_at.desc())
            )
        ).scalars().all()
    return {
        "count": len(res),
        "results": [
            {"method": r.method, "metrics": r.metrics, "created_at": r.created_at}
            for r in res
        ],
    }


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return chat_page()


if __name__ == "__main__":
    import sys

    import uvicorn

    if str(settings.location.parents[3]) not in sys.path:
        sys.path.insert(0, str(settings.location.parents[3]))
    uvicorn.run("apps.api.main:app", reload=True)
