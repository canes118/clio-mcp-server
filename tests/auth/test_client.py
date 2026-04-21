"""Tests for ClioAuthClient OAuth2 operations."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

import httpx
import pytest
import respx

from clio_mcp.auth.client import ClioAuthClient
from clio_mcp.auth.exceptions import ClioTokenRefreshError
from clio_mcp.auth.models import ClioConfig, ClioTokens


@pytest.fixture
def config() -> ClioConfig:
    return ClioConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8080/callback",
        api_base="https://app.clio.com/api/v4",
    )


@pytest.fixture
def auth_client(config: ClioConfig) -> ClioAuthClient:
    return ClioAuthClient(config)


@pytest.fixture
def token_response() -> dict:
    return {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
        "token_type": "bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def existing_tokens() -> ClioTokens:
    return ClioTokens(
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        token_type="bearer",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestBuildAuthorizeUrl:
    def test_contains_required_params(self, auth_client: ClioAuthClient) -> None:
        url = auth_client.build_authorize_url(state="abc123")
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)

        assert params["response_type"] == ["code"]
        assert params["client_id"] == ["test-client-id"]
        assert params["redirect_uri"] == ["http://localhost:8080/callback"]
        assert params["state"] == ["abc123"]

    def test_encodes_special_characters_in_state(
        self, auth_client: ClioAuthClient
    ) -> None:
        url = auth_client.build_authorize_url(state="foo=bar&baz")
        assert "foo%3Dbar%26baz" in url
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        assert params["state"] == ["foo=bar&baz"]


class TestExchangeCode:
    @respx.mock
    async def test_sends_correct_form_body(
        self, auth_client: ClioAuthClient, token_response: dict
    ) -> None:
        route = respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(200, json=token_response)
        )

        await auth_client.exchange_code("auth-code-123")

        request = route.calls[0].request
        body = urllib.parse.parse_qs(request.content.decode())
        assert body["grant_type"] == ["authorization_code"]
        assert body["code"] == ["auth-code-123"]
        assert body["client_id"] == ["test-client-id"]
        assert body["client_secret"] == ["test-client-secret"]
        assert body["redirect_uri"] == ["http://localhost:8080/callback"]

    @respx.mock
    async def test_returns_tokens_on_success(
        self, auth_client: ClioAuthClient, token_response: dict
    ) -> None:
        respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(200, json=token_response)
        )

        tokens = await auth_client.exchange_code("auth-code-123")

        assert tokens.access_token == "new-access-token"
        assert tokens.refresh_token == "new-refresh-token"

    @respx.mock
    async def test_raises_on_400_response(self, auth_client: ClioAuthClient) -> None:
        respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(400, text="invalid_grant")
        )

        with pytest.raises(ClioTokenRefreshError, match="invalid_grant"):
            await auth_client.exchange_code("bad-code")


class TestRefresh:
    @respx.mock
    async def test_sends_correct_form_body(
        self,
        auth_client: ClioAuthClient,
        existing_tokens: ClioTokens,
        token_response: dict,
    ) -> None:
        route = respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(200, json=token_response)
        )

        await auth_client.refresh(existing_tokens)

        request = route.calls[0].request
        body = urllib.parse.parse_qs(request.content.decode())
        assert body["grant_type"] == ["refresh_token"]
        assert body["refresh_token"] == ["old-refresh-token"]
        assert body["client_id"] == ["test-client-id"]
        assert body["client_secret"] == ["test-client-secret"]

    @respx.mock
    async def test_returns_new_tokens_with_new_refresh_token(
        self,
        auth_client: ClioAuthClient,
        existing_tokens: ClioTokens,
        token_response: dict,
    ) -> None:
        respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(200, json=token_response)
        )

        tokens = await auth_client.refresh(existing_tokens)

        assert tokens.access_token == "new-access-token"
        assert tokens.refresh_token == "new-refresh-token"

    @respx.mock
    async def test_falls_back_to_previous_refresh_token(
        self, auth_client: ClioAuthClient, existing_tokens: ClioTokens
    ) -> None:
        """Regression test: when Clio omits refresh_token, use previous."""
        response_without_refresh = {
            "access_token": "refreshed-access-token",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(200, json=response_without_refresh)
        )

        tokens = await auth_client.refresh(existing_tokens)

        assert tokens.access_token == "refreshed-access-token"
        assert tokens.refresh_token == "old-refresh-token"

    @respx.mock
    async def test_raises_on_401_response(
        self, auth_client: ClioAuthClient, existing_tokens: ClioTokens
    ) -> None:
        respx.post("https://app.clio.com/oauth/token").mock(
            return_value=httpx.Response(401, text="unauthorized")
        )

        with pytest.raises(ClioTokenRefreshError, match="401"):
            await auth_client.refresh(existing_tokens)
