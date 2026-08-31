"""Chunking strategy selection.

``build_chunks`` is the single entry point that produces ALL chunks (text +
tables) for a processed document, attaching the provenance metadata that every
chunk must retain (company, document, source, dates, section, document type,
page).
"""

from __future__ import annotations

from basechatt.chunking.structural import chunk_sections
from basechatt.chunking.tables import chunk_tables
from basechatt.database.models import (
    ChunkType,
    Document,
    DocumentChunk,
    DocumentVersion,
    TableRecord,
)
from basechatt.ingestion.parser import ParsedDocument


def build_chunks(
    parsed: ParsedDocument,
    document: Document,
    version: DocumentVersion,
    version_id: str,
    tables: list[TableRecord] | None = None,
) -> list[DocumentChunk]:
    """Create persisted DocumentChunk rows for a parsed document.

    Provenance metadata is attached to each chunk from the document/version so
    retrieval can filter and cite correctly.
    """
    tables = tables or []
    text_chunks = chunk_sections(parsed)
    table_chunks = chunk_tables(tables)

    source_name = getattr(document.source, "name", "") if hasattr(document, "source") else ""

    rows: list[DocumentChunk] = []
    for ch in text_chunks:
        meta = _base_meta(document, source_name)
        meta["chunk_type"] = "text"
        if ch.subsection:
            meta["subsection"] = ch.subsection
        rows.append(
            DocumentChunk(
                version_id=version_id,
                section=ch.section,
                subsection=ch.subsection,
                page=ch.page,
                chunk_type=ChunkType.TEXT,
                text=ch.text,
                published_at=document.published_at,
                effective_date=document.effective_date,
                meta=meta,
            )
        )
    for ch in table_chunks:
        meta = _base_meta(document, source_name)
        meta.update(ch.metadata or {})
        meta["chunk_type"] = "table"
        rows.append(
            DocumentChunk(
                version_id=version_id,
                section=ch.section,
                subsection=ch.subsection,
                page=ch.page,
                chunk_type=ChunkType.TABLE,
                text=ch.text,
                published_at=document.published_at,
                effective_date=document.effective_date,
                meta=meta,
            )
        )
    return rows


def _base_meta(document: Document, source_name: str) -> dict:
    company = getattr(document, "company", None)
    return {
        "document_id": document.id,
        "source_id": document.source_id,
        "source_name": source_name,
        "company_id": document.company_id or "",
        "company_ticker": company.ticker if company else "",
        "document_type": document.document_type.value,
        "title": document.title,
        "authority_level": document.authority_level.value,
    }
