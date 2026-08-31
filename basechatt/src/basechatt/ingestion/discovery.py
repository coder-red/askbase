"""Discovery wrapper around source connectors.

Runs each connector's ``discover`` and merges results into a flat list of
documents to be processed by the pipeline.
"""

from __future__ import annotations

import asyncio

from basechatt.ingestion.connectors.base import DiscoveredDocument
from basechatt.ingestion.registry import get_connector, list_connector_codes
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.ingestion.discovery")


async def discover_source(source_code: str) -> list[DiscoveredDocument]:
    connector = get_connector(source_code)
    try:
        docs = await connector.discover()
        logger.info("discovered %d documents from %s", len(docs), source_code)
        return docs
    except Exception as e:  # noqa: BLE001
        logger.error("discovery failed for source %s: %s", source_code, e)
        return []


async def discover_all(
    source_codes: list[str] | None = None,
) -> dict[str, list[DiscoveredDocument]]:
    """Discover documents across all (or selected) sources, in parallel."""
    codes = source_codes or list_connector_codes()
    results = await asyncio.gather(*[discover_source(code) for code in codes])
    return dict(zip(codes, results, strict=True))
