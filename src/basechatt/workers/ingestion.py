"""Single-document ingestion worker.

Processes one document version through the full pipeline:
parse -> extract tables -> extract metadata -> normalize -> chunk ->
persist -> embed -> index. Each stage is idempotent: old chunks/tables for the
version are cleared first so a retry never leaves partial state.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.chunking.strategy import build_chunks
from basechatt.database.models import (
    Document,
    ProcessingStatus,
    Source,
)
from basechatt.database.repositories import (
    ChunkRepository,
    DocumentVersionRepository,
    IngestionJobRepository,
    TableRepository,
)
from basechatt.ingestion.downloader import raw_path_to_abs
from basechatt.ingestion.metadata import (
    extract_date,
    extract_period,
)
from basechatt.ingestion.parser import parse_bytes
from basechatt.ingestion.tables import normalize_table
from basechatt.observability.logging import get_logger
from basechatt.workers.indexing import embed_and_index_version

logger = get_logger("basechatt.workers.ingestion")


async def process_version(session: AsyncSession, version_id: str) -> str:
    """Process a single document version end-to-end.

    Returns a ProcessingStatus string (COMPLETED/FAILED).
    """
    version_repo = DocumentVersionRepository(session)
    version = await version_repo.get(version_id)
    if version is None:
        return ProcessingStatus.FAILED.value

    job_repo = IngestionJobRepository(session)
    job = await job_repo.create(
        document_id=version.document_id,
        version_id=version_id,
        stage="parse",
        status=ProcessingStatus.PROCESSING,
    )

    try:
        # Load document + source with relationships.
        res = await session.execute(
            select(Document).where(Document.id == version.document_id)
        )
        document = res.scalar_one_or_none()
        if document is None:
            await job_repo.fail(job, "document not found")
            return ProcessingStatus.FAILED.value
        src_res = await session.execute(
            select(Source).where(Source.id == document.source_id)
        )
        source = src_res.scalar_one_or_none()

        # 1. Read raw content.
        raw_path = raw_path_to_abs(version.raw_path)
        content = raw_path.read_bytes()

        # 2. Parse.
        parsed = parse_bytes(content, _infer_mime(raw_path))

        # 3. Extract / normalise tables -> persist.
        table_records = [
            normalize_table(t, document.id, version_id) for t in parsed.tables
        ]
        table_repo = TableRepository(session)
        await table_repo.bulk_insert(table_records)

        # 4. Metadata extraction (deterministic).
        if document.published_at is None and parsed.raw_text:
            document.published_at = extract_date(parsed.title + " " + parsed.raw_text)
        period_start, period_end = extract_period(parsed.raw_text + " " + parsed.title)
        if document.period_start is None and period_start:
            document.period_start = period_start.date()
        if document.period_end is None and period_end:
            document.period_end = period_end.date()
        if source:
            document.source = source

        # 5. Normalize + chunk.
        chunks = build_chunks(parsed, document, version, version_id, table_records)

        # 6. Clear old chunks for this version (idempotency), then persist.
        chunk_repo = ChunkRepository(session)
        await chunk_repo.delete_for_version(version_id)
        await chunk_repo.bulk_insert(chunks)
        await session.flush()

        # 7. Embed + index (embedding failure is isolated to status FAILED).
        await embed_and_index_version(session, version_id)

        await job_repo.complete(job)
        logger.info("version %s processed (%d chunks)", version_id, len(chunks))
        return ProcessingStatus.COMPLETED.value

    except Exception as e:  # noqa: BLE001
        logger.exception("processing failed for version %s: %s", version_id, e)
        await job_repo.fail(job, str(e))
        await version_repo.set_status(version_id, ProcessingStatus.FAILED, str(e))
        return ProcessingStatus.FAILED.value


def _infer_mime(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith((".html", ".htm")):
        return "text/html"
    return "application/octet-stream"
