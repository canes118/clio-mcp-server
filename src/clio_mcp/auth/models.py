from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, SecretStr, computed_field, field_validator

from clio_mcp.auth.exceptions import ClioConfigError, ClioTokenRefreshError

DEFAULT_API_BASE = "https://app.clio.com/api/v4"


class ClioConfig(BaseModel):
    """OAuth2 configuration for the Clio API."""

    client_id: str
    client_secret: SecretStr
    redirect_uri: str
    api_base: str = DEFAULT_API_BASE

    @classmethod
    def from_env(cls) -> ClioConfig:
        """Read Clio config from environment variables.

        Raises ClioConfigError listing all missing variables if any required
        ones are absent.
        """
        mapping = {
            "client_id": "CLIO_CLIENT_ID",
            "client_secret": "CLIO_CLIENT_SECRET",
            "redirect_uri": "CLIO_REDIRECT_URI",
        }
        missing = [env for env in mapping.values() if not os.environ.get(env)]
        if missing:
            raise ClioConfigError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        return cls(
            client_id=os.environ["CLIO_CLIENT_ID"],
            client_secret=os.environ["CLIO_CLIENT_SECRET"],
            redirect_uri=os.environ["CLIO_REDIRECT_URI"],
            api_base=os.environ.get("CLIO_API_BASE", DEFAULT_API_BASE),
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def oauth_base(self) -> str:
        """Base URL for OAuth endpoints (api_base with /api/v4 stripped)."""
        return self.api_base.removesuffix("/api/v4")


class ClioTokens(BaseModel):
    """OAuth2 token pair for Clio API access."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def _expires_at_must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("expires_at must be a timezone-aware datetime")
        return v

    @classmethod
    def from_token_response(
        cls, response_data: dict, previous: ClioTokens | None = None
    ) -> ClioTokens:
        """Build ClioTokens from a raw /oauth/token JSON response.

        If the response omits refresh_token (common on refresh grant
        responses), falls back to previous.refresh_token. Raises
        ClioTokenRefreshError if neither source provides one.
        """
        refresh_token = response_data.get("refresh_token")
        if refresh_token is None and previous is not None:
            refresh_token = previous.refresh_token
        if refresh_token is None:
            raise ClioTokenRefreshError(
                "No refresh_token in response and no previous token to fall back to"
            )

        expires_at = datetime.now(UTC) + timedelta(seconds=response_data["expires_in"])

        return cls(
            access_token=response_data["access_token"],
            refresh_token=refresh_token,
            token_type=response_data.get("token_type", "bearer"),
            expires_at=expires_at,
        )

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Return True if the token expires within buffer_seconds from now."""
        return self.expires_at <= datetime.now(UTC) + timedelta(seconds=buffer_seconds)
