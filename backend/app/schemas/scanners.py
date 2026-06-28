import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import UserRead

ScanCommand = Literal["page", "finish"]


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


class ScannerDeviceRead(BaseModel):
    id: uuid.UUID
    device_key: str
    name: str
    enabled: bool
    live_page_mode: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None
    recipients: list[UserRead] = Field(default_factory=list)


class ScannerDeviceListResponse(BaseModel):
    items: list[ScannerDeviceRead] = Field(default_factory=list)


class ScannerDeviceCreateRequest(BaseModel):
    device_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=150)
    enabled: bool = True
    recipient_user_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("device_key", "name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


class ScanCommandRequest(BaseModel):
    command: ScanCommand


class ScanCommandResponse(BaseModel):
    id: uuid.UUID
    command: ScanCommand
    created_at: datetime


class ScannerDeviceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    enabled: bool | None = None
    live_page_mode: bool | None = None
    recipient_user_ids: list[uuid.UUID] | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_text(value)
        if not normalized:
            raise ValueError("must not be empty")
        return normalized
