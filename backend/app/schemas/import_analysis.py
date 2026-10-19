"""Validated model boundary; values are normalised before validation."""
from pydantic import BaseModel, ConfigDict, Field


class ImportAnalysisFields(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    doc_type: str | None = Field(default=None, max_length=64)
    issuer: str | None = Field(default=None, max_length=40)
    subject: str | None = Field(default=None, max_length=50)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    tags: list[str] = Field(default_factory=list, max_length=2)
    amount: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, pattern=r"^EUR$")
    summary: str | None = Field(default=None, max_length=240)
