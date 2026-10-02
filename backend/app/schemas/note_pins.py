import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.common import ORMModel
from app.schemas.notes import NoteTagRef

class PinTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Bitte einen Gedanken eingeben.")
        return value.replace("\r\n", "\n").replace("\r", "\n")

class PinPositionRequest(BaseModel):
    position_x: int = Field(ge=0, le=100000)
    position_y: int = Field(ge=0, le=100000)
    base_updated_at: datetime

class PinCreateRequest(PinTextRequest):
    room_id: uuid.UUID | None = None
    title_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    request_id: uuid.UUID | None = None
    collection_id: uuid.UUID
    # None: the server picks a free spot (e.g. quick capture from the command palette).
    position_x: int | None = Field(default=None, ge=0, le=100000)
    position_y: int | None = Field(default=None, ge=0, le=100000)

    @model_validator(mode="after")
    def _position_pair(self):
        if (self.position_x is None) != (self.position_y is None):
            raise ValueError("position_x und position_y müssen gemeinsam angegeben werden")
        return self

class PinUpdateRequest(PinTextRequest):
    title_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    base_updated_at: datetime

class PinRead(ORMModel):
    room_id: uuid.UUID | None = None
    title_color: str | None = None
    id: uuid.UUID
    collection_id: uuid.UUID
    text: str
    status: str
    position_x: int | None = None
    position_y: int | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[NoteTagRef] = Field(default_factory=list)

class PinListResponse(BaseModel):
    items: list[PinRead]

class PinCountResponse(BaseModel):
    count: int

class PinArchiveRequest(BaseModel):
    collection_id: uuid.UUID
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    archived: bool = True

class RoomRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Bitte einen Namen eingeben.")
        return value.strip()

class RoomCreateRequest(BaseModel):
    collection_id: uuid.UUID
    title: str | None = Field(default=None, min_length=1, max_length=120)
    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        return RoomRequest.clean_title(value) if value is not None else None

class RoomRead(ORMModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    content: str = ""

class PinColorBatchRequest(BaseModel):
    room_id: uuid.UUID
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    title_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    base_updated_at: dict[uuid.UUID, datetime]

class PinPositionItem(PinPositionRequest):
    id: uuid.UUID

class PinPositionBatchRequest(BaseModel):
    room_id: uuid.UUID
    items: list[PinPositionItem] = Field(min_length=1, max_length=500)
    @field_validator("items")
    @classmethod
    def unique_ids(cls, value):
        if len({item.id for item in value}) != len(value):
            raise ValueError("Jeder Gedanke darf nur einmal enthalten sein.")
        return value

class ThoughtSummaryRead(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=30000)
    @field_validator("title", "content")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Die Zusammenfassung ist leer.")
        return value.strip()
