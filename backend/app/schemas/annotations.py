import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AnnotationKind(str, Enum):
    highlight = "highlight"
    underline = "underline"
    note = "note"
    link = "link"
    rectangle = "rectangle"
    text = "text"
    pen = "pen"


class AnnotationRect(BaseModel):
    """Normalisiertes Rechteck (0–1, relativ zur Seitengröße) – zoom-unabhängig."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class AnnotationCreateRequest(BaseModel):
    page: int = Field(ge=1)
    kind: AnnotationKind = AnnotationKind.highlight
    color: str | None = Field(default=None, max_length=16)
    rects: list[AnnotationRect] = Field(min_length=1)
    quote: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    comment: str | None = None
    target_document_id: uuid.UUID | None = None
    target_url: str | None = Field(default=None, max_length=2048)


class AnnotationUpdateRequest(BaseModel):
    """Teil-Update: nur gesetzte Felder werden übernommen."""

    color: str | None = Field(default=None, max_length=16)
    comment: str | None = None
    target_document_id: uuid.UUID | None = None
    target_url: str | None = Field(default=None, max_length=2048)


class AnnotationRead(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    page: int
    kind: AnnotationKind
    color: str | None = None
    rects: list[AnnotationRect]
    quote: str | None = None
    comment: str | None = None
    target_document_id: uuid.UUID | None = None
    target_document_title: str | None = None
    target_url: str | None = None
    created_at: datetime
    updated_at: datetime


class AnnotationListResponse(BaseModel):
    items: list[AnnotationRead]
