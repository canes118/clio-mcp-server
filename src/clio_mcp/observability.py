"""OpenTelemetry tracing setup for the Clio MCP server.

OTel is optional: if the `otel` dependency group is not installed, this
module logs a single warning to stderr and returns. Spans are exported
over OTLP/gRPC; never to stdout, which is the MCP protocol channel.
"""

from __future__ import annotations

import sys

_SERVICE_NAME = "clio-mcp-server"

_configured = False


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
