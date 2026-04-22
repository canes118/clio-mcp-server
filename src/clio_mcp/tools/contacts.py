"""FastMCP tool functions for Clio contacts."""

from __future__ import annotations

from typing import Literal

from clio_mcp.auth.models import ClioConfig
from clio_mcp.client import ClioClient
from clio_mcp.models import Contact

_client: ClioClient | None = None


def _get_client() -> ClioClient:
    global _client
    if _client is None:
        _client = ClioClient(ClioConfig.from_env())
    return _client


async def get_contact(contact_id: int) -> Contact:
    """Look up a specific contact by its Clio ID. Returns full details
    for the contact — a Person (with name parts, date of birth) or a
    Company (with company name). Use this when you have a contact's ID
    and need its details; use search_contacts instead if you're looking
    for contacts by name or keyword.
    """
    return await _get_client().get_contact(contact_id)


async def search_contacts(
    query: str,
    type: Literal["Person", "Company"] | None = None,
    limit: int = 25,
) -> list[Contact]:
    """Search for contacts by keyword. Matches against names, company
    names, email, and phone.

    Pass distinctive terms — a company name, person's last name.
    Do not pass full sentences or predicate expressions.

    Good: "Acme", "Smith"
    Bad: "all people at Acme", "contacts whose email contains smith"

    type restricts results to one contact kind:
      - "Person" for individuals (clients, opposing parties, witnesses).
      - "Company" for organizations (corporate clients, opposing firms).
    Omit type to return both.

    Returns up to limit contacts (default 25, max 100). Passing a limit
    above 100 raises ValueError.
    """
    if limit > 100:
        raise ValueError("limit must be 100 or fewer")
    return await _get_client().search_contacts(query, type, limit)
