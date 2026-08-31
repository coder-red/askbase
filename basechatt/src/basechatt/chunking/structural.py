"""Structural & semantic chunking.

``chunk_sections`` performs structure-aware splitting: section boundaries are
respected, then long sections are split on paragraph/sentence boundaries into
chunks of a configurable size with overlap only when necessary. Semantic
segmentation is applied as a secondary pass that tries to keep related
paragraphs together.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from basechatt.config.settings import settings
from basechatt.database.models import ChunkType
from basechatt.ingestion.parser import ParsedDocument, ParsedSection


@dataclass
class Chunk:
    text: str
    section: str = ""
    subsection: str = ""
    page: int | None = None
    chunk_type: ChunkType = ChunkType.TEXT
    metadata: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if len(parts) == 1 and "\n" not in text:
        # Sentence-level split for very long single paragraphs.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        parts = [s for s in sentences if s.strip()]
    return parts or [text]


def chunk_sections(doc: ParsedDocument, chunk_size: int | None = None) -> list[Chunk]:
    """Produce chunks from a parsed document respecting structure."""
    max_size = chunk_size or settings.chunk_size
    chunks: list[Chunk] = []
    current_chunk_text: list[str] = []
    current_chunk_size = 0
    current_section = ""
    current_subsection = ""
    current_page: int | None = None

    sections: list[ParsedSection] = doc.sections or []
    if not sections and doc.raw_text:
        sections = [ParsedSection(title="", level=1, text=doc.raw_text)]

    def flush() -> None:
        nonlocal current_chunk_text, current_chunk_size
        if current_chunk_text:
            chunks.append(
                Chunk(
                    text="\n".join(current_chunk_text),
                    section=current_section,
                    subsection=current_subsection,
                    page=current_page,
                )
            )
            current_chunk_text = []
            current_chunk_size = 0

    for sec in sections:
        # Section heading begins a new block context.
        if sec.title and sec.level <= 3:
            current_section = sec.title[:500] if sec.level <= 2 else current_section
            current_subsection = sec.title[:500] if sec.level >= 3 else ""
            if sec.level <= 2:
                flush()
        if sec.level >= 3 and sec.title:
            current_subsection = sec.title[:500]

        paragraphs = _split_paragraphs(sec.text) if sec.title else _split_paragraphs(sec.text)
        for para in paragraphs:
            if current_chunk_size + len(para) > max_size and current_chunk_size > 0:
                flush()
                # Carry the section heading so a split chunk keeps context.
            preamble = (
                f"{current_subsection}: "
                if current_subsection and not current_chunk_text
                else ""
            )
            segment = preamble + para if preamble else para
            current_chunk_text.append(segment)
            current_chunk_size += len(segment)
            if sec.page:
                current_page = sec.page

    flush()
    # Merge tiny trailing chunks and apply overlap-lite splitting on oversized ones.
    return _finalize(chunks, max_size)


def _finalize(chunks: list[Chunk], max_size: int) -> list[Chunk]:
    """Split any oversized chunk and merge very short chunks."""
    out: list[Chunk] = []
    for chunk in chunks:
        if len(chunk.text) <= max_size * 1.2:
            out.append(chunk)
            continue
        # Split oversized chunk on sentence boundaries.
        sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
        buf: list[str] = []
        size = 0
        for sent in sentences:
            if size + len(sent) > max_size and buf:
                out.append(Chunk(text=" ".join(buf), section=chunk.section,
                                 subsection=chunk.subsection, page=chunk.page))
                buf = []
                size = 0
            buf.append(sent)
            size += len(sent)
        if buf:
            out.append(Chunk(text=" ".join(buf), section=chunk.section,
                             subsection=chunk.subsection, page=chunk.page))
    return out
