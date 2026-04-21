from datetime import UTC, datetime, timedelta

import pytest

from clio_mcp.auth.exceptions import ClioConfigError, ClioTokenRefreshError
from clio_mcp.auth.models import ClioConfig, ClioTokens


class TestClioConfigFromEnv:
    def test_raises_listing_all_missing_vars(self, monkeypatch):
        monkeypatch.delenv("CLIO_CLIENT_ID", raising=False)
        monkeypatch.delenv("CLIO_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("CLIO_REDIRECT_URI", raising=False)

        with pytest.raises(ClioConfigError, match="CLIO_CLIENT_ID") as exc_info:
            ClioConfig.from_env()

        msg = str(exc_info.value)
        assert "CLIO_CLIENT_SECRET" in msg
        assert "CLIO_REDIRECT_URI" in msg

    def test_succeeds_when_all_vars_set(self, monkeypatch):
        monkeypatch.setenv("CLIO_CLIENT_ID", "id123")
        monkeypatch.setenv("CLIO_CLIENT_SECRET", "secret456")
        monkeypatch.setenv("CLIO_REDIRECT_URI", "http://localhost/callback")

        config = ClioConfig.from_env()

        assert config.client_id == "id123"
        assert config.client_secret.get_secret_value() == "secret456"
        assert config.redirect_uri == "http://localhost/callback"
        assert config.api_base == "https://app.clio.com/api/v4"

    def test_oauth_base_strips_api_v4(self):
        config = ClioConfig(
            client_id="x",
            client_secret="y",
            redirect_uri="http://localhost",
            api_base="https://app.clio.com/api/v4",
        )
        assert config.oauth_base == "https://app.clio.com"


class TestClioTokensValidation:
    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            ClioTokens(
                access_token="abc",
                refresh_token="def",
                expires_at=datetime(2026, 1, 1, 12, 0, 0),  # naive
            )


class TestClioTokensFromTokenResponse:
    def test_uses_refresh_token_from_response(self):
        response = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
            "token_type": "bearer",
        }
        tokens = ClioTokens.from_token_response(response)

        assert tokens.access_token == "new_access"
        assert tokens.refresh_token == "new_refresh"

    def test_falls_back_to_previous_refresh_token(self):
        previous = ClioTokens(
            access_token="old_access",
            refresh_token="old_refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        response = {
            "access_token": "new_access",
            "expires_in": 3600,
            "token_type": "bearer",
        }
        tokens = ClioTokens.from_token_response(response, previous=previous)

        assert tokens.access_token == "new_access"
        assert tokens.refresh_token == "old_refresh"

    def test_raises_when_no_refresh_token_available(self):
        response = {
            "access_token": "new_access",
            "expires_in": 3600,
            "token_type": "bearer",
        }
        with pytest.raises(ClioTokenRefreshError, match="No refresh_token"):
            ClioTokens.from_token_response(response)


class TestClioTokensIsExpired:
    def test_expired_when_in_the_past(self):
        tokens = ClioTokens(
            access_token="a",
            refresh_token="r",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert tokens.is_expired() is True

    def test_expired_when_within_buffer(self):
        tokens = ClioTokens(
            access_token="a",
            refresh_token="r",
            expires_at=datetime.now(UTC) + timedelta(seconds=60),
        )
        assert tokens.is_expired(buffer_seconds=300) is True

    def test_not_expired_when_safely_in_future(self):
        tokens = ClioTokens(
            access_token="a",
            refresh_token="r",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        assert tokens.is_expired() is False
