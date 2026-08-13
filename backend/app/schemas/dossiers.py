import uuid
from datetime import date, datetime
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import ORMModel


class DossierState(str, Enum):
    active = "active"
    closed = "closed"


class DossierPropertyType(str, Enum):
    text = "text"
    date = "date"
    number = "number"
    boolean = "boolean"


class DossierItemType(str, Enum):
    document = "document"
    note = "note"
    link = "link"
    image = "image"


class DossierPropertyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None = None
    label: str = Field(min_length=1, max_length=120)
    value_type: DossierPropertyType = DossierPropertyType.text
    value_text: str | None = Field(default=None, max_length=2000)
    value_date: date | None = None
    value_number: float | None = None
    value_boolean: bool | None = None

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("label must not be empty")
        return normalized


class DossierPropertyRead(DossierPropertyWrite):
    id: uuid.UUID
    sort_order: int


class DossierCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    dossier_type: str | None = Field(default=None, max_length=120)
    reference: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    state: DossierState = DossierState.active
    opened_on: date | None = None
    closed_on: date | None = None
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=64)
    properties: list[DossierPropertyWrite] = Field(default_factory=list, max_length=100)

    @field_validator("title", "dossier_type", "reference")
    @classmethod
    def normalize_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_title_and_dates(self) -> "DossierCreateRequest":
        if not self.title:
            raise ValueError("title must not be empty")
        if self.opened_on and self.closed_on and self.opened_on > self.closed_on:
            raise ValueError("closed_on must be on or after opened_on")
        return self


class DossierUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=240)
    dossier_type: str | None = Field(default=None, max_length=120)
    reference: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    state: DossierState | None = None
    opened_on: date | None = None
    closed_on: date | None = None
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=64)
    is_favorite: bool | None = None
    archived: bool | None = None
    properties: list[DossierPropertyWrite] | None = Field(default=None, max_length=100)

    @field_validator("title", "dossier_type", "reference")
    @classmethod
    def normalize_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "DossierUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class DossierRead(ORMModel):
    id: uuid.UUID
    title: str
    dossier_type: str | None = None
    reference: str | None = None
    description: str | None = None
    state: DossierState
    opened_on: date | None = None
    closed_on: date | None = None
    color: str | None = None
    icon: str | None = None
    is_favorite: bool = False
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    properties: list[DossierPropertyRead] = Field(default_factory=list)


class DossierGroupSummary(BaseModel):
    name: str
    count: int = 0


class DossierListItem(DossierRead):
    document_count: int = 0
    image_count: int = 0
    item_count: int = 0
    group_count: int = 0
    preview_document_ids: list[uuid.UUID] = Field(default_factory=list)
    groups: list[DossierGroupSummary] = Field(default_factory=list)
    top_note: str | None = None


class DossierListResponse(BaseModel):
    items: list[DossierListItem]


_POS_MIN = -200_000.0
_POS_MAX = 200_000.0


class DossierGroupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    color: str | None = Field(default=None, max_length=16)
    pos_x: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    pos_y: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized


class DossierGroupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    color: str | None = Field(default=None, max_length=16)
    pos_x: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    pos_y: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized


class DossierGroupRead(ORMModel):
    id: uuid.UUID
    dossier_id: uuid.UUID
    title: str
    color: str | None = None
    sort_order: int
    pos_x: float | None = None
    pos_y: float | None = None
    created_at: datetime
    updated_at: datetime


class DossierGroupOrderRequest(BaseModel):
    group_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


class DossierDocumentSummary(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    document_date: date | None = None
    document_type: str | None = None
    correspondent_name: str | None = None
    page_count: int | None = None
    is_deleted: bool = False


class DossierItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: DossierItemType
    group_id: uuid.UUID | None = None
    pos_x: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    pos_y: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    document_id: uuid.UUID | None = None
    attached_to_item_id: uuid.UUID | None = None
    note_title: str | None = Field(default=None, max_length=240)
    note_body: str | None = Field(default=None, max_length=50000)
    note_color: str | None = Field(default=None, max_length=16)
    link_title: str | None = Field(default=None, max_length=240)
    link_url: str | None = Field(default=None, max_length=2048)
    link_description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_payload(self) -> "DossierItemCreateRequest":
        if self.item_type == DossierItemType.document and self.document_id is None:
            raise ValueError("document_id is required for document items")
        if self.item_type == DossierItemType.document and self.attached_to_item_id is not None:
            raise ValueError("document items cannot be attached to another item")
        if self.item_type == DossierItemType.image:
            raise ValueError("image items must be created through the image upload endpoint")
        if self.item_type == DossierItemType.link:
            _validate_web_url(self.link_url)
        return self


class DossierItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: uuid.UUID | None = None
    attached_to_item_id: uuid.UUID | None = None
    pos_x: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    pos_y: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    note_title: str | None = Field(default=None, max_length=240)
    note_body: str | None = Field(default=None, max_length=50000)
    note_color: str | None = Field(default=None, max_length=16)
    link_title: str | None = Field(default=None, max_length=240)
    link_url: str | None = Field(default=None, max_length=2048)
    link_description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_update(self) -> "DossierItemUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        if "link_url" in self.model_fields_set and self.link_url is not None:
            _validate_web_url(self.link_url)
        return self


class DossierItemRead(ORMModel):
    id: uuid.UUID
    dossier_id: uuid.UUID
    group_id: uuid.UUID | None = None
    item_type: DossierItemType
    sort_order: int
    pos_x: float | None = None
    pos_y: float | None = None
    document_id: uuid.UUID | None = None
    attached_to_item_id: uuid.UUID | None = None
    document: DossierDocumentSummary | None = None
    note_title: str | None = None
    note_body: str | None = None
    note_color: str | None = None
    link_title: str | None = None
    link_url: str | None = None
    link_description: str | None = None
    image_filename: str | None = None
    image_content_type: str | None = None
    image_file_key: str | None = None
    image_size_bytes: int | None = None
    image_width: int | None = None
    image_height: int | None = None
    created_at: datetime
    updated_at: datetime


class DossierDocumentsAddRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    group_id: uuid.UUID | None = None


class DossierDocumentsAddResponse(BaseModel):
    items: list[DossierItemRead]
    skipped_document_ids: list[uuid.UUID] = Field(default_factory=list)


class DossierItemPlacement(BaseModel):
    item_id: uuid.UUID
    group_id: uuid.UUID | None = None
    sort_order: int = Field(ge=0, le=10_000_000)
    pos_x: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    pos_y: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)


class DossierItemsReorderRequest(BaseModel):
    placements: list[DossierItemPlacement] = Field(min_length=1, max_length=2000)


class DossierItemsDeleteRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)

    @field_validator("item_ids")
    @classmethod
    def validate_unique_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("item_ids must be unique")
        return value


class DossierItemRestoreWrite(BaseModel):
    """Vollständiger Karten-Snapshot für das unmittelbare Undo eines Löschvorgangs."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    item_type: DossierItemType
    group_id: uuid.UUID | None = None
    sort_order: int = Field(ge=0, le=10_000_000)
    pos_x: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    pos_y: float | None = Field(default=None, ge=_POS_MIN, le=_POS_MAX)
    document_id: uuid.UUID | None = None
    attached_to_item_id: uuid.UUID | None = None
    note_title: str | None = Field(default=None, max_length=240)
    note_body: str | None = Field(default=None, max_length=50000)
    note_color: str | None = Field(default=None, max_length=16)
    link_title: str | None = Field(default=None, max_length=240)
    link_url: str | None = Field(default=None, max_length=2048)
    link_description: str | None = Field(default=None, max_length=2000)
    image_filename: str | None = Field(default=None, max_length=512)
    image_content_type: str | None = Field(default=None, max_length=32)
    image_file_key: str | None = Field(default=None, max_length=2048)
    image_size_bytes: int | None = Field(default=None, ge=1)
    image_width: int | None = Field(default=None, ge=1)
    image_height: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_payload(self) -> "DossierItemRestoreWrite":
        if self.item_type == DossierItemType.document:
            if self.document_id is None:
                raise ValueError("document_id is required for document items")
            if self.attached_to_item_id is not None:
                raise ValueError("document items cannot be attached to another item")
        elif self.document_id is not None:
            raise ValueError("document_id is only allowed for document items")
        if self.item_type == DossierItemType.link:
            _validate_web_url(self.link_url)
        if self.item_type == DossierItemType.image:
            required = (
                self.image_filename,
                self.image_content_type,
                self.image_file_key,
                self.image_size_bytes,
                self.image_width,
                self.image_height,
            )
            if any(value is None for value in required):
                raise ValueError("image metadata is required for image items")
            if self.image_content_type not in {"image/jpeg", "image/png"}:
                raise ValueError("image_content_type must be image/jpeg or image/png")
        return self


class DossierItemsRestoreRequest(BaseModel):
    items: list[DossierItemRestoreWrite] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "DossierItemsRestoreRequest":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("item ids must be unique")
        return self


class DossierItemsBatchResponse(BaseModel):
    items: list[DossierItemRead]


class DossierBoardResponse(BaseModel):
    dossier: DossierRead
    groups: list[DossierGroupRead]
    items: list[DossierItemRead]


def _validate_web_url(value: str | None) -> None:
    parsed = urlparse((value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("link_url must be an http or https URL")
