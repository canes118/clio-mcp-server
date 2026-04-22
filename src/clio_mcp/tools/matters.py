"""FastMCP tool functions for Clio matters."""

from __future__ import annotations

from clio_mcp.auth.models import ClioConfig
from clio_mcp.client import ClioClient
from clio_mcp.models import Matter

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
    return await _get_client().get_matter(matter_id)


async def search_matters(query: str, limit: int = 25) -> list[Matter]:
    """Search for matters by keyword. Matches against matter numbers,
    descriptions, and client names.

    Pass distinctive terms — a company name, person's last name. 
    Do not pass full sentences or predicate expressions.

    Good: "Acme", "Smith"
    Bad: "all Smith matters", "client name contains Acme"

    Returns up to limit matters (default 25, max 100). Passing a limit
    above 100 raises ValueError.
    """
    if limit > 100:
        raise ValueError("limit must be 100 or fewer")
    return await _get_client().search_matters(query, limit)
