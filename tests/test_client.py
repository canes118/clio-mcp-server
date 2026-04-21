"""Tests for ClioClient main-API operations."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import httpx
import pytest
import respx

from clio_mcp.auth.models import ClioConfig
from clio_mcp.client import ClioClient
from clio_mcp.exceptions import ClioAPIError, ClioNotFoundError
from clio_mcp.models import Matter

MATTER_PAYLOAD = {
    "id": 123,
    "display_number": "00001-Smith",
    "description": "Contract dispute with ACME Corp",
    "status": "Open",
    "client": {"id": 42, "name": "Smith, John"},
    "practice_area": {"id": 7, "name": "Litigation"},
}


@pytest.fixture
def config() -> ClioConfig:
    return ClioConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8080/callback",
        api_base="https://app.clio.com/api/v4",
    )


@pytest.fixture
def client(config: ClioConfig) -> ClioClient:
    return ClioClient(config)


@pytest.fixture(autouse=True)
def mock_access_token() -> Iterator[None]:
    """Stub out the token-refresh flow with a fixed bearer token."""

    async def fake_get_access_token(*args: object, **kwargs: object) -> str:
        return "fake-access-token"

    with patch("clio_mcp.client.get_access_token", side_effect=fake_get_access_token):
        yield


class TestGetMatter:
    @respx.mock
    async def test_returns_parsed_matter(self, client: ClioClient) -> None:
        route = respx.get("https://app.clio.com/api/v4/matters/123.json").mock(
            return_value=httpx.Response(200, json={"data": MATTER_PAYLOAD})
        )

        matter = await client.get_matter(123)

        assert isinstance(matter, Matter)
        assert matter.id == 123
        assert matter.display_number == "00001-Smith"
        assert matter.client.name == "Smith, John"
        assert matter.practice_area.id == 7

        sent_auth = route.calls[0].request.headers["Authorization"]
        assert sent_auth == "Bearer fake-access-token"

    @respx.mock
    async def test_raises_not_found_on_404(self, client: ClioClient) -> None:
        respx.get("https://app.clio.com/api/v4/matters/999.json").mock(
            return_value=httpx.Response(404, text='{"error":"not found"}')
        )

        with pytest.raises(ClioNotFoundError) as exc_info:
            await client.get_matter(999)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.body

    @respx.mock
    async def test_raises_api_error_on_500(self, client: ClioClient) -> None:
        respx.get("https://app.clio.com/api/v4/matters/1.json").mock(
            return_value=httpx.Response(500, text="internal error")
        )

        with pytest.raises(ClioAPIError) as exc_info:
            await client.get_matter(1)

        assert not isinstance(exc_info.value, ClioNotFoundError)
        assert exc_info.value.status_code == 500
        assert exc_info.value.body == "internal error"


class TestSearchMatters:
    @respx.mock
    async def test_returns_list_of_matters(self, client: ClioClient) -> None:
        second = {**MATTER_PAYLOAD, "id": 124, "display_number": "00002-Smith"}
        route = respx.get("https://app.clio.com/api/v4/matters.json").mock(
            return_value=httpx.Response(200, json={"data": [MATTER_PAYLOAD, second]})
        )

        matters = await client.search_matters("Smith", limit=10)

        assert len(matters) == 2
        assert all(isinstance(m, Matter) for m in matters)
        assert [m.id for m in matters] == [123, 124]

        request = route.calls[0].request
        assert request.url.params["query"] == "Smith"
        assert request.url.params["limit"] == "10"
