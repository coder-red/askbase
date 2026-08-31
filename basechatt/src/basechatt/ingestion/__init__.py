"""Ingestion package: connectors, discovery, download, parsing, processing."""

from basechatt.ingestion.connectors.base import (
    ConnectorError,
    DiscoveredDocument,
    SourceConnector,
)
from basechatt.ingestion.registry import get_connector, list_connector_codes

__all__ = [
    "ConnectorError",
    "DiscoveredDocument",
    "SourceConnector",
    "get_connector",
    "list_connector_codes",
]
