"""BaseChatt command-line interface.

Run the agent, manage the index, sync sources and drive evaluation from a
terminal. Also the ``basechatt`` console-script entry point (see pyproject).

Usage: ``python -m basechatt.cli <command>`` or ``basechatt <command>``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from basechatt.config.settings import PROJECT_ROOT, get_settings
from basechatt.observability.logging import get_logger

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # pyright: ignore[reportAttributeAccessIssue]
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # pyright: ignore[reportAttributeAccessIssue]

logger = get_logger("basechatt.cli")

EVALUATION_QUESTIONS_PATH = PROJECT_ROOT / "datasets" / "evaluation" / "questions.json"
SOURCES_META = {
    "cbn": "Central Bank of Nigeria",
    "nbs": "National Bureau of Statistics",
    "sec_nigeria": "Securities & Exchange Commission Nigeria",
    "ngx": "Nigerian Exchange",
    "fmdq": "FMDQ Securities Exchange",
    "company_ir": "Nigerian Company Investor Relations",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="basechatt",
        description="BaseChatt — AI financial research analyst for Nigeria.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create the pgvector schema (dev bootstrap).")

    seed = sub.add_parser("seed", help="Load the company universe + sources.")
    seed.add_argument(
        "--companies",
        default=None,
        help="Path to companies.yaml (default: settings.companies_config).",
    )

    sync = sub.add_parser("sync", help="Run ingestion syncs for one or more sources.")
    sync.add_argument("sources", nargs="*", help="Source codes (default: all).")

    sub.add_parser("sync-status", help="Show the latest sync run per source.")

    ask = sub.add_parser("ask", help="Ask the research agent a question.")
    ask.add_argument("query", help="The research question.")
    ask.add_argument("--company", default=None, help="Restrict to a company ticker.")
    ask.add_argument("--source", default=None, help="Restrict to a source code.")
    ask.add_argument("--json", action="store_true", help="Emit the answer as JSON.")

    eval_p = sub.add_parser("eval", help="Run the evaluation harness over seeded questions.")
    eval_p.add_argument("--mock", action="store_true", help="Use the offline mock LLM.")
    eval_p.add_argument("--limit", type=int, default=None, help="Limit number of questions.")
    eval_p.add_argument("--no-persist", action="store_true", help="Do not persist results.")

    seed_eval = sub.add_parser("seed-eval", help="Load evaluation questions into the DB.")
    seed_eval.add_argument("--file", default=str(EVALUATION_QUESTIONS_PATH))

    serve = sub.add_parser("serve", help="Run the FastAPI server (uvicorn).")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    sub.add_parser("doctor", help="Check the environment (DB, provider, config).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler = {
        "init-db": _cmd_init_db,
        "seed": _cmd_seed,
        "sync": _cmd_sync,
        "sync-status": _cmd_sync_status,
        "ask": _cmd_ask,
        "eval": _cmd_eval,
        "seed-eval": _cmd_seed_eval,
        "serve": _cmd_serve,
        "doctor": _cmd_doctor,
    }[args.command]
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:  # noqa: BLE001
        logger.exception("command '%s' failed: %s", args.command, e)
        print(f"error: {e}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _cmd_init_db(args: argparse.Namespace) -> int:
    async def _run() -> None:
        from basechatt.database.session import init_models

        await init_models()

    asyncio.run(_run())
    print("database initialised (pgvector schema created)")
    return 0


def _cmd_seed(args: argparse.Namespace) -> int:
    import yaml

    from basechatt.database.models import Company
    from basechatt.database.repositories import (
        CompanyRepository,
        SourceRepository,
    )
    from basechatt.database.session import SessionLocal
    from basechatt.ingestion.registry import get_connector, list_connector_codes

    companies_path = (
        Path(args.companies)
        if args.companies
        else get_settings().companies_config
    )

    async def _run() -> None:
        with open(companies_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        async with SessionLocal() as session:
            company_repo = CompanyRepository(session)
            companies = [
                Company(
                    ticker=c["ticker"],
                    ngx_symbol=c.get("ngx_symbol", c["ticker"]),
                    name=c["name"],
                    sector=c.get("sector", "other"),
                    ir_url=c.get("ir_url", ""),
                )
                for c in data.get("companies", [])
            ]
            added = await company_repo.upsert_many(companies)

            source_repo = SourceRepository(session)
            for code in list_connector_codes():
                connector = get_connector(code)
                await source_repo.upsert(
                    code=connector.code,
                    name=connector.name,
                    authority_level=connector.authority_level,
                    base_url=getattr(connector, "base_url", ""),
                )
            await session.commit()
            print(f"seeded {added} new companies, refreshed {len(list_connector_codes())} sources")

    asyncio.run(_run())
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    from basechatt.database.session import SessionLocal
    from basechatt.workers.scheduled import sync_sources

    async def _run() -> None:
        async with SessionLocal() as session:
            results = await sync_sources(session, args.sources or None)
        _report_sync_results(results)

    asyncio.run(_run())
    return 0


def _cmd_sync_status(args: argparse.Namespace) -> int:
    from basechatt.database.session import SessionLocal
    from basechatt.workers.scheduled import sync_status

    async def _run() -> None:
        async with SessionLocal() as session:
            status = await sync_status(session)
        for code, run in status["sources"].items():
            print(
                f"{code:<12} {run['status']:<10} "
                f"discovered={run['documents_discovered']} "
                f"added={run['documents_added']} "
                f"updated={run['documents_updated']} "
                f"failed={run['documents_failed']}"
            )
        if not status["sources"]:
            print("no sync runs recorded yet")

    asyncio.run(_run())
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from basechatt.agents.graphs import run_research
    from basechatt.agents.state import ResearchState
    from basechatt.database.session import SessionLocal
    from basechatt.security.sanitize import sanitize_query
    from basechatt.verification import persist_citations, verify_answer

    query = sanitize_query(args.query)
    if query is None:
        print("error: query empty or rejected", file=sys.stderr)
        return 1

    async def _run() -> dict:
        async with SessionLocal() as session:
            state = ResearchState(
                query=query,
                session=session,
                company_ticker=args.company,
                source_code=args.source,
            )
            state = await run_research(state)
            if state.answer is None:
                return {"error": "no answer produced"}
            verdict = await verify_answer(state.answer, state.answer.evidence)
            try:
                await persist_citations(session, state.answer)
            except Exception as e:  # noqa: BLE001
                logger.warning("citation persistence failed: %s", e)
            payload = _answer_payload(state, verdict)
            return payload

    payload = asyncio.run(_run())
    if "error" in payload:
        print(f"error: {payload['error']}", file=sys.stderr)
        return 1
    _print_answer(payload, as_json=args.json)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from basechatt.database.session import SessionLocal
    from basechatt.evaluation.harness import run_evaluation

    async def _run() -> None:
        async with SessionLocal() as session:
            results = await run_evaluation(
                session,
                provider="mock" if args.mock else "default",
                limit=args.limit,
                persist=not args.no_persist,
            )
        _report_evaluation(results)

    asyncio.run(_run())
    return 0


def _cmd_seed_eval(args: argparse.Namespace) -> int:
    from basechatt.database.models import EvaluationQuestion
    from basechatt.database.session import SessionLocal

    path = Path(args.file)
    if not path.exists():
        print(f"error: questions file not found: {path}", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)

    async def _run() -> None:
        count = 0
        async with SessionLocal() as session:
            from sqlalchemy import select

            for row in rows:
                existing = (
                    await session.execute(
                        select(EvaluationQuestion).where(
                            EvaluationQuestion.id == str(row["id"])
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    existing.question = row["question"]
                    existing.category = row.get("category", "general")
                    existing.difficulty = row.get("difficulty", "medium")
                    existing.expected_answer = row.get("expected_answer", "")
                    existing.relevant_document_ids = row.get("relevant_document_ids", [])
                    existing.relevant_chunk_ids = row.get("relevant_chunk_ids", [])
                else:
                    session.add(
                        EvaluationQuestion(
                            id=str(row["id"]),
                            question=row["question"],
                            category=row.get("category", "general"),
                            difficulty=row.get("difficulty", "medium"),
                            expected_answer=row.get("expected_answer", ""),
                            relevant_document_ids=row.get("relevant_document_ids", []),
                            relevant_chunk_ids=row.get("relevant_chunk_ids", []),
                        )
                    )
                    count += 1
            await session.commit()
        print(f"seeded/updated {len(rows)} evaluation questions ({count} new)")

    asyncio.run(_run())
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from basechatt.observability.logging import configure_logging

    configure_logging()
    uvicorn.run(
        "apps.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from basechatt.config.settings import settings

    ok = True

    def _check(label: str, value: str, warn: bool = False) -> None:
        nonlocal ok
        status = "OK" if value else ("warn" if warn else "MISSING")
        if not value:
            ok = ok and warn
        print(f"[{status:<7}] {label}: {value or '-'}")

    _check("app", settings.app_name)
    _check("environment", settings.environment)
    _check("llm provider", settings.llm_provider)
    if settings.llm_provider == "groq":
        _check("GROQ_API_KEY", settings.groq_api_key, warn=True)
    _check("api key", settings.api_key, warn=True)
    _check("database url", settings.database_url.split("@")[-1])
    _check("redis url", settings.redis_url)
    _check("embedding model", settings.embedding_model)
    _check("reranker", settings.reranker_strategy)

    try:
        import basechatt.ingestion.registry  # noqa: F401
        from basechatt.ingestion.registry import list_connector_codes

        _check("connectors", ", ".join(list_connector_codes()))
    except Exception as e:  # noqa: BLE001
        print(f"[FAILED  ] connector registry: {e}")
        ok = False

    print("environment looks healthy" if ok else "several checks need attention")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def _answer_payload(state, verdict) -> dict:
    answer = state.answer
    return {
        "query": state.query,
        "answer": answer.text,
        "confidence": answer.confidence,
        "verdict": verdict.verdict,
        "satisfactory": answer.is_satisfactory,
        "elapsed_ms": round(answer.elapsed_ms, 1),
        "evidence_count": len(answer.evidence),
        "citations": answer.citations,
        "sources": state.retrieval.sources if state.retrieval else [],
    }


def _print_answer(payload: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return
    print("\n" + payload["answer"])
    print(f"\nverdict: {payload['verdict']}  confidence: {payload['confidence']}")
    for i, cite in enumerate(payload["citations"], start=1):
        title = cite.get("title", "")
        url = cite.get("source_url", "")
        print(f"  [{i}] {title} — {url}")


def _report_sync_results(results: dict) -> None:
    for code, res in results.items():
        if res.get("status") == "completed":
            print(
                f"{code:<12} completed  discovered={res['discovered']} "
                f"added={res['added']} updated={res['updated']} failed={res['failed']}"
            )
        else:
            print(f"{code:<12} failed     {res.get('error', 'unknown error')}")


def _report_evaluation(results: dict) -> None:
    agg = results["aggregate"]
    print("aggregate metrics:")
    for name, stats in agg.items():
        print(f"  {name:<16} mean={stats['mean']:.4f}  (n={stats['count']})")
    summary = results["summary"]
    print(f"questions evaluated: {summary['questions_evaluated']}")
    print(f"supported answers:   {summary['supported_count']}")


if __name__ == "__main__":
    raise SystemExit(main())
