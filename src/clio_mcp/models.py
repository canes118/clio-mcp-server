"""Pydantic models for Clio API entities.

Single source of truth for the shapes MCP tools return to the LLM. Models
only cover the fields current tools actually need — expand the models as
new tools require new fields, rather than pre-modeling the entire Clio
schema.
"""

from datetime import date, datetime
from typing import Any

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


class Contact(ClioEntity):
    """A person or organization in Clio's address book. Contacts may be
    clients on matters, opposing parties, vendors, or unrelated third
    parties; the type field distinguishes Person vs. Company.
    """

    id: int
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    type: str | None = None
    title: str | None = None
    email: str | None = Field(None, alias="primary_email_address")
    phone: str | None = Field(None, alias="primary_phone_number")
    company: ClioRef = Field(default_factory=ClioRef)
    created_at: datetime | None = None
    updated_at: datetime | None = None
