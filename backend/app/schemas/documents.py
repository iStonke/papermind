import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.jobs import JobRead
from app.schemas.tags import TagRead
from app.services.utils import NAME_MAX_LENGTH, NAME_MIN_LENGTH, validate_vocab_name


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


class DocumentOCRQualityStatus(str, Enum):
    good = "good"
    warning = "warning"
    error = "error"


class DocumentEmbeddingStatus(str, Enum):
    not_started = "not_started"
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class DocumentAIStatus(str, Enum):
    pending = "pending"
    done = "done"
    skipped = "skipped"
    error = "error"


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
    is_favorite = "is_favorite"
    favorite = "favorite"


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
    document_type: str | None = Field(
        default=None,
        max_length=NAME_MAX_LENGTH,
        validation_alias=AliasChoices("document_type", "category"),
    )
    correspondent_id: uuid.UUID | None = Field(default=None)
    status: DocumentStatus | None = None
    display_name: str | None = Field(default=None, max_length=200)

    @field_validator("document_type")
    @classmethod
    def normalize_document_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        if not normalized:
            return None
        if len(normalized) < NAME_MIN_LENGTH:
            raise ValueError(f"Document type name must contain at least {NAME_MIN_LENGTH} characters")
        return validate_vocab_name(normalized, label="Document type name")

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
    is_deleted: bool = False
    is_favorite: bool = False
    document_date: date | None
    document_date_source: DocumentDateSource
    document_date_confidence: float | None
    document_date_candidates: list[dict[str, Any]] | None = None
    document_type: str | None = None
    category: str | None = None
    status: DocumentStatus
    ocr_status: DocumentOCRStatus
    ocr_quality_status: DocumentOCRQualityStatus | None = None
    ocr_confidence_score: float | None = None
    embedding_status: DocumentEmbeddingStatus
    ai_document_type: str | None = None
    ai_status: DocumentAIStatus = DocumentAIStatus.pending
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
    is_deleted: bool = False
    is_favorite: bool = False
    storage_key: str | None
    created_at: datetime
    updated_at: datetime
    document_date: date | None
    document_date_source: DocumentDateSource
    document_date_confidence: float | None
    document_date_candidates: list[dict[str, Any]] | None = None
    notes: str | None
    document_type: str | None = None
    category: str | None = None
    correspondent_id: uuid.UUID | None = None
    correspondent_name: str | None = None
    status: DocumentStatus
    ocr_status: DocumentOCRStatus
    ocr_quality_status: DocumentOCRQualityStatus | None = None
    ocr_confidence_score: float | None = None
    ocr_quality_message: str | None = None
    ocr_processing_seconds: float | None = None
    embedding_status: DocumentEmbeddingStatus
    embedding_model: str | None
    embedding_dim: int | None
    embedding_error: str | None
    embedding_updated_at: datetime | None
    ai_document_type: str | None = None
    ai_document_date: date | None = None
    ai_sender: str | None = None
    ai_recipient: str | None = None
    ai_amount: float | None = None
    ai_currency: str | None = None
    ai_summary: str | None = None
    ai_suggested_tags: list[str] | None = None
    ai_confidence: float | None = None
    ai_status: DocumentAIStatus = DocumentAIStatus.pending
    ai_processed_at: datetime | None = None
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


class DocumentMetadataSuggestion(BaseModel):
    """AI-derived metadata suggestions for a document's editable fields."""

    display_name: str | None = None
    document_date: date | None = None
    document_type: str | None = None
    category: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
