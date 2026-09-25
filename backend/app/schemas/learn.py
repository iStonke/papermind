import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

ArtifactType = Literal[
    "fakt", "prozess", "zusammenhang", "prozedural", "verstaendnis", "uebung"
]
SheetScope = Literal["session", "topic"]
SheetStatus = Literal["draft", "in_progress", "worked", "archived"]


# --- Kurs ------------------------------------------------------------------
class LearnCourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    module_key: str | None = Field(default=None, max_length=64)
    default_artifact_type: ArtifactType = "fakt"
    has_script: bool = False
    color: str | None = Field(default=None, max_length=32)


class LearnCourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    module_key: str | None = Field(default=None, max_length=64)
    default_artifact_type: ArtifactType | None = None
    has_script: bool | None = None
    color: str | None = Field(default=None, max_length=32)
    is_archived: bool | None = None
    position: int | None = Field(default=None, ge=0, le=100000)


class LearnCourseRead(ORMModel):
    id: uuid.UUID
    title: str
    module_key: str | None = None
    default_artifact_type: str
    has_script: bool
    color: str | None = None
    is_archived: bool
    position: int
    created_at: datetime
    updated_at: datetime
    # Vom Service befüllt (nicht auf dem Modell).
    session_count: int = 0
    sheet_count: int = 0


class LearnCourseListResponse(BaseModel):
    items: list[LearnCourseRead]


# --- Sitzung ----------------------------------------------------------------
class LearnSessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    session_date: date | None = None
    note_id: uuid.UUID | None = None
    ordinal: int = Field(default=0, ge=0, le=100000)


class LearnSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    session_date: date | None = None
    note_id: uuid.UUID | None = None
    ordinal: int | None = Field(default=None, ge=0, le=100000)


class LearnSessionRead(ORMModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    session_date: date | None = None
    note_id: uuid.UUID | None = None
    ordinal: int
    created_at: datetime
    updated_at: datetime
    sheet_count: int = 0


class LearnSessionListResponse(BaseModel):
    items: list[LearnSessionRead]


# --- Lernblatt --------------------------------------------------------------
class LearnSheetCreate(BaseModel):
    course_id: uuid.UUID
    session_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    scope: SheetScope = "session"
    status: SheetStatus = "draft"
    is_favorite: bool = False
    structure: dict[str, Any] = Field(default_factory=dict)
    source_label: str | None = Field(default=None, max_length=500)


class LearnSheetUpdate(BaseModel):
    session_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    scope: SheetScope | None = None
    status: SheetStatus | None = None
    is_favorite: bool | None = None
    structure: dict[str, Any] | None = None
    source_label: str | None = Field(default=None, max_length=500)
    position: int | None = Field(default=None, ge=0, le=100000)


class LearnSheetRead(ORMModel):
    id: uuid.UUID
    course_id: uuid.UUID
    session_id: uuid.UUID | None = None
    title: str
    scope: str
    status: str
    is_favorite: bool
    structure: dict[str, Any]
    source_label: str | None = None
    position: int
    created_at: datetime
    updated_at: datetime
    # Vom Service befüllt (Anzahl Karten/Artefakte – vorerst 0).
    card_count: int = 0


class LearnSheetListResponse(BaseModel):
    items: list[LearnSheetRead]


# --- Board (Artboard 1a: Sitzungen mit ihren Lernblättern) ------------------
class LearnBoardSession(BaseModel):
    id: uuid.UUID
    title: str
    session_date: date | None = None
    ordinal: int
    sheets: list[LearnSheetRead] = Field(default_factory=list)


class LearnBoardResponse(BaseModel):
    course: LearnCourseRead
    sessions: list[LearnBoardSession] = Field(default_factory=list)
    # Lernblätter ohne Sitzung (themenübergreifend / verwaist).
    loose_sheets: list[LearnSheetRead] = Field(default_factory=list)


# --- Karte (Artefakt) -------------------------------------------------------
class LearnCardCreate(BaseModel):
    kind: ArtifactType = "fakt"
    front: str = Field(min_length=1, max_length=4000)
    back: str | None = Field(default=None, max_length=8000)


class LearnCardUpdate(BaseModel):
    kind: ArtifactType | None = None
    front: str | None = Field(default=None, min_length=1, max_length=4000)
    back: str | None = Field(default=None, max_length=8000)
    position: int | None = Field(default=None, ge=0, le=100000)


class LearnCardRead(ORMModel):
    id: uuid.UUID
    sheet_id: uuid.UUID
    kind: str
    front: str
    back: str | None = None
    position: int
    created_at: datetime
    updated_at: datetime


class LearnCardListResponse(BaseModel):
    items: list[LearnCardRead]
