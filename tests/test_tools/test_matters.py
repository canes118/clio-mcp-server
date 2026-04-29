"""Tests for the matters tool functions.

These tests verify only the thin delegation layer; HTTP behavior is
exercised in tests/test_client.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from clio_mcp.models import Matter
from clio_mcp.tools import matters


@pytest.fixture
def sample_matter() -> Matter:
    return Matter(id=1, display_number="00001-Smith")


async def test_get_matter_delegates_to_client(sample_matter: Matter) -> None:
    fake_client = AsyncMock()
    fake_client.get_matter.return_value = sample_matter

    with patch.object(matters, "_get_client", return_value=fake_client):
        result = await matters.get_matter(1)

    fake_client.get_matter.assert_awaited_once_with(1)
    assert result is sample_matter


async def test_search_matters_delegates_to_client(sample_matter: Matter) -> None:
    fake_client = AsyncMock()
    fake_client.search_matters.return_value = [sample_matter]

    with patch.object(matters, "_get_client", return_value=fake_client):
        result = await matters.search_matters("Smith", limit=10)

    fake_client.search_matters.assert_awaited_once_with("Smith", 10, None)
    assert result == [sample_matter]


async def test_search_matters_passes_status(sample_matter: Matter) -> None:
    fake_client = AsyncMock()
    fake_client.search_matters.return_value = [sample_matter]

    with patch.object(matters, "_get_client", return_value=fake_client):
        await matters.search_matters("Smith", limit=10, status="open")

    fake_client.search_matters.assert_awaited_once_with("Smith", 10, "open")


async def test_search_matters_passes_none_query_when_omitted(
    sample_matter: Matter,
) -> None:
    fake_client = AsyncMock()
    fake_client.search_matters.return_value = [sample_matter]

    with patch.object(matters, "_get_client", return_value=fake_client):
        await matters.search_matters(limit=10, status="open")

    fake_client.search_matters.assert_awaited_once_with(None, 10, "open")


async def test_search_matters_rejects_limit_above_100() -> None:
    with pytest.raises(ValueError, match="100"):
        await matters.search_matters("Smith", limit=101)
