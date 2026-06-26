import uuid
from datetime import date as date_cls, datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.services.utils import NAME_MAX_LENGTH, NAME_MIN_LENGTH, validate_vocab_name


class ImportSourceRead(BaseModel):
    source_file_id: str
    original_name: str
    page_count: int = Field(ge=1)


class ImportSourceUploadResponse(BaseModel):
    items: list[ImportSourceRead] = Field(default_factory=list)


class ImportInboxItemRead(BaseModel):
    id: str
    source_file_id: str
    original_name: str
    page_count: int = Field(ge=1)
    client_name: str | None = None
    source_type: str = "shortcut"
    scanner_device_id: str | None = None
    is_assigned_to_me: bool = True
    created_at: datetime


class ImportInboxUploadResponse(BaseModel):
    items: list[ImportInboxItemRead] = Field(default_factory=list)
    pending_count: int = Field(default=0, ge=0)


class ImportInboxListResponse(BaseModel):
    items: list[ImportInboxItemRead] = Field(default_factory=list)
    pending_count: int = Field(default=0, ge=0)
    scanning: bool = False


class ImportInboxClaimRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class ImportInboxClaimResponse(BaseModel):
    claimed: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)


class ImportInboxAssignRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class ImportInboxAssignResponse(BaseModel):
    assigned: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)


class ImportInboxDiscardRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class ImportInboxDiscardResponse(BaseModel):
    discarded: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)


class ImportInboxDiscardPagesRequest(BaseModel):
    page_indices: list[int] = Field(default_factory=list)

    @field_validator("page_indices")
    @classmethod
    def validate_page_indices(cls, value: list[int]) -> list[int]:
        normalized = []
        seen = set()
        for page_index in value:
            index = int(page_index)
            if index < 0:
                raise ValueError("page_indices must be greater than or equal to 0")
            if index in seen:
                continue
            seen.add(index)
            normalized.append(index)
        if not normalized:
            raise ValueError("page_indices is required")
        return normalized


class ImportInboxDiscardPagesResponse(BaseModel):
    source_file_id: str
    page_count: int = Field(default=0, ge=0)
    pending_count: int = Field(default=0, ge=0)


class ImportCommitPageInput(BaseModel):
    source_file_id: str = Field(min_length=1)
    page_index: int = Field(ge=0)
    rotation: int = Field(default=0)

    @field_validator("rotation")
    @classmethod
    def validate_rotation(cls, value: int) -> int:
        normalized = int(value)
        if normalized not in (0, 90, 180, 270):
            raise ValueError("rotation must be one of 0, 90, 180, 270")
        return normalized


class ImportCommitDocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    document_type: str | None = Field(
        default=None,
        max_length=NAME_MAX_LENGTH,
        validation_alias=AliasChoices("document_type", "category"),
    )
    correspondent_id: uuid.UUID | None = Field(default=None)
    date: date_cls | None = Field(default=None)
    note: str | None = Field(default=None, max_length=2000)
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    pages: list[ImportCommitPageInput] = Field(default_factory=list)

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

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ImportCommitOptions(BaseModel):
    auto_ocr: bool = True
    auto_index: bool = True
    auto_embed: bool = True


class ImportCommitRequest(BaseModel):
    documents: list[ImportCommitDocumentInput] = Field(default_factory=list)
    options: ImportCommitOptions = Field(default_factory=ImportCommitOptions)


class ImportCommitCreatedItem(BaseModel):
    doc_id: str
    title: str
    page_count: int = Field(ge=1)


class ImportCommitErrorItem(BaseModel):
    document_index: int | None = None
    title: str | None = None
    message: str


class ImportCommitResponse(BaseModel):
    created: list[ImportCommitCreatedItem] = Field(default_factory=list)
    errors: list[ImportCommitErrorItem] = Field(default_factory=list)


class StageTitlePageScope(str):
    FIRST_PAGE = "first_page"
    ALL_PAGES = "all_pages"


class StageTitleSuggestRequest(BaseModel):
    sourceFileIds: list[str] = Field(default_factory=list, min_length=1)
    pageScope: str = Field(default=StageTitlePageScope.FIRST_PAGE)

    @field_validator("pageScope")
    @classmethod
    def validate_page_scope(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {StageTitlePageScope.FIRST_PAGE, StageTitlePageScope.ALL_PAGES}:
            raise ValueError("pageScope must be 'first_page' or 'all_pages'")
        return normalized


class StageTitleSuggestResponse(BaseModel):
    suggestion: str
    status: str = "ready"
    pageScope: str = StageTitlePageScope.FIRST_PAGE
    usedFallback: bool = False
    meta: dict[str, object] = Field(default_factory=dict)
