import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.utils import NAME_MAX_LENGTH, NAME_MIN_LENGTH, validate_vocab_name

DocumentTypeArea = Literal[
    "finance",
    "contracts_law",
    "insurance",
    "government_tax",
    "employment",
    "health",
    "access_it",
    "other",
]


class DocumentTypeCreateRequest(BaseModel):
    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    naming_template: str | None = Field(default=None, max_length=500)
    prompt_hint: str | None = Field(default=None, max_length=1000)
    area: DocumentTypeArea | None = None
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_vocab_name(value, label="Document type name")

    @field_validator("naming_template", "prompt_hint")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class DocumentTypeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)
    naming_template: str | None = Field(default=None, max_length=500)
    prompt_hint: str | None = Field(default=None, max_length=1000)
    area: DocumentTypeArea | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_vocab_name(value, label="Document type name")

    @field_validator("naming_template", "prompt_hint")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class DocumentTypeRead(ORMModel):
    id: uuid.UUID
    name: str
    naming_template: str | None = None
    prompt_hint: str | None = None
    area: DocumentTypeArea | None = None
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime
    usage_count: int | None = None


class DocumentTypeListResponse(BaseModel):
    items: list[DocumentTypeRead]
