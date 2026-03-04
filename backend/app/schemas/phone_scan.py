from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PhoneScanSessionCreateRequest(BaseModel):
    maxFiles: int | None = Field(default=None, ge=1, le=200)
    stageId: str | None = None


class PhoneScanSessionCreateResponse(BaseModel):
    token: str
    sessionId: str
    expiresAt: datetime
    stageId: str | None = None
    uploadUrl: str
    statusUrl: str


class PhoneScanFileRead(BaseModel):
    id: str
    filename: str
    size: int = Field(ge=1)
    contentType: str
    createdAt: datetime
    sourceFileId: str
    pageCount: int = Field(ge=1)
    targetStageId: str | None = None


class PhoneScanUploadResponse(BaseModel):
    received: int = Field(ge=0)
    jobId: str


class PhoneScanStatusResponse(BaseModel):
    state: Literal["waiting", "receiving", "processing", "ready", "error", "expired", "closed"]
    step: str | None = None
    progress: int = Field(ge=0, le=100)
    filesCount: int = Field(ge=0)
    files: list[PhoneScanFileRead] = Field(default_factory=list)
    last3Uploads: list[str] = Field(default_factory=list)
    expiresAt: datetime
    maxFiles: int = Field(ge=1)
    stageId: str | None = None
    resultDocId: str | None = None
    errorMessage: str | None = None
