"""Scheduled synchronization entry points.

Thin wrappers around the ingestion pipeline used by the CLI, API, and (optionally)
a background scheduler. Schedules per source are defined in settings; callers can
trigger a one-off sync for any subset of sources.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.database.repositories import SyncRunRepository
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.workers.scheduled")


async def sync_source(session: AsyncSession, source_code: str) -> dict:
    from basechatt.ingestion.pipeline import run_source_sync

    return await run_source_sync(session, source_code)


async def sync_sources(
    session: AsyncSession, source_codes: list[str] | None = None
) -> dict:
    from basechatt.ingestion.pipeline import run_all_syncs

    return await run_all_syncs(session, source_codes)


async def sync_status(session: AsyncSession) -> dict:
    """Return the latest sync run per known source."""
    repo = SyncRunRepository(session)
    runs = await repo.list_runs()
    latest: dict = {}
    for run in runs:
        if run.source_code not in latest:
            latest[run.source_code] = {
                "source_code": run.source_code,
                "status": run.status.value,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "documents_discovered": run.documents_discovered,
                "documents_added": run.documents_added,
                "documents_updated": run.documents_updated,
                "documents_failed": run.documents_failed,
                "error": run.error,
            }
    return {"sources": latest}
