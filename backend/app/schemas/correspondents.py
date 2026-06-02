import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.utils import (
    CORRESPONDENT_NAME_MAX_LENGTH,
    CORRESPONDENT_NAME_MIN_LENGTH,
    validate_correspondent_alias,
    validate_correspondent_name,
)


class CorrespondentCreateRequest(BaseModel):
    name: str = Field(min_length=CORRESPONDENT_NAME_MIN_LENGTH, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    short_name: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_correspondent_name(value)

    @field_validator("short_name", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class CorrespondentAliasCreateRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=120)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return validate_correspondent_alias(value)


class CorrespondentAliasRead(ORMModel):
    id: uuid.UUID
    alias: str


class CorrespondentRead(ORMModel):
    id: uuid.UUID
    name: str
    short_name: str | None = None
    notes: str | None = None
    created_at: datetime
    aliases: list[CorrespondentAliasRead] = Field(default_factory=list)
    usage_count: int | None = None


class CorrespondentListResponse(BaseModel):
    items: list[CorrespondentRead]
