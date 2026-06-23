from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorData(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorData


class OkResponse(BaseModel):
    ok: bool = True


class CountResponse(OkResponse):
    count: int = 0


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
