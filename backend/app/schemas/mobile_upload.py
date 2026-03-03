from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MobileUploadSessionCreateRequest(BaseModel):
    maxFiles: int | None = Field(default=None, ge=1, le=200)
    targetStageId: str | None = None


class MobileUploadSessionCreateResponse(BaseModel):
    sessionId: str
    uploadUrl: str
    expiresAt: datetime
    targetStageId: str | None = None


class MobileUploadFileRead(BaseModel):
    id: str
    filename: str
    size: int = Field(ge=1)
    contentType: str
    createdAt: datetime
    sourceFileId: str
    pageCount: int = Field(ge=1)
    targetStageId: str | None = None


class MobileUploadStatusResponse(BaseModel):
    status: Literal["open", "uploaded", "closed", "expired"]
    filesCount: int = Field(ge=0)
    files: list[MobileUploadFileRead] = Field(default_factory=list)
    expiresAt: datetime
    maxFiles: int = Field(ge=1)


class MobileUploadFilesResponse(BaseModel):
    ok: bool = True
    uploaded: int = Field(ge=0)
