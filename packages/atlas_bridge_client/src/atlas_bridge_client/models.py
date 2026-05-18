from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ─────────────────────────── Leads ───────────────────────────


class LeadIn(_Base):
    first_name: str = Field(..., max_length=150)
    last_name: str = Field("", max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    company: str = Field("", max_length=200)
    tax_id: str = Field("", max_length=50)
    position: str = Field("", max_length=150)
    source_detail: str = Field("", max_length=255)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _email_or_phone(self) -> "LeadIn":
        if not self.email and not self.phone:
            raise ValueError("At least one of 'email' or 'phone' is required.")
        return self


class LeadResult(_Base):
    lead_id: UUID
    created: bool


# ─────────────────────────── Contacts ───────────────────────────


class ContactIn(_Base):
    first_name: str = Field(..., max_length=150)
    last_name: str = Field("", max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    company: str = Field("", max_length=200)
    tax_id: str = Field("", max_length=50)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _email_or_phone(self) -> "ContactIn":
        if not self.email and not self.phone:
            raise ValueError("At least one of 'email' or 'phone' is required.")
        return self


class ContactResult(_Base):
    contact_id: UUID
    created: bool


# ─────────────────────────── Events ───────────────────────────


class EventIn(_Base):
    event_type: str
    contact_id: UUID | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    source: str = Field("", max_length=50)
    project_name: str = Field("", max_length=255)
    conversation_summary: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _has_contact_ref(self) -> "EventIn":
        if not any((self.contact_id, self.contact_email, self.contact_phone)):
            raise ValueError(
                "One of 'contact_id', 'contact_email' or 'contact_phone' is required."
            )
        return self


class EventResult(_Base):
    event_id: UUID
    contact_id: UUID


# ─────────────────────────── Convert (Lead → Account) ───────────────────────────


class AccountIn(_Base):
    name: str = Field(..., max_length=255)
    trade_name: str = Field("", max_length=255)
    tax_id: str = Field("", max_length=50)
    industry: str = Field("", max_length=100)
    customer_entity_type: Literal["person", "company", ""] = "company"
    company_size: str = Field("", max_length=50)
    phone: str = Field("", max_length=30)
    email: EmailStr | str = ""
    website: str = Field("", max_length=300)
    address: str = Field("", max_length=300)
    city: str = Field("", max_length=100)
    province: str = Field("", max_length=100)
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class ConvertResult(_Base):
    account_id: UUID
    lead_id: UUID
    created: bool
