"""Pydantic models for Clio API entities.

Single source of truth for the shapes MCP tools return to the LLM. Models
only cover the fields current tools actually need — expand the models as
new tools require new fields, rather than pre-modeling the entire Clio
schema.
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClioRef(BaseModel):
    """A lightweight reference to another Clio entity (e.g. the client on a
    matter, or the company on a contact). Clio embeds these as small nested
    objects with just an id and name rather than the full related record.
    """

    id: int | None = None
    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def handle_non_dict(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {}
        return data


class ClioEntity(BaseModel):
    """Base class for top-level Clio entities. Allows population by field
    name or alias and tolerates unknown fields so newly-added Clio API
    attributes don't break parsing before we explicitly model them.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Matter(ClioEntity):
    """A legal matter — one engagement for one client. The core unit of
    work in Clio. Attorneys refer to matters by their display_number.
    """

    id: int
    display_number: str | None = None
    description: str | None = None
    status: str | None = None
    client: ClioRef = Field(default_factory=ClioRef)
    practice_area: ClioRef = Field(default_factory=ClioRef)
    responsible_attorney: ClioRef = Field(default_factory=ClioRef)
    originating_attorney: ClioRef = Field(default_factory=ClioRef)
    open_date: date | None = None
    close_date: date | None = None
    billable: bool | None = None
    billing_method: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContactBase(ClioEntity):
    """Fields common to every contact, regardless of Person vs. Company.

    Not instantiated directly — use ContactPerson or ContactCompany, or
    the Contact discriminated union that resolves between them on the
    type field.
    """

    id: int
    primary_email_address: str | None = None
    primary_phone_number: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContactPerson(ContactBase):
    """An individual person in Clio's address book — a client, opposing
    party, witness, vendor contact, or other named individual.
    """

    type: Literal["Person"]
    first_name: str | None = None
    last_name: str | None = None
    prefix: str | None = None
    middle_name: str | None = None
    suffix: str | None = None
    date_of_birth: date | None = None


class ContactCompany(ContactBase):
    """An organization in Clio's address book — a corporate client,
    opposing firm, vendor, or other entity.
    """

    type: Literal["Company"]
    name: str | None = None


Contact = Annotated[ContactPerson | ContactCompany, Field(discriminator="type")]
