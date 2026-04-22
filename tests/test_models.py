from datetime import date, datetime

from pydantic import TypeAdapter

from clio_mcp.models import Contact, ContactCompany, ContactPerson, Matter

_contact_adapter: TypeAdapter[Contact] = TypeAdapter(Contact)


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


def test_contact_person_parses_with_discriminator() -> None:
    contact = _contact_adapter.validate_python(
        {
            "id": 99,
            "type": "Person",
            "first_name": "Jane",
            "last_name": "Smith",
            "primary_email_address": "jane@example.com",
        }
    )
    assert isinstance(contact, ContactPerson)
    assert contact.first_name == "Jane"
    assert contact.last_name == "Smith"
    assert contact.primary_email_address == "jane@example.com"


def test_contact_company_parses_with_discriminator() -> None:
    contact = _contact_adapter.validate_python(
        {
            "id": 17,
            "type": "Company",
            "name": "Acme LLC",
            "primary_phone_number": "555-0100",
        }
    )
    assert isinstance(contact, ContactCompany)
    assert contact.name == "Acme LLC"
    assert contact.primary_phone_number == "555-0100"


def test_matter_tolerates_unknown_fields() -> None:
    matter = Matter.model_validate({"id": 5, "some_future_clio_field": "whatever"})
    assert matter.id == 5
