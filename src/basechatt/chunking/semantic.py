"""Semantic chunking strategy.

A lightweight semantic segmentation that groups consecutive paragraphs whose
content is closely related using lexical-overlap similarity as a proxy for
topical cohesion, then fuses them into chunks bounded by size. This avoids the
heavyweight cost of re-embedding at chunk time while still producing
topically-coherent segments.
"""

from __future__ import annotations

import re

from basechatt.chunking.structural import Chunk
from basechatt.config.settings import settings
from basechatt.database.models import ChunkType


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def chunk_semantic(
    paragraphs: list[str],
    chunk_size: int | None = None,
    section: str = "",
    subsection: str = "",
) -> list[Chunk]:
    """Group paragraphs into semantically-coherent, size-bounded chunks."""
    max_size = chunk_size or settings.chunk_size
    groups: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    prev_tokens: set[str] = set()

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        tokens = _tokenize(para)
        # Start a new group on topic shift or size limit.
        topic_shift = _jaccard(prev_tokens, tokens) < 0.05
        size_exceeded = current_size + len(para) > max_size
        if current and (topic_shift or size_exceeded):
            groups.append(current)
            current = []
            current_size = 0
        current.append(para)
        current_size += len(para)
        prev_tokens = tokens

    if current:
        groups.append(current)

    chunks = []
    for group in groups:
        text = " ".join(group)
        if len(text) > max_size * 1.2:
            for sub in _split_by_size(text, max_size):
                chunks.append(Chunk(text=sub, section=section, subsection=subsection,
                                    chunk_type=ChunkType.TEXT))
        else:
            chunks.append(Chunk(text=text, section=section, subsection=subsection,
                                chunk_type=ChunkType.TEXT))
    return chunks


def _split_by_size(text: str, max_size: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for s in sentences:
        if size + len(s) > max_size and buf:
            out.append(" ".join(buf))
            buf = []
            size = 0
        buf.append(s)
        size += len(s)
    if buf:
        out.append(" ".join(buf))
    return out
