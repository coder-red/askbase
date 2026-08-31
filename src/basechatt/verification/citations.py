"""Persist verified citations to the database.

When an answer is produced, its citations (document id + snippet + source url)
are written to the ``citations`` table so research outputs are auditable and
reusable — the API can return stable citation ids pointing at the exact evidence
chunks that supported each claim.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from basechatt.agents.state import Answer, Evidence
from basechatt.database.repositories import CitationRepository
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.verification.citations")


async def persist_citations(
    session: AsyncSession,
    answer: Answer,
) -> list[str]:
    """Write the answer's citations to DB. Returns list of citation ids.

    Only citations whose evidence is traceable to a real chunk are persisted;
    free-form "sources" are ignored to keep the citation graph trustworthy.
    """
    if not answer or not answer.citations:
        return []

    ev_by_doc: dict[str, Evidence] = {}
    for ev in answer.evidence:
        ev_by_doc[ev.document_id] = ev

    repo = CitationRepository(session)
    citation_ids: list[str] = []
    for cite in answer.citations:
        doc_id = cite.get("document_id")
        ev = ev_by_doc.get(doc_id)
        if ev is None:
            continue
        citation = await repo.create(
            document_id=doc_id,
            chunk_id=ev.chunk_id,
            version_id=None,
            section=cite.get("section", ""),
            source_url=cite.get("source_url", ""),
            snippet=ev.text[:600],
            published_at=_parse_dt(ev.published_at),
        )
        citation_ids.append(citation.id)
    await session.commit()
    logger.info("persisted %d citations", len(citation_ids))
    return citation_ids


def _parse_dt(value):
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
