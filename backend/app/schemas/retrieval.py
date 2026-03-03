import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    doc_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None


class RetrievalQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=100)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)


class RetrievalResult(BaseModel):
    doc_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    page_from: int | None
    page_to: int | None
    chunk_type: str | None = None
    score: float
    text: str


class RetrievalTimings(BaseModel):
    embed_ms: float
    db_ms: float
    total_ms: float


class RetrievalQueryResponse(BaseModel):
    query: str
    model: str
    dim: int
    top_k: int
    results: list[RetrievalResult]
    timings: RetrievalTimings


class DocumentChunkDebugRead(BaseModel):
    id: uuid.UUID
    chunk_index: int
    page_from: int | None
    page_to: int | None
    chunk_type: str | None = None
    char_len: int
    token_len: int | None
    content_hash: str


class DocumentChunkListResponse(BaseModel):
    document_id: uuid.UUID
    chunk_count: int
    items: list[DocumentChunkDebugRead]


class DocumentEmbeddingStatusResponse(BaseModel):
    document_id: uuid.UUID
    embedding_status: str
    chunk_count: int
    embedded_count: int
    model: str | None
    dim: int | None
    text_hash: str | None
    updated_at: datetime | None
    last_error: str | None
