"""Tests for the contacts tool functions.

These tests verify only the thin delegation layer; HTTP behavior is
exercised in tests/test_client.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from clio_mcp.models import ContactCompany, ContactPerson
from clio_mcp.tools import contacts


@pytest.fixture
def sample_person() -> ContactPerson:
    return ContactPerson(id=501, type="Person", first_name="Jane", last_name="Smith")


@pytest.fixture
def sample_company() -> ContactCompany:
    return ContactCompany(id=502, type="Company", name="Acme LLC")


async def test_get_contact_delegates_to_client(sample_person: ContactPerson) -> None:
    fake_client = AsyncMock()
    fake_client.get_contact.return_value = sample_person

    with patch.object(contacts, "_get_client", return_value=fake_client):
        result = await contacts.get_contact(501)

    fake_client.get_contact.assert_awaited_once_with(501)
    assert result is sample_person


async def test_get_contact_returns_company(sample_company: ContactCompany) -> None:
    fake_client = AsyncMock()
    fake_client.get_contact.return_value = sample_company

    with patch.object(contacts, "_get_client", return_value=fake_client):
        result = await contacts.get_contact(502)

    assert result is sample_company


async def test_search_contacts_delegates_without_type(
    sample_person: ContactPerson,
) -> None:
    fake_client = AsyncMock()
    fake_client.search_contacts.return_value = [sample_person]

    with patch.object(contacts, "_get_client", return_value=fake_client):
        result = await contacts.search_contacts("Smith", limit=10)

    fake_client.search_contacts.assert_awaited_once_with("Smith", None, 10)
    assert result == [sample_person]


async def test_search_contacts_passes_type_filter(
    sample_company: ContactCompany,
) -> None:
    fake_client = AsyncMock()
    fake_client.search_contacts.return_value = [sample_company]

    with patch.object(contacts, "_get_client", return_value=fake_client):
        result = await contacts.search_contacts("Acme", type="Company", limit=5)

    fake_client.search_contacts.assert_awaited_once_with("Acme", "Company", 5)
    assert result == [sample_company]


async def test_search_contacts_rejects_limit_above_100() -> None:
    with pytest.raises(ValueError, match="100"):
        await contacts.search_contacts("Smith", limit=101)
