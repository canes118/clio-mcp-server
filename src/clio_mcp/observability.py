"""OpenTelemetry tracing setup for the Clio MCP server.

OTel is optional: if the `otel` dependency group is not installed, this
module logs a single warning to stderr and returns. Spans are exported
over OTLP/gRPC; never to stdout, which is the MCP protocol channel.

This module also re-exports `trace`, `Status`, and `StatusCode` from
opentelemetry so tool modules can acquire a tracer with a single import.
If OTel is not installed, no-op stand-ins are exported instead so tool
modules remain importable.
"""

from __future__ import annotations

import sys
from typing import Any

_SERVICE_NAME = "clio-mcp-server"

_configured = False


try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
except ImportError:

    class _NoOpSpan:
        def __enter__(self) -> _NoOpSpan:
            return self

        def __exit__(self, *exc_info: object) -> bool:
            return False

        def set_attribute(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_status(self, *args: Any, **kwargs: Any) -> None:
            pass

        def record_exception(self, *args: Any, **kwargs: Any) -> None:
            pass

    class _NoOpTracer:
        def start_as_current_span(
            self, name: str, *args: Any, **kwargs: Any
        ) -> _NoOpSpan:
            return _NoOpSpan()

    class _NoOpTraceModule:
        @staticmethod
        def get_tracer(name: str) -> _NoOpTracer:
            return _NoOpTracer()

        @staticmethod
        def set_tracer_provider(provider: object) -> None:
            pass

    trace = _NoOpTraceModule()  # type: ignore[assignment]

    class StatusCode:  # type: ignore[no-redef]
        ERROR = "ERROR"
        OK = "OK"
        UNSET = "UNSET"

    class Status:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


__all__ = ["Status", "StatusCode", "setup_tracing", "trace"]


def setup_tracing() -> None:
    """Configure global tracing and auto-instrument httpx.

    Idempotent: subsequent calls are no-ops. Must be called before any
    `httpx.AsyncClient` is constructed, since `HTTPXClientInstrumentor`
    patches the module at call time.
    """
    global _configured
    if _configured:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print(
            "clio-mcp-server: OpenTelemetry packages not installed; "
            "tracing disabled. Install the 'otel' dependency group to enable.",
            file=sys.stderr,
        )
        _configured = True
        return

    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()

    _configured = True
