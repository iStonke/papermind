import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.jobs import JobRead
from app.schemas.tags import TagRead


class DocumentStatus(str, Enum):
    imported = "imported"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class DocumentFileRole(str, Enum):
    original = "original"
    ocr = "ocr"
    preview_pdf = "preview_pdf"
    thumbnail = "thumbnail"


class DocumentTextSource(str, Enum):
    none = "none"
    embedded = "embedded"
    ocr = "ocr"


class DocumentOCRStatus(str, Enum):
    not_started = "not_started"
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class DocumentEmbeddingStatus(str, Enum):
    not_started = "not_started"
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class DocumentDuplicateKind(str, Enum):
    exact = "exact"
    text = "text"
    image = "image"


class DocumentSortField(str, Enum):
    created_at = "created_at"
    document_date = "document_date"
    doc_date = "doc_date"
    updated_at = "updated_at"
    name = "name"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class DocumentCreateRequest(BaseModel):
    original_filename: str = Field(min_length=1, max_length=1000)
    document_date: date | None = Field(default=None, validation_alias=AliasChoices("document_date", "doc_date"))
    notes: str | None = Field(default=None, max_length=10000)


class DocumentUpdateRequest(BaseModel):
    document_date: date | None = Field(default=None, validation_alias=AliasChoices("document_date", "doc_date"))
    notes: str | None = Field(default=None, max_length=10000)
    status: DocumentStatus | None = None
    display_name: str | None = Field(default=None, max_length=200)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("display_name must not be empty")
        return normalized


class DocumentTagReplaceRequest(BaseModel):
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class DocumentDateSource(str, Enum):
    manual = "manual"
    ocr = "ocr"
    pdf_meta = "pdf_meta"


class DocumentFileRead(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    role: DocumentFileRole
    file_key: str
    filename: str | None
    mime_type: str
    bytes: int | None
    page_count: int | None
    created_at: datetime


class DocumentSummary(ORMModel):
    id: uuid.UUID
    original_filename: str
    display_name: str | None
    is_duplicate: bool = False
    duplicate_of_doc_id: uuid.UUID | None = None
    duplicate_kind: DocumentDuplicateKind | None = None
    duplicate_score: float | None = None
    is_unread: bool
    document_date: date | None
    document_date_source: DocumentDateSource
    document_date_confidence: float | None
    document_date_candidates: list[dict[str, Any]] | None = None
    status: DocumentStatus
    ocr_status: DocumentOCRStatus
    embedding_status: DocumentEmbeddingStatus
    created_at: datetime
    updated_at: datetime
    tags: list[TagRead] = Field(default_factory=list)
    snippet: str | None = None
    rank: float | None = None


class DocumentDetail(ORMModel):
    id: uuid.UUID
    original_filename: str
    display_name: str | None
    is_duplicate: bool = False
    duplicate_of_doc_id: uuid.UUID | None = None
    duplicate_kind: DocumentDuplicateKind | None = None
    duplicate_score: float | None = None
    is_unread: bool
    storage_key: str | None
    created_at: datetime
    updated_at: datetime
    document_date: date | None
    document_date_source: DocumentDateSource
    document_date_confidence: float | None
    document_date_candidates: list[dict[str, Any]] | None = None
    notes: str | None
    status: DocumentStatus
    ocr_status: DocumentOCRStatus
    embedding_status: DocumentEmbeddingStatus
    embedding_model: str | None
    embedding_dim: int | None
    embedding_error: str | None
    embedding_updated_at: datetime | None
    mime_type: str | None
    page_count: int | None
    flags: dict[str, Any] | None
    text_content: str | None
    text_source: DocumentTextSource
    tags: list[TagRead] = Field(default_factory=list)
    files: list[DocumentFileRead] = Field(default_factory=list)
    jobs: list[JobRead] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int
