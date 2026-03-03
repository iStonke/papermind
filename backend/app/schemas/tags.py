import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class TagDeleteBehavior(str, Enum):
    detach = "detach"


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class TagUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class TagMergeRequest(BaseModel):
    target_id: uuid.UUID


class TagRead(ORMModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    usage_count: int | None = None


class TagListResponse(BaseModel):
    items: list[TagRead]
