import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.utils import NAME_MAX_LENGTH, NAME_MIN_LENGTH, validate_vocab_name


class TagDeleteBehavior(str, Enum):
    detach = "detach"


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_vocab_name(value, label="Tag name")


class TagUpdateRequest(BaseModel):
    name: str = Field(min_length=NAME_MIN_LENGTH, max_length=NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_vocab_name(value, label="Tag name")


class TagMergeRequest(BaseModel):
    target_id: uuid.UUID


class TagRead(ORMModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    usage_count: int | None = None


class TagListResponse(BaseModel):
    items: list[TagRead]
