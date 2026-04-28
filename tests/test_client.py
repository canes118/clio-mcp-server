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
from clio_mcp.client import CONTACT_FIELDS, MATTER_FIELDS, ClioClient
from clio_mcp.exceptions import ClioAPIError, ClioNotFoundError
from clio_mcp.models import ContactCompany, ContactPerson, Matter

MATTER_PAYLOAD = {
    "id": 123,
    "display_number": "00001-Smith",
    "description": "Contract dispute with ACME Corp",
    "status": "Open",
    "client": {"id": 42, "name": "Smith, John"},
    "practice_area": {"id": 7, "name": "Litigation"},
}

PERSON_PAYLOAD = {
    "id": 501,
    "type": "Person",
    "first_name": "Jane",
    "last_name": "Smith",
    "primary_email_address": "jane@example.com",
    "primary_phone_number": "555-0101",
}

COMPANY_PAYLOAD = {
    "id": 502,
    "type": "Company",
    "name": "Acme LLC",
    "primary_phone_number": "555-0100",
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
    async def test_requests_expanded_fields(self, client: ClioClient) -> None:
        route = respx.get("https://app.clio.com/api/v4/matters/123.json").mock(
            return_value=httpx.Response(200, json={"data": MATTER_PAYLOAD})
        )

        await client.get_matter(123)

        request = route.calls[0].request
        assert request.url.params["fields"] == MATTER_FIELDS
        fields = request.url.params["fields"]
        for expected in (
            "description",
            "status",
            "billable",
            "client",
            "responsible_attorney",
        ):
            assert expected in fields

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
        assert request.url.params["fields"] == MATTER_FIELDS

    @respx.mock
    async def test_parses_nested_refs_from_expanded_payload(
        self, client: ClioClient
    ) -> None:
        expanded = {
            **MATTER_PAYLOAD,
            "responsible_attorney": {"id": 11, "name": "Attorney A"},
            "originating_attorney": {"id": 12, "name": "Attorney B"},
        }
        respx.get("https://app.clio.com/api/v4/matters.json").mock(
            return_value=httpx.Response(200, json={"data": [expanded]})
        )

        matters = await client.search_matters("Smith")

        assert len(matters) == 1
        matter = matters[0]
        assert matter.client.id == 42
        assert matter.client.name == "Smith, John"
        assert matter.practice_area.id == 7
        assert matter.practice_area.name == "Litigation"
        assert matter.responsible_attorney.id == 11
        assert matter.responsible_attorney.name == "Attorney A"
        assert matter.originating_attorney.id == 12
        assert matter.originating_attorney.name == "Attorney B"


class TestGetContact:
    @respx.mock
    async def test_returns_parsed_person(self, client: ClioClient) -> None:
        route = respx.get("https://app.clio.com/api/v4/contacts/501.json").mock(
            return_value=httpx.Response(200, json={"data": PERSON_PAYLOAD})
        )

        contact = await client.get_contact(501)

        assert isinstance(contact, ContactPerson)
        assert contact.id == 501
        assert contact.first_name == "Jane"
        assert contact.last_name == "Smith"
        assert contact.primary_email_address == "jane@example.com"

        sent_auth = route.calls[0].request.headers["Authorization"]
        assert sent_auth == "Bearer fake-access-token"

    @respx.mock
    async def test_requests_expanded_fields(self, client: ClioClient) -> None:
        route = respx.get("https://app.clio.com/api/v4/contacts/501.json").mock(
            return_value=httpx.Response(200, json={"data": PERSON_PAYLOAD})
        )

        await client.get_contact(501)

        request = route.calls[0].request
        assert request.url.params["fields"] == CONTACT_FIELDS
        fields = request.url.params["fields"]
        for expected in (
            "type",
            "first_name",
            "last_name",
            "primary_email_address",
        ):
            assert expected in fields

    @respx.mock
    async def test_returns_parsed_company(self, client: ClioClient) -> None:
        respx.get("https://app.clio.com/api/v4/contacts/502.json").mock(
            return_value=httpx.Response(200, json={"data": COMPANY_PAYLOAD})
        )

        contact = await client.get_contact(502)

        assert isinstance(contact, ContactCompany)
        assert contact.id == 502
        assert contact.name == "Acme LLC"

    @respx.mock
    async def test_raises_not_found_on_404(self, client: ClioClient) -> None:
        respx.get("https://app.clio.com/api/v4/contacts/999.json").mock(
            return_value=httpx.Response(404, text='{"error":"not found"}')
        )

        with pytest.raises(ClioNotFoundError) as exc_info:
            await client.get_contact(999)

        assert exc_info.value.status_code == 404


class TestSearchContacts:
    @respx.mock
    async def test_returns_mixed_list(self, client: ClioClient) -> None:
        route = respx.get("https://app.clio.com/api/v4/contacts.json").mock(
            return_value=httpx.Response(
                200, json={"data": [PERSON_PAYLOAD, COMPANY_PAYLOAD]}
            )
        )

        contacts = await client.search_contacts("Smith", limit=10)

        assert len(contacts) == 2
        assert isinstance(contacts[0], ContactPerson)
        assert isinstance(contacts[1], ContactCompany)

        request = route.calls[0].request
        assert request.url.params["query"] == "Smith"
        assert request.url.params["limit"] == "10"
        assert request.url.params["fields"] == CONTACT_FIELDS
        assert "type" not in request.url.params

    @respx.mock
    async def test_passes_type_filter(self, client: ClioClient) -> None:
        route = respx.get("https://app.clio.com/api/v4/contacts.json").mock(
            return_value=httpx.Response(200, json={"data": [COMPANY_PAYLOAD]})
        )

        contacts = await client.search_contacts("Acme", type="Company", limit=5)

        assert len(contacts) == 1
        assert isinstance(contacts[0], ContactCompany)

        request = route.calls[0].request
        assert request.url.params["query"] == "Acme"
        assert request.url.params["type"] == "Company"
        assert request.url.params["limit"] == "5"
        assert request.url.params["fields"] == CONTACT_FIELDS

    @respx.mock
    async def test_parses_populated_person_and_company_fields(
        self, client: ClioClient
    ) -> None:
        populated_person = {
            **PERSON_PAYLOAD,
            "prefix": "Dr.",
            "middle_name": "Q",
            "suffix": "Jr.",
            "date_of_birth": "1980-05-01",
        }
        populated_company = {**COMPANY_PAYLOAD, "primary_email_address": "info@acme.example"}
        respx.get("https://app.clio.com/api/v4/contacts.json").mock(
            return_value=httpx.Response(
                200, json={"data": [populated_person, populated_company]}
            )
        )

        contacts = await client.search_contacts("Smith")

        person, company = contacts
        assert isinstance(person, ContactPerson)
        assert person.prefix == "Dr."
        assert person.middle_name == "Q"
        assert person.suffix == "Jr."
        assert person.date_of_birth is not None
        assert person.date_of_birth.isoformat() == "1980-05-01"
        assert isinstance(company, ContactCompany)
        assert company.name == "Acme LLC"
        assert company.primary_email_address == "info@acme.example"


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
