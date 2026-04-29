"""Tests for the custom OTel spans emitted by tool handlers.

Asserts the per-tool span name, the clio.tool.* attribute schema, and
the error-path behavior (status=ERROR + recorded exception event).
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from clio_mcp.models import ContactPerson, Matter
from clio_mcp.tools import contacts, matters


@pytest.fixture(scope="module")
def _tracer_provider() -> InMemorySpanExporter:
    """Install a global TracerProvider that captures spans in memory.

    OTel disallows fully replacing a provider once set, so this is
    module-scoped and the per-test fixture clears the exporter between
    runs.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture
def span_exporter(
    _tracer_provider: InMemorySpanExporter,
) -> Iterator[InMemorySpanExporter]:
    _tracer_provider.clear()
    yield _tracer_provider
    _tracer_provider.clear()


def _only_tool_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    spans = [s for s in exporter.get_finished_spans() if s.name.startswith("tool.")]
    assert len(spans) == 1, f"expected exactly one tool span, got {len(spans)}"
    return spans[0]


async def test_get_matter_emits_dict_shape_span(
    span_exporter: InMemorySpanExporter,
) -> None:
    sample = Matter(id=1, display_number="00001-Smith")
    fake_client = AsyncMock()
    fake_client.get_matter.return_value = sample

    with patch.object(matters, "_get_client", return_value=fake_client):
        await matters.get_matter(1)

    span = _only_tool_span(span_exporter)
    assert span.name == "tool.get_matter"
    assert span.attributes is not None
    assert span.attributes["clio.tool.name"] == "get_matter"
    assert span.attributes["clio.tool.args_keys"] == "matter_id"
    assert span.attributes["clio.tool.result.shape"] == "dict"
    assert "clio.tool.result.item_count" not in span.attributes
    assert span.status.status_code != StatusCode.ERROR


async def test_search_contacts_emits_list_shape_span_with_count(
    span_exporter: InMemorySpanExporter,
) -> None:
    fake_client = AsyncMock()
    fake_client.search_contacts.return_value = [
        ContactPerson(id=1, type="Person", first_name="Jane", last_name="Smith"),
        ContactPerson(id=2, type="Person", first_name="John", last_name="Smith"),
    ]

    with patch.object(contacts, "_get_client", return_value=fake_client):
        await contacts.search_contacts("Smith", type="Person", limit=10)

    span = _only_tool_span(span_exporter)
    assert span.name == "tool.search_contacts"
    assert span.attributes is not None
    assert span.attributes["clio.tool.name"] == "search_contacts"
    # Comma-separated, sorted, includes 'type' because it was provided.
    assert span.attributes["clio.tool.args_keys"] == "limit,query,type"
    assert span.attributes["clio.tool.result.shape"] == "list"
    assert span.attributes["clio.tool.result.item_count"] == 2


async def test_search_matters_omits_optional_arg_key_when_absent(
    span_exporter: InMemorySpanExporter,
) -> None:
    fake_client = AsyncMock()
    fake_client.search_matters.return_value = []

    with patch.object(matters, "_get_client", return_value=fake_client):
        await matters.search_matters("Smith", limit=5)

    span = _only_tool_span(span_exporter)
    assert span.attributes is not None
    assert span.attributes["clio.tool.args_keys"] == "limit,query"
    assert span.attributes["clio.tool.result.item_count"] == 0


async def test_search_matters_args_keys_omits_query_when_none(
    span_exporter: InMemorySpanExporter,
) -> None:
    fake_client = AsyncMock()
    fake_client.search_matters.return_value = []

    with patch.object(matters, "_get_client", return_value=fake_client):
        await matters.search_matters(limit=5, status="open")

    span = _only_tool_span(span_exporter)
    assert span.attributes is not None
    assert span.attributes["clio.tool.args_keys"] == "limit,status"


async def test_tool_span_records_exception_and_sets_error_status(
    span_exporter: InMemorySpanExporter,
) -> None:
    fake_client = AsyncMock()
    fake_client.get_matter.side_effect = RuntimeError("clio exploded")

    with (
        patch.object(matters, "_get_client", return_value=fake_client),
        pytest.raises(RuntimeError, match="clio exploded"),
    ):
        await matters.get_matter(42)

    span = _only_tool_span(span_exporter)
    assert span.name == "tool.get_matter"
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes is not None
    assert span.attributes["clio.tool.result.shape"] == "error"
    assert "clio.tool.result.item_count" not in span.attributes

    exception_events = [e for e in span.events if e.name == "exception"]
    assert len(exception_events) == 1
