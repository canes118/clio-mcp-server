"""Tests for ClioClient main-API operations."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest
import respx

from clio_mcp.auth.client import ClioAuthClient
from clio_mcp.auth.models import ClioConfig, ClioTokens
from clio_mcp.auth.token_store import TokenStore
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


class InMemoryTokenStore(TokenStore):
    def __init__(self, tokens: ClioTokens | None = None) -> None:
        self.tokens = tokens

    def load(self) -> ClioTokens | None:
        return self.tokens

    def save(self, tokens: ClioTokens) -> None:
        self.tokens = tokens

    def clear(self) -> None:
        self.tokens = None


class TestRefreshOn401:
    """Covers the refresh-once-and-retry path when the Clio API returns 401.

    These tests bypass the autouse `mock_access_token` patch by driving a
    real ClioAuthClient + InMemoryTokenStore, so the OAuth token endpoint
    (mocked via respx) is actually hit on refresh.
    """

    MATTER_URL = "https://app.clio.com/api/v4/matters/123.json"
    OAUTH_URL = "https://app.clio.com/oauth/token"

    @pytest.fixture
    def tokens(self) -> ClioTokens:
        return ClioTokens(
            access_token="old-access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    @pytest.fixture
    def store(self, tokens: ClioTokens) -> InMemoryTokenStore:
        return InMemoryTokenStore(tokens=tokens)

    @pytest.fixture
    def real_auth_client(
        self, config: ClioConfig, store: InMemoryTokenStore
    ) -> ClioClient:
        return ClioClient(
            config,
            token_store=store,
            auth_client=ClioAuthClient(config),
        )

    @staticmethod
    def _refresh_response() -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )

    @respx.mock
    async def test_happy_path_refresh_and_retry(
        self, real_auth_client: ClioClient, store: InMemoryTokenStore
    ) -> None:
        matter_route = respx.get(self.MATTER_URL).mock(
            side_effect=[
                httpx.Response(401, text='{"error":"unauthorized"}'),
                httpx.Response(200, json={"data": MATTER_PAYLOAD}),
            ]
        )
        oauth_route = respx.post(self.OAUTH_URL).mock(
            return_value=self._refresh_response()
        )

        matter = await real_auth_client.get_matter(123)

        assert isinstance(matter, Matter)
        assert matter.id == 123
        assert oauth_route.call_count == 1
        assert matter_route.call_count == 2
        assert store.tokens is not None
        assert store.tokens.access_token == "new-access-token"

    @respx.mock
    async def test_double_401_raises_after_single_retry(
        self, real_auth_client: ClioClient
    ) -> None:
        matter_route = respx.get(self.MATTER_URL).mock(
            side_effect=[
                httpx.Response(401, text='{"error":"unauthorized"}'),
                httpx.Response(401, text='{"error":"still unauthorized"}'),
            ]
        )
        oauth_route = respx.post(self.OAUTH_URL).mock(
            return_value=self._refresh_response()
        )

        with pytest.raises(ClioAPIError, match="still unauthorized"):
            await real_auth_client.get_matter(123)

        assert oauth_route.call_count == 1
        assert matter_route.call_count == 2

    @respx.mock
    async def test_non_401_does_not_refresh(
        self, real_auth_client: ClioClient
    ) -> None:
        respx.get(self.MATTER_URL).mock(
            return_value=httpx.Response(500, text="internal error")
        )
        oauth_route = respx.post(self.OAUTH_URL).mock(
            return_value=self._refresh_response()
        )

        with pytest.raises(ClioAPIError) as exc_info:
            await real_auth_client.get_matter(123)

        assert exc_info.value.status_code == 500
        assert oauth_route.call_count == 0

    @respx.mock
    async def test_success_does_not_refresh(
        self, real_auth_client: ClioClient
    ) -> None:
        respx.get(self.MATTER_URL).mock(
            return_value=httpx.Response(200, json={"data": MATTER_PAYLOAD})
        )
        oauth_route = respx.post(self.OAUTH_URL).mock(
            return_value=self._refresh_response()
        )

        matter = await real_auth_client.get_matter(123)

        assert matter.id == 123
        assert oauth_route.call_count == 0
