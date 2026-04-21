"""Tests for the public get_access_token() interface."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from clio_mcp.auth import get_access_token
from clio_mcp.auth.exceptions import ClioTokenNotFoundError, ClioTokenRefreshError
from clio_mcp.auth.models import ClioConfig, ClioTokens
from clio_mcp.auth.token_store import TokenStore


class InMemoryTokenStore(TokenStore):
    """Simple in-memory token store for testing."""

    def __init__(self, tokens: ClioTokens | None = None) -> None:
        self.tokens = tokens

    def load(self) -> ClioTokens | None:
        return self.tokens

    def save(self, tokens: ClioTokens) -> None:
        self.tokens = tokens

    def clear(self) -> None:
        self.tokens = None


@pytest.fixture
def config() -> ClioConfig:
    return ClioConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="http://localhost:8765/callback",
    )


def _make_tokens(*, expired: bool = False) -> ClioTokens:
    if expired:
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return ClioTokens(
        access_token="access-123",
        refresh_token="refresh-456",
        expires_at=expires_at,
    )


def _make_refreshed_tokens() -> ClioTokens:
    return ClioTokens(
        access_token="access-refreshed",
        refresh_token="refresh-789",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_raises_token_not_found_when_no_tokens(config: ClioConfig) -> None:
    store = InMemoryTokenStore(tokens=None)
    client = AsyncMock()

    with pytest.raises(ClioTokenNotFoundError, match="No stored tokens found"):
        await get_access_token(config, store, client)


@pytest.mark.asyncio
async def test_returns_access_token_when_valid(config: ClioConfig) -> None:
    tokens = _make_tokens(expired=False)
    store = InMemoryTokenStore(tokens=tokens)
    client = AsyncMock()

    result = await get_access_token(config, store, client)

    assert result == "access-123"
    client.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_refreshes_when_expired(config: ClioConfig) -> None:
    tokens = _make_tokens(expired=True)
    refreshed = _make_refreshed_tokens()
    store = InMemoryTokenStore(tokens=tokens)
    client = AsyncMock()
    client.refresh.return_value = refreshed

    result = await get_access_token(config, store, client)

    assert result == "access-refreshed"
    client.refresh.assert_called_once_with(tokens)
    assert store.tokens == refreshed


@pytest.mark.asyncio
async def test_propagates_refresh_error(config: ClioConfig) -> None:
    tokens = _make_tokens(expired=True)
    store = InMemoryTokenStore(tokens=tokens)
    client = AsyncMock()
    client.refresh.side_effect = ClioTokenRefreshError("refresh failed")

    with pytest.raises(ClioTokenRefreshError, match="refresh failed"):
        await get_access_token(config, store, client)
