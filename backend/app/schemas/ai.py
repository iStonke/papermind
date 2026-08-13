import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AIRequestType(str, Enum):
    answer = "answer"
    summary = "summary"


class AIAskRequest(BaseModel):
    session_id: uuid.UUID | None = None
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=50)
    request_type: AIRequestType = AIRequestType.answer
    debug: bool = False
    doc_id: uuid.UUID | None = None


class AICitation(BaseModel):
    doc_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    chunk_index: int | None = None
    page_from: int | None = None
    page_to: int | None = None
    snippet: str
    document_title: str
    wiki_claim_ids: list[uuid.UUID] = Field(default_factory=list)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)


class AIKnowledgePageTrace(BaseModel):
    page_id: uuid.UUID
    title: str
    kind: str
    status: str
    revision_id: uuid.UUID | None = None
    score: float


class AIKnowledgeEvidenceTrace(BaseModel):
    evidence_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_id: uuid.UUID
    chunk_index: int | None = None
    page_from: int | None = None
    page_to: int | None = None
    quote: str
    chunk_content_hash: str


class AIKnowledgeClaimTrace(BaseModel):
    claim_id: uuid.UUID
    page_id: uuid.UUID
    page_title: str
    revision_id: uuid.UUID
    status: str
    text: str
    evidence: list[AIKnowledgeEvidenceTrace] = Field(default_factory=list)


class AIKnowledgeTrace(BaseModel):
    used: bool = False
    pages: list[AIKnowledgePageTrace] = Field(default_factory=list)
    claims: list[AIKnowledgeClaimTrace] = Field(default_factory=list)


class AIAskDebugRetrievalTimings(BaseModel):
    embed_ms: float
    db_ms: float
    total_ms: float


class AIAskDebugChunk(BaseModel):
    doc_id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    chunk_index: int | None = None
    page_from: int | None = None
    page_to: int | None = None
    chunk_type: str | None = None
    score: float
    preview: str = ""


class AIAskDebugRetrieval(BaseModel):
    timings: AIAskDebugRetrievalTimings
    num_hits: int
    best_score: float | None = None
    scores: list[float] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    context_chars: int
    chunks: list[AIAskDebugChunk] = Field(default_factory=list)


class AIAskDebugLLM(BaseModel):
    model_name: str
    temperature: float
    top_p: float
    max_tokens: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_ms: float
    timeout: bool
    retries: int


class AIAskDebugQualityFlags(BaseModel):
    empty_answer: bool = False
    numbers_without_citations: bool = False
    missing_citations: bool = False
    repair_pass_used: bool = False


class AIAskDebug(BaseModel):
    mode: str
    retrieval_model: str
    retrieval: AIAskDebugRetrieval
    llm: AIAskDebugLLM
    quality_flags: AIAskDebugQualityFlags
    total_ms: float


class AIAskMeta(BaseModel):
    request_id: str
    session_id: uuid.UUID
    mode: str
    rewritten_query: str
    embed_ms: float
    db_ms: float
    llm_ms: float
    total_ms: float
    assistant_message_id: uuid.UUID | None = None
    wiki_used: bool = False


class AIAskResponse(BaseModel):
    answer: str
    citations: list[AICitation] = Field(default_factory=list)
    knowledge_trace: AIKnowledgeTrace | None = None
    debug: AIAskDebug | None = None
    meta: AIAskMeta | None = None


class AIChatMessageRead(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_trace: dict[str, Any] | None = None
    created_at: datetime


class AIChatSessionSummary(BaseModel):
    session_id: uuid.UUID
    title: str | None = None
    message_count: int = 0
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AIChatSessionRead(AIChatSessionSummary):
    messages: list[AIChatMessageRead] = Field(default_factory=list)
