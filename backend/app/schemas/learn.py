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
# Lernstand einer Karte (Selbsteinschätzung im Lernmodus).
CardStatus = Literal["open", "weak", "medium", "strong"]
# Abgeleiteter Status einer Notiz-Markierung (Rückkopplung in der Notiz).
MarkerReviewState = Literal["open", "card", "strong"]


class LearnProficiency(BaseModel):
    """Verteilung der Karten-Lernstände (für die Fortschrittsbalken)."""

    total: int = 0
    open: int = 0
    weak: int = 0
    medium: int = 0
    strong: int = 0


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
    card_count: int = 0
    proficiency: LearnProficiency = Field(default_factory=LearnProficiency)


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
    # Nur Karten mit befüllter Vorder- und Rückseite sind lernbereit.
    learnable_card_count: int = 0
    proficiency: LearnProficiency = Field(default_factory=LearnProficiency)
    # Dominanter Kartentyp (oder "gemischt"); für den Typ-Chip im Leuchttisch.
    kind_summary: str | None = None


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
    front: str = Field(default="", max_length=4000)
    back: str | None = Field(default=None, max_length=8000)
    payload: dict[str, Any] = Field(default_factory=dict)


class LearnCardUpdate(BaseModel):
    kind: ArtifactType | None = None
    front: str | None = Field(default=None, max_length=4000)
    back: str | None = Field(default=None, max_length=8000)
    payload: dict[str, Any] | None = None
    position: int | None = Field(default=None, ge=0, le=100000)
    status: CardStatus | None = None


class LearnCardReview(BaseModel):
    """Selbsteinschätzung im Lernmodus setzt den Lernstand einer Karte."""

    status: CardStatus


class LearnCardRead(ORMModel):
    id: uuid.UUID
    sheet_id: uuid.UUID
    kind: str
    front: str
    back: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    position: int
    status: str = "open"
    last_reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Herkunftsanker (gesetzt bei aus Nachbereitung entstandenen Karten).
    source_note_id: uuid.UUID | None = None
    source_pm_id: str | None = None


class LearnCardListResponse(BaseModel):
    items: list[LearnCardRead]


# --- Lerndurchlauf ---------------------------------------------------------
class LearnRunCreate(BaseModel):
    sheet_id: uuid.UUID | None = None
    scope: Literal["sheet", "course"] = "sheet"
    total_cards: int = Field(ge=1, le=100000)
    started_at: datetime | None = None


class LearnRunUpdate(BaseModel):
    assessed_cards: int = Field(ge=0, le=100000)
    weak_count: int = Field(ge=0, le=100000)
    medium_count: int = Field(ge=0, le=100000)
    strong_count: int = Field(ge=0, le=100000)
    completed_at: datetime | None = None


class LearnRunRead(ORMModel):
    id: uuid.UUID
    course_id: uuid.UUID
    sheet_id: uuid.UUID | None = None
    sheet_title: str | None = None
    scope: str
    total_cards: int
    assessed_cards: int
    weak_count: int
    medium_count: int
    strong_count: int
    started_at: datetime
    completed_at: datetime | None = None
    updated_at: datetime


class LearnRunListResponse(BaseModel):
    items: list[LearnRunRead]


# --- Marker (Projektion aus Notizen) ---------------------------------------
class LearnMarkerRead(ORMModel):
    id: uuid.UUID
    note_id: uuid.UUID
    node_pm_id: str
    kind: str
    snippet: str
    context: str = ""
    position: int
    created_at: datetime
    # Vom Service befüllt.
    note_title: str | None = None
    has_card: bool = False
    # Abgeleiteter Status der Markierung für die Rückkopplung in der Notiz:
    #   open   – noch keine vollständige Karte (Nachbereitung offen)
    #   card   – vollständige Karte vorhanden, aber noch nicht sicher gelernt
    #   strong – zugehörige Karte(n) sind als „sicher“ bewertet
    review_state: MarkerReviewState = "open"
    # Bei einem unvollständigen Kartenentwurf: dessen tatsächliche Zuordnung.
    # Frische Markierungen bleiben bis zur expliziten Kurswahl unzugeordnet.
    course_id: uuid.UUID | None = None
    course_title: str | None = None
    session_id: uuid.UUID | None = None
    session_title: str | None = None
    # Repräsentative verknüpfte Karte (vollständig bevorzugt, sonst Entwurf) –
    # Sprungziel für den „Karte öffnen“-Klick aus der Notiz.
    card_id: uuid.UUID | None = None
    card_sheet_id: uuid.UUID | None = None
    # Bereits angelegte, aber noch unvollständige Karte. Sie bleibt als
    # Nachbereitung sichtbar und wird beim erneuten Übernehmen aktualisiert.
    draft_card_id: uuid.UUID | None = None
    draft_sheet_id: uuid.UUID | None = None
    draft_kind: str | None = None
    draft_front: str | None = None
    draft_back: str | None = None


class LearnMarkerListResponse(BaseModel):
    items: list[LearnMarkerRead]


class LearnMarkerPromote(BaseModel):
    """Nachbereitung: einen offenen Marker in eine Lernkarte mit Anker überführen.

    Ziel wird über genau eine der drei Ebenen bestimmt (Vorrang: sheet_id →
    session_id → course_id). Bei ``session_id``/``course_id`` legt der Service
    bei Bedarf ein passendes Lernblatt an (find-or-create). Mit ``bind_note``
    wird die Mitschrift-Notiz dauerhaft der Sitzung zugeordnet, sodass weitere
    Marker derselben Notiz künftig automatisch zugeordnet sind.
    """

    note_id: uuid.UUID
    node_pm_id: str = Field(min_length=1, max_length=16)
    kind: ArtifactType = "fakt"
    front: str = Field(default="", max_length=4000)
    back: str | None = Field(default=None, max_length=8000)
    payload: dict[str, Any] = Field(default_factory=dict)
    sheet_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    bind_note: bool = False
