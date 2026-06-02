import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.utils import NAME_MAX_LENGTH, NAME_MIN_LENGTH, validate_vocab_name


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_vocab_name(value, label="Category name")


class CategoryUpdateRequest(BaseModel):
    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_vocab_name(value, label="Category name")


class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    usage_count: int | None = None


class CategoryListResponse(BaseModel):
    items: list[CategoryRead]
