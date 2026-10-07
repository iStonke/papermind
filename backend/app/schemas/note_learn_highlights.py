import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.annotations import AnnotationRect
from app.schemas.common import ORMModel

LearnHighlightColor = Literal["important", "definition", "unclear"]


class NoteLearnHighlightCreate(BaseModel):
    document_id: uuid.UUID
    page: int = Field(ge=1)
    color: LearnHighlightColor
    rects: list[AnnotationRect] = Field(min_length=1, max_length=200)
    quote: str | None = Field(default=None, max_length=4000)


class NoteLearnHighlightUpdate(BaseModel):
    color: LearnHighlightColor


class NoteLearnHighlightRead(ORMModel):
    id: uuid.UUID
    note_id: uuid.UUID
    document_id: uuid.UUID
    page: int
    color: LearnHighlightColor
    rects: list[AnnotationRect]
    quote: str | None = None
    # Nur in der Dokument-Gesamtübersicht befüllt (transient, nicht gespeichert).
    note_title: str | None = None
    created_at: datetime
    updated_at: datetime


class NoteLearnHighlightListResponse(BaseModel):
    items: list[NoteLearnHighlightRead]
