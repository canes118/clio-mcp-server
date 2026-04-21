from datetime import date, datetime

from clio_mcp.models import Contact, Matter


def test_matter_parses_realistic_payload() -> None:
    matter = Matter.model_validate(
        {
            "id": 42,
            "display_number": "00042-Smith",
            "status": "Open",
            "client": {"id": 7, "name": "Acme Corp"},
            "open_date": "2024-01-15",
            "created_at": "2024-01-15T09:30:00Z",
        }
    )
    assert matter.id == 42
    assert matter.display_number == "00042-Smith"
    assert matter.status == "Open"
    assert matter.client.id == 7
    assert matter.client.name == "Acme Corp"
    assert matter.open_date == date(2024, 1, 15)
    assert isinstance(matter.created_at, datetime)


def test_matter_with_none_client_parses_cleanly() -> None:
    matter = Matter.model_validate({"id": 1, "client": None})
    assert matter.client.id is None
    assert matter.client.name is None


def test_contact_email_alias() -> None:
    contact = Contact.model_validate(
        {"id": 99, "primary_email_address": "jane@example.com"}
    )
    assert contact.email == "jane@example.com"


def test_matter_tolerates_unknown_fields() -> None:
    matter = Matter.model_validate({"id": 5, "some_future_clio_field": "whatever"})
    assert matter.id == 5
