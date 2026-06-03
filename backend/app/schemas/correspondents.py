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


class CorrespondentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=CORRESPONDENT_NAME_MIN_LENGTH, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    short_name: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_correspondent_name(value)

    @field_validator("short_name", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class CorrespondentMatcherCreateRequest(BaseModel):
    kind: str = Field(default="contains")
    pattern: str = Field(min_length=1, max_length=240)
    scope: str = Field(default="both")
    priority: int = Field(default=100, ge=0, le=1000)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip() or "contains"
        if normalized not in {"contains", "regex", "starts_with"}:
            raise ValueError("Matcher kind must be contains, regex or starts_with")
        return normalized

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip() or "both"
        if normalized not in {"filename", "ocr_text", "both"}:
            raise ValueError("Matcher scope must be filename, ocr_text or both")
        return normalized

    @field_validator("pattern")
    @classmethod
    def normalize_pattern(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("Matcher pattern must not be empty")
        return normalized


class CorrespondentAliasRead(ORMModel):
    id: uuid.UUID
    alias: str


class CorrespondentMatcherRead(ORMModel):
    id: uuid.UUID
    kind: str
    pattern: str
    scope: str
    priority: int


class CorrespondentRead(ORMModel):
    id: uuid.UUID
    name: str
    short_name: str | None = None
    notes: str | None = None
    created_at: datetime
    aliases: list[CorrespondentAliasRead] = Field(default_factory=list)
    matchers: list[CorrespondentMatcherRead] = Field(default_factory=list)
    usage_count: int | None = None


class CorrespondentListResponse(BaseModel):
    items: list[CorrespondentRead]


class UnresolvedCorrespondentItemRead(BaseModel):
    document_id: uuid.UUID
    title: str
    original_filename: str
    sender: str | None = None
    document_type: str | None = None
    document_date: str | None = None
    ai_status: str
    ocr_status: str
    text_available: bool
    text_excerpt: str | None = None


class UnresolvedCorrespondentReportResponse(BaseModel):
    scanned: int
    unresolved: int
    include_deleted: bool
    items: list[UnresolvedCorrespondentItemRead]


class CorrespondentReviewIgnoreRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None
