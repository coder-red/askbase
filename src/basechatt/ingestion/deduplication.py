"""Content deduplication.

Determines whether a fetched document is NEW, UPDATED, or UNCHANGED based on
its content hash and existing database state. The pipeline calls this before
downloading/processing so unchanged documents are not re-embedded.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.database.models import Document
from basechatt.database.repositories import (
    DocumentRepository,
    DocumentVersionRepository,
)


class ChangeType(enum.StrEnum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"


@dataclass
class DedupDecision:
    change_type: ChangeType
    document: Document | None = None
    existing_hash: str = ""
    new_hash: str = ""


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def decide(
    session: AsyncSession,
    source_id: str,
    external_id: str,
    source_url: str,
    content: bytes,
) -> DedupDecision:
    """Decide whether fetched content represents a new/updated/unchanged doc."""
    doc_repo = DocumentRepository(session)
    version_repo = DocumentVersionRepository(session)

    new_hash = sha256_hex(content)

    # Try external id first, then URL.
    doc = await doc_repo.find_by_external(source_id, external_id)
    if doc is None:
        doc = await doc_repo.find_by_url(source_id, source_url)
        if doc is None:
            return DedupDecision(change_type=ChangeType.NEW, new_hash=new_hash)

    latest = await version_repo.latest(doc.id)
    existing_hash = latest.content_hash if latest else doc.content_hash
    if existing_hash == new_hash:
        return DedupDecision(
            change_type=ChangeType.UNCHANGED,
            document=doc,
            existing_hash=existing_hash,
            new_hash=new_hash,
        )
    return DedupDecision(
        change_type=ChangeType.UPDATED,
        document=doc,
        existing_hash=existing_hash,
        new_hash=new_hash,
    )
