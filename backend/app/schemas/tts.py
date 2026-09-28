from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Das konfigurierbare Betriebs-Limit wird im Router geprüft. Die obere
    # Schema-Grenze verhindert unabhängig davon übergroße Request-Bodies.
    text: str = Field(min_length=1, max_length=20000)
    voice: Literal["standard", "neutral", "amused", "sleepy", "whisper"] = "standard"

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("text must contain readable characters")
        return normalized
