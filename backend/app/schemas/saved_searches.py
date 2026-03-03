import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.documents import DocumentSortField, DocumentStatus, SortOrder


class SavedSearchVersion(int, Enum):
    v1 = 1


class SavedSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: SavedSearchVersion = SavedSearchVersion.v1
    q: str | None = Field(default=None, max_length=512)
    tagId: uuid.UUID | None = None
    status: DocumentStatus | None = None
    dateFrom: date | None = None
    dateTo: date | None = None
    sort: DocumentSortField | None = None
    order: SortOrder | None = None

    @field_validator("q")
    @classmethod
    def normalize_q(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_date_range(self) -> "SavedSearchQuery":
        if self.dateFrom and self.dateTo and self.dateFrom > self.dateTo:
            raise ValueError("dateFrom must be earlier than or equal to dateTo")
        return self


class SavedSearchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    query: SavedSearchQuery

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class SavedSearchUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    query: SavedSearchQuery | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "SavedSearchUpdateRequest":
        if self.name is None and self.query is None:
            raise ValueError("At least one field must be provided")
        return self


class SavedSearchListItem(ORMModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class SavedSearchRead(ORMModel):
    id: uuid.UUID
    name: str
    query_json: SavedSearchQuery
    created_at: datetime
    updated_at: datetime


class SavedSearchListResponse(BaseModel):
    items: list[SavedSearchListItem]
