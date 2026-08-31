"""OpenTelemetry-compatible tracing for BaseChatt.

Wraps the OpenTelemetry API so that the rest of the codebase (and the FastAPI
server) can emit spans without hard-coupling to a specific backend. When an
exporter isn't configured the tracer still works (no-op), which keeps local
development dependency-free.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, Span

_tracer_provider: trace.TracerProvider | None = None
_tracer: trace.Tracer | None = None


def init_tracing(service_name: str = "basechatt") -> None:
    """Initialise the global tracer. No-op if OpenTelemetry is already set up.

    To wire an OTLP exporter, configure ``OTEL_EXPORTER_OTLP_ENDPOINT`` and set
    the resource attributes before calling this; by default we use the in-memory
    span processor so spans are still available for tests.
    """
    global _tracer_provider, _tracer
    if _tracer is not None:
        return
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    _tracer = provider.get_tracer(service_name)


def get_tracer():
    if _tracer is None:
        init_tracing()
    return _tracer


class Tracing:
    """Context-manager friendly helper around the OpenTelemetry tracer."""

    def __init__(self, name: str) -> None:
        self.name = name

    @contextlib.contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Iterator[Span]:
        tracer = get_tracer()
        with tracer.start_as_current_span(name) as span:
            if attributes:
                span.set_attributes(attributes)
            yield span

    def get_current_trace_id(self) -> str:
        span = trace.get_current_span()
        if isinstance(span, NonRecordingSpan):
            return ""
        ctx = span.get_span_context()
        return format(ctx.trace_id, "032x") if ctx.trace_id else ""

    def get_current_span_id(self) -> str:
        span = trace.get_current_span()
        if isinstance(span, NonRecordingSpan):
            return ""
        ctx = span.get_span_context()
        return format(ctx.span_id, "016x") if ctx.span_id else ""


tracing = Tracing("basechatt")
