"""Raw document downloader and local filesystem storage."""

from __future__ import annotations

import re
from pathlib import Path

from basechatt.config.settings import settings
from basechatt.ingestion.connectors.base import FetchedDocument
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.ingestion.downloader")


def _sanitize(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name.strip("_")[:120]


def store_raw(doc: FetchedDocument, source_code: str) -> str:
    """Write raw bytes to data/raw/{source}/{...} and return the relative path."""
    root = settings.raw_dir / _sanitize(source_code)
    root.mkdir(parents=True, exist_ok=True)
    filename = _sanitize(doc.filename) or "document"
    if not filename.endswith((".pdf", ".html", ".htm", ".xml", ".txt")):
        ext = ".pdf" if "pdf" in doc.mime_type else ".html"
        filename += ext
    path = root / filename
    path.write_bytes(doc.content)
    rel = path.relative_to(settings.data_dir)
    logger.info("stored raw document %s -> %s", doc.discovered.external_id, rel)
    return str(rel)


def raw_path_to_abs(rel: str) -> Path:
    return settings.data_dir / rel
