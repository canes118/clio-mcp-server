"""Clio OAuth2 authentication module.

Public interface:
    get_access_token() — the single function tool handlers call to get a
    valid access token, refreshing transparently if needed.
"""

from __future__ import annotations

from clio_mcp.auth.client import ClioAuthClient
from clio_mcp.auth.exceptions import (
    ClioAuthError,
    ClioConfigError,
    ClioTokenError,
    ClioTokenFileCorruptError,
    ClioTokenNotFoundError,
    ClioTokenRefreshError,
)
from clio_mcp.auth.models import ClioConfig, ClioTokens
from clio_mcp.auth.token_store import FileTokenStore, TokenStore

__all__ = [
    "ClioAuthClient",
    "ClioAuthError",
    "ClioConfig",
    "ClioConfigError",
    "ClioTokenError",
    "ClioTokenFileCorruptError",
    "ClioTokenNotFoundError",
    "ClioTokenRefreshError",
    "ClioTokens",
    "FileTokenStore",
    "TokenStore",
    "get_access_token",
]


async def get_access_token(
    config: ClioConfig,
    store: TokenStore,
    client: ClioAuthClient,
) -> str:
    """Return a valid access token, refreshing if expired.

    Raises ClioTokenNotFoundError if no tokens are stored (user must run
    the bootstrap CLI first). Propagates ClioTokenRefreshError if the
    refresh call fails.
    """
    tokens = store.load()

    if tokens is None:
        raise ClioTokenNotFoundError(
            "No stored tokens found. Run `python -m clio_mcp.auth` to authorize."
        )

    if tokens.is_expired():
        tokens = await client.refresh(tokens)
        store.save(tokens)

    return tokens.access_token
