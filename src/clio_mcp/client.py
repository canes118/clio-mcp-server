"""Async HTTP wrapper for Clio's main API."""

from __future__ import annotations

from typing import Any

import httpx

from clio_mcp.auth import get_access_token
from clio_mcp.auth.client import ClioAuthClient
from clio_mcp.auth.models import ClioConfig
from clio_mcp.auth.token_store import FileTokenStore, TokenStore
from clio_mcp.exceptions import ClioAPIError, ClioNotFoundError
from clio_mcp.models import Matter


class ClioClient:
    """Async HTTP wrapper for Clio's main API.

    Handles auth-header injection, response parsing into typed models,
    and error mapping. All outbound Clio API calls go through here.
    """

    def __init__(
        self,
        config: ClioConfig,
        *,
        token_store: TokenStore | None = None,
        auth_client: ClioAuthClient | None = None,
    ) -> None:
        self.config = config
        self._token_store = token_store or FileTokenStore()
        self._auth_client = auth_client or ClioAuthClient(config)

    async def get_matter(self, matter_id: int) -> Matter:
        payload = await self._request("GET", f"/matters/{matter_id}.json")
        return Matter.model_validate(payload["data"])

    async def search_matters(self, query: str, limit: int = 25) -> list[Matter]:
        payload = await self._request(
            "GET",
            "/matters.json",
            params={"query": query, "limit": limit},
        )
        return [Matter.model_validate(item) for item in payload["data"]]

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.api_base}{path}"
        headers = await self._authorized_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=headers, params=params
            )

        self._raise_for_status(response)
        return response.json()

    async def _authorized_headers(self) -> dict[str, str]:
        token = await get_access_token(
            self.config, self._token_store, self._auth_client
        )
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        if response.status_code == 404:
            raise ClioNotFoundError(response.status_code, response.text)
        raise ClioAPIError(response.status_code, response.text)
