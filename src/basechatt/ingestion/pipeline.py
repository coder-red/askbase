"""Ingestion pipeline.

Orchestrates a full source sync: discover -> fetch -> deduplicate -> store ->
version -> process -> index. Tracks per-source SyncRun statistics and is
fully idempotent (unchanged documents are never re-downloaded/processed).
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.config.settings import settings
from basechatt.database.models import (
    ProcessingStatus,
    SyncStatus,
)
from basechatt.database.repositories import (
    CompanyRepository,
    DocumentRepository,
    SourceRepository,
    SyncRunRepository,
)
from basechatt.ingestion.connectors.base import ConnectorError
from basechatt.ingestion.deduplication import ChangeType, decide
from basechatt.ingestion.downloader import store_raw
from basechatt.ingestion.registry import get_connector
from basechatt.ingestion.versioning import create_version
from basechatt.observability.logging import get_logger
from basechatt.workers.ingestion import process_version

logger = get_logger("basechatt.ingestion.pipeline")

# Per-document processing timeout.  We do this in-process (no worker queue) so
# that one stuck PDF cannot block the whole sync.
DOC_TIMEOUT_SECONDS = 45.0

# Overall per-source sync timeout.  Prevents a source with many slow docs from
# blocking indefinitely.  A timed-out source is marked FAILED.
SOURCE_TIMEOUT_SECONDS = 480.0

# How many documents to process in parallel.  Balance between speed and avoiding
# hammering source servers or exhausting CPU during PDF parsing.
MAX_CONCURRENT_DOCS = 6


def _clean_title(title: str, limit: int = 480) -> str:
    """Collapse whitespace and cap length so long page titles never overflow."""
    collapsed = " ".join(title.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1].rstrip() + "\u2026"


async def run_source_sync(session: AsyncSession, source_code: str) -> dict:
    """Run a full sync for one source. Returns summary counters."""
    try:
        return await asyncio.wait_for(
            _run_source_sync_inner(session, source_code),
            timeout=SOURCE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("sync %s timed out after %.0fs", source_code, SOURCE_TIMEOUT_SECONDS)
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {
            "source": source_code,
            "status": "failed",
            "error": f"source sync timed out after {SOURCE_TIMEOUT_SECONDS:.0f}s",
        }


async def _process_one_doc(
    session: AsyncSession,
    doc,
    connector,
    source_id: str,
    added: list,
    updated: list,
    failed_ref: dict,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        try:
            fetched = await connector.fetch(doc)
        except ConnectorError as e:
            logger.warning("fetch failed for %s: %s", doc.url, e)
            failed_ref["n"] += 1
            return
        except asyncio.TimeoutError:
            logger.warning("fetch timed out for %s", doc.url)
            failed_ref["n"] += 1
            return

        company = None
        if doc.company_ticker:
            from basechatt.database.repositories import CompanyRepository

            company_repo = CompanyRepository(session)
            company = await company_repo.get_by_ticker(doc.company_ticker)

        decision = await decide(
            session, source_id, doc.external_id, doc.url, fetched.content
        )

        if decision.change_type == ChangeType.UNCHANGED:
            return

        raw_rel = ""
        try:
            raw_rel = store_raw(fetched, source_code=connector.code)
        except Exception as e:  # noqa: BLE001
            logger.error("failed to store raw for %s: %s", doc.url, e)
            failed_ref["n"] += 1
            return

        content_hash = connector.get_content_hash(fetched.content)

        period_start = None
        period_end = None
        if doc.published_at:
            period_start = doc.published_at.date()
            period_end = doc.published_at.date()
        elif doc.period_start:
            period_start = doc.period_start.date()
            period_end = doc.period_end.date() if doc.period_end else None

        if decision.change_type == ChangeType.NEW:
            from basechatt.database.repositories import DocumentRepository

            doc_repo = DocumentRepository(session)
            document = await doc_repo.create(
                source_id=source_id,
                document_type=doc.document_type,
                title=_clean_title(doc.title or "Untitled"),
                source_url=doc.url,
                external_id=doc.external_id,
                content_hash=content_hash,
                authority_level=doc.authority_level,
                company_id=company.id if company else None,
                published_at=doc.published_at,
                period_start=period_start,
                period_end=period_end,
                effective_date=doc.effective_date,
            )
            added.append(document.id)
        else:
            from basechatt.database.repositories import DocumentRepository

            doc_repo = DocumentRepository(session)
            document = decision.document
            await doc_repo.update_hash(document, content_hash)
            updated.append(document.id)

        version = await create_version(
            session, document, content_hash, raw_rel, ProcessingStatus.PENDING
        )
        await session.flush()

        try:
            await asyncio.wait_for(
                process_version(session, version.id),
                timeout=DOC_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("process_version timed out for %s", doc.url)
        except Exception as e:  # noqa: BLE001
            logger.warning("process_version failed for %s: %s", doc.url, e)


async def _run_source_sync_inner(session: AsyncSession, source_code: str) -> dict:
    source_repo = SourceRepository(session)
    sync_repo = SyncRunRepository(session)
    connector = get_connector(source_code)

    # Ensure source row exists.
    source = await source_repo.upsert(
        code=connector.code,
        name=connector.name,
        authority_level=connector.authority_level,
        base_url=getattr(connector, "base_url", ""),
    )

    sync_run = await sync_repo.start(source_code)

    try:
        discovered = await connector.discover()
    except ConnectorError as e:
        logger.error("discovery failed for %s: %s", source_code, e)
        await sync_repo.finish(
            sync_run, SyncStatus.FAILED, failed=1, error=str(e)
        )
        await session.commit()
        return {"source": source_code, "status": "failed", "error": str(e)}

    # Fan out all discovered docs in parallel (bounded by semaphore).
    # Each task uses its own DB session so concurrent SQLAlchemy work is safe.
    from basechatt.database.session import SessionLocal

    added_list: list = []
    updated_list: list = []
    failed_ref: dict = {"n": 0}
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOCS)

    async def _run_one(d) -> None:
        async with SessionLocal() as task_session:
            await _process_one_doc(
                task_session,
                d,
                connector,
                source.id,
                added_list,
                updated_list,
                failed_ref,
                sem,
            )
            try:
                await task_session.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning("commit failed for %s: %s", d.url, e)
                await task_session.rollback()

    await asyncio.gather(*[_run_one(d) for d in discovered], return_exceptions=True)
    added = len(added_list)
    updated = len(updated_list)
    failed = failed_ref["n"]

    await sync_repo.finish(
        sync_run,
        SyncStatus.COMPLETED,
        discovered=len(discovered),
        added=added,
        updated=updated,
        failed=failed,
    )
    await session.commit()

    logger.info(
        "sync %s: discovered=%d added=%d updated=%d failed=%d",
        source_code, len(discovered), added, updated, failed,
    )
    return {
        "source": source_code,
        "status": "completed",
        "discovered": len(discovered),
        "added": added,
        "updated": updated,
        "failed": failed,
    }


async def run_all_syncs(session: AsyncSession, source_codes: list[str] | None = None) -> dict:
    """Run syncs across sources sequentially (concurrency yields fairness and
    avoids hammering any single host with simultaneous requests)."""
    from basechatt.ingestion.registry import list_connector_codes

    codes = source_codes or list_connector_codes()
    results: dict = {}
    for code in codes:
        try:
            results[code] = await run_source_sync(session, code)
        except Exception as e:  # noqa: BLE001
            logger.exception("sync failed for %s: %s", code, e)
            results[code] = {"source": code, "status": "failed", "error": str(e)}
    return results
