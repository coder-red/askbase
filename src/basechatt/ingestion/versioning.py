"""Document versioning.

Ensures historical documents are never overwritten. A changed source document
becomes a new version; the pipeline tracks version numbers per document so both
current and historical states remain queryable.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.database.models import Document, ProcessingStatus
from basechatt.database.repositories import DocumentVersionRepository


async def create_version(
    session: AsyncSession,
    document: Document,
    content_hash: str,
    raw_path: str,
    status: ProcessingStatus = ProcessingStatus.PENDING,
):
    """Create the next version for a document.

    Version numbers increment from the latest existing version (default 1).
    Returns the created DocumentVersion.
    """
    repo = DocumentVersionRepository(session)
    latest = await repo.latest(document.id)
    next_number = (latest.version_number + 1) if latest else 1
    version = await repo.create(
        document_id=document.id,
        content_hash=content_hash,
        version_number=next_number,
        raw_path=raw_path,
        status=status,
    )
    return version
