"""FastMCP tool functions for Clio matters."""

from __future__ import annotations

from typing import Literal

from clio_mcp.auth.models import ClioConfig
from clio_mcp.client import ClioClient
from clio_mcp.models import Matter
from clio_mcp.observability import Status, StatusCode, trace

tracer = trace.get_tracer(__name__)

_client: ClioClient | None = None


def _get_client() -> ClioClient:
    global _client
    if _client is None:
        _client = ClioClient(ClioConfig.from_env())
    return _client


async def get_matter(matter_id: int) -> Matter:
    """Look up a specific matter by its Clio ID. Returns full details
    including the client, practice area, status, and assigned attorneys.
    Use this when you have a matter's ID and need its details; use
    search_matters instead if you're looking for matters by name,
    client, or keyword.
    """
    with tracer.start_as_current_span(
        "tool.get_matter",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("clio.tool.name", "get_matter")
        span.set_attribute("clio.tool.args_keys", "matter_id")
        try:
            result = await _get_client().get_matter(matter_id)
        except Exception as exc:
            span.set_attribute("clio.tool.result.shape", "error")
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        span.set_attribute("clio.tool.result.shape", "dict")
        return result


async def search_matters(
    query: str | None = None,
    limit: int = 25,
    status: Literal["open", "pending", "closed"] | None = None,
) -> list[Matter]:
    """List matters, optionally filtered by keyword and/or status.
    Both filters are optional — call with neither to list recent
    matters across all statuses, with either to narrow on one
    dimension, or with both to combine.

    query is a keyword search against matter numbers, descriptions,
    and client names. Pass distinctive terms — a company name, a
    person's last name. Do not pass full sentences or predicate
    expressions. Omit query when the user has not named a specific
    matter or party.

    Good: "Acme", "Smith"
    Bad: "all Smith matters", "client name contains Acme"

    status restricts results to matters in that status ("open",
    "pending", or "closed"). Omit it to return matters of all
    statuses.

    Returns up to limit matters (default 25, max 100). Passing a
    limit above 100 raises ValueError.
    """
    args_keys = ["limit"]
    if query is not None:
        args_keys.append("query")
    if status is not None:
        args_keys.append("status")
    with tracer.start_as_current_span(
        "tool.search_matters",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("clio.tool.name", "search_matters")
        span.set_attribute("clio.tool.args_keys", ",".join(args_keys))
        try:
            if limit > 100:
                raise ValueError("limit must be 100 or fewer")
            result = await _get_client().search_matters(query, limit, status)
        except Exception as exc:
            span.set_attribute("clio.tool.result.shape", "error")
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        span.set_attribute("clio.tool.result.shape", "list")
        span.set_attribute("clio.tool.result.item_count", len(result))
        return result
