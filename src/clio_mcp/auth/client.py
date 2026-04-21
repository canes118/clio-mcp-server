"""Async OAuth2 client for Clio token operations."""

from __future__ import annotations

import urllib.parse

import httpx

from clio_mcp.auth.exceptions import ClioTokenRefreshError
from clio_mcp.auth.models import ClioConfig, ClioTokens


class ClioAuthClient:
    """Handles the HTTP protocol side of Clio OAuth2.

    Builds authorize URLs, exchanges authorization codes for tokens,
    and refreshes access tokens. Does NOT touch the filesystem —
    persistence is the token store's job.
    """

    def __init__(self, config: ClioConfig) -> None:
        self.config = config

    def build_authorize_url(self, state: str) -> str:
        """Return the full authorization URL for the user to visit."""
        params = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "state": state,
            }
        )
        return f"{self.config.oauth_base}/oauth/authorize?{params}"

    async def exchange_code(self, code: str) -> ClioTokens:
        """Exchange an authorization code for tokens.

        Raises ClioTokenRefreshError on non-2xx responses.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret.get_secret_value(),
            "redirect_uri": self.config.redirect_uri,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.config.oauth_base}/oauth/token",
                data=data,
            )

        if not response.is_success:
            raise ClioTokenRefreshError(
                f"Token exchange failed ({response.status_code}): {response.text}"
            )

        return ClioTokens.from_token_response(response.json())

    async def refresh(self, tokens: ClioTokens) -> ClioTokens:
        """Refresh an access token using the refresh token.

        Raises ClioTokenRefreshError on non-2xx responses.
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": tokens.refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret.get_secret_value(),
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.config.oauth_base}/oauth/token",
                data=data,
            )

        if not response.is_success:
            raise ClioTokenRefreshError(
                f"Token refresh failed ({response.status_code}): {response.text}"
            )

        return ClioTokens.from_token_response(response.json(), previous=tokens)
