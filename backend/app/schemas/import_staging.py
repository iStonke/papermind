import uuid

from pydantic import BaseModel, Field, field_validator


class ImportSourceRead(BaseModel):
    source_file_id: str
    original_name: str
    page_count: int = Field(ge=1)


class ImportSourceUploadResponse(BaseModel):
    items: list[ImportSourceRead] = Field(default_factory=list)


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
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    pages: list[ImportCommitPageInput] = Field(default_factory=list)


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
    meta: dict[str, str | float | None] = Field(default_factory=dict)
