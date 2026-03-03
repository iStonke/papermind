import uuid

from pydantic import BaseModel, Field
from enum import Enum


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


class AIAskResponse(BaseModel):
    answer: str
    citations: list[AICitation] = Field(default_factory=list)
    debug: AIAskDebug | None = None
    meta: AIAskMeta | None = None
