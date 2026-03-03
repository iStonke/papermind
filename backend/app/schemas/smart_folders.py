import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.documents import DocumentSummary


class SmartFolderSort(str, Enum):
    created_desc = "created_desc"
    doc_date_desc = "doc_date_desc"
    title_asc = "title_asc"


class SmartFolderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    is_pinned: bool = False
    query_json: dict[str, Any]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class SmartFolderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_pinned: bool | None = None
    query_json: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "SmartFolderUpdateRequest":
        if self.name is None and self.is_pinned is None and self.query_json is None:
            raise ValueError("At least one field must be provided")
        return self


class SmartFolderPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_json: dict[str, Any]
    count_only: bool = False
    limit: int = Field(default=5, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort: SmartFolderSort = SmartFolderSort.created_desc


class SmartFolderPreviewResponse(BaseModel):
    total: int = 0
    items: list[DocumentSummary] | None = None
    limit: int | None = None
    offset: int | None = None


class SmartFolderListItem(ORMModel):
    id: uuid.UUID
    name: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class SmartFolderRead(ORMModel):
    id: uuid.UUID
    name: str
    is_pinned: bool
    query_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SmartFolderListResponse(BaseModel):
    items: list[SmartFolderListItem]
