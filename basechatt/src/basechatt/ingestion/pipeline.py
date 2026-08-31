"""Ingestion pipeline.

Orchestrates a full source sync: discover -> fetch -> deduplicate -> store ->
version -> process -> index. Tracks per-source SyncRun statistics and is
fully idempotent (unchanged documents are never re-downloaded/processed).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

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


def _clean_title(title: str, limit: int = 480) -> str:
    """Collapse whitespace and cap length so long page titles never overflow."""
    collapsed = " ".join(title.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1].rstrip() + "\u2026"


async def run_source_sync(session: AsyncSession, source_code: str) -> dict:
    """Run a full sync for one source. Returns summary counters."""
    source_repo = SourceRepository(session)
    company_repo = CompanyRepository(session)
    doc_repo = DocumentRepository(session)
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

    discovered, added, updated, failed = [], 0, 0, 0

    try:
        discovered = await connector.discover()
    except ConnectorError as e:
        logger.error("discovery failed for %s: %s", source_code, e)
        await sync_repo.finish(
            sync_run, SyncStatus.FAILED, failed=1, error=str(e)
        )
        await session.commit()
        return {"source": source_code, "status": "failed", "error": str(e)}

    for doc in discovered:
        try:
            fetched = await connector.fetch(doc)
        except ConnectorError as e:
            logger.warning("fetch failed for %s: %s", doc.url, e)
            failed += 1
            continue

        # Resolve company if this is a company document.
        company = None
        if doc.company_ticker:
            company = await company_repo.get_by_ticker(doc.company_ticker)

        decision = await decide(
            session, source.id, doc.external_id, doc.url, fetched.content
        )

        if decision.change_type == ChangeType.UNCHANGED:
            continue

        # Store raw bytes on disk first.
        raw_rel = ""
        try:
            raw_rel = store_raw(fetched, source_code)
        except Exception as e:  # noqa: BLE001
            logger.error("failed to store raw for %s: %s", doc.url, e)
            failed += 1
            continue

        content_hash = connector.get_content_hash(fetched.content)

        if decision.change_type == ChangeType.NEW:
            document = await doc_repo.create(
                source_id=source.id,
                document_type=doc.document_type,
                title=_clean_title(doc.title or "Untitled"),
                source_url=doc.url,
                external_id=doc.external_id,
                content_hash=content_hash,
                authority_level=doc.authority_level,
                company_id=company.id if company else None,
                published_at=doc.published_at,
                period_start=doc.period_start.date() if doc.period_start else None,
                period_end=doc.period_end.date() if doc.period_end else None,
                effective_date=doc.effective_date,
            )
            added += 1
        else:  # UPDATED
            document = decision.document
            await doc_repo.update_hash(document, content_hash)
            updated += 1

        version = await create_version(
            session, document, content_hash, raw_rel, ProcessingStatus.PENDING
        )
        await session.flush()

        # Process asynchronously but bounded. We inline process to keep the
        # sync deterministic; a failed version marks itself FAILED.
        await process_version(session, version.id)
        await session.commit()

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
