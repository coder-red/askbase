"""Table chunking.

``chunk_tables`` turns each parsed/stored table into a dedicated chunk so the
retrieval engine can retrieve tables independently of ordinary text chunks.
"""

from __future__ import annotations

from basechatt.chunking.structural import Chunk
from basechatt.database.models import ChunkType, TableRecord


def chunk_tables(tables: list[TableRecord], section: str = "") -> list[Chunk]:
    """Create one TABLE chunk per table record."""
    chunks: list[Chunk] = []
    for table in tables:
        text = _table_to_text(table)
        if not text:
            continue
        chunks.append(
            Chunk(
                text=text,
                section=(section or table.section)[:500],
                subsection=table.title[:500],
                page=table.page,
                chunk_type=ChunkType.TABLE,
                metadata={
                    "table_id": table.id,
                    "title": table.title,
                    "headers": table.headers,
                    "currency": table.currency,
                    "units": table.units,
                },
            )
        )
    return chunks


def _table_to_text(table: TableRecord) -> str:
    lines: list[str] = []
    if table.title:
        lines.append(table.title)
    if table.headers:
        lines.append(" | ".join(table.headers))
    for row in table.rows:
        lines.append(" | ".join(str(c) for c in row))
    return "\n".join(lines)
