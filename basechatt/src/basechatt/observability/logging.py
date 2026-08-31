"""Structured JSON logging for BaseChatt.

Every log record is emitted as a single JSON line carrying structured fields
such as ``request_id`` and ``trace_id`` so they can be correlated and shipped
to a log aggregator. Never log secrets.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Mapping
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "fields", {}).items():
            payload[key] = value
        return json.dumps(payload, default=str)


class FieldsFilter(logging.Filter):
    """Attach contextual fields stored on the logger via extra={...}."""

    def filter(self, record: logging.LogRecord) -> bool:
        fields = getattr(record, "fields", None)
        if fields is None:
            record.fields = {}  # type: ignore[attr-defined]
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger to emit structured JSON lines."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(FieldsFilter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger that emits structured JSON records."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that lets callers pass structured fields in one dict."""

    def process(self, msg: Any, kwargs: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
        extra = dict(kwargs.get("extra", {}))
        fields = extra.get("fields", {})
        extra["fields"] = fields
        kwargs = dict(kwargs)
        kwargs["extra"] = extra
        return msg, kwargs


def start_span_id() -> str:
    return uuid.uuid4().hex[:16]
