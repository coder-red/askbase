"""Registry mapping source codes to connector classes.

New connectors can be added by registering them here without touching the
pipeline or retrieval layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basechatt.ingestion.connectors.base import SourceConnector

_REGISTRY: dict[str, type[SourceConnector]] = {}


def register(cls: type[SourceConnector]) -> type[SourceConnector]:
    _REGISTRY[cls.code] = cls
    return cls


def get_connector(code: str, session=None) -> SourceConnector:
    cls = _REGISTRY.get(code)
    if cls is None:
        raise KeyError(f"No connector registered for source code: {code}")
    return cls()


def list_connector_codes() -> list[str]:
    return sorted(_REGISTRY.keys())


# Import connectors so their @register decorators run.
from basechatt.ingestion.connectors import (  # noqa: E402,F401
    cbn,
    company_ir,
    fmdq,
    nbs,
    ngx,
    sec_nigeria,
)
