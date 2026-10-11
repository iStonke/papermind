from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SpeechPronunciation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    word: str = Field(min_length=1, max_length=120)
    pronunciation: str = Field(min_length=1, max_length=300)
    case_sensitive: bool = False
    enabled: bool = True

    @field_validator("word", "pronunciation")
    @classmethod
    def single_line(cls, value: str) -> str:
        if any(char in value for char in "\r\n\x00"):
            raise ValueError("Pronunciations must be a single line")
        return value


class SpeechOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    engine: Literal["piper", "kokoro", "cosyvoice"] = "piper"
    speed: float = Field(default=1.0, ge=0.6, le=1.5)
    sentence_pause: float = Field(default=0.18, ge=0.05, le=0.8)
    paragraph_pause: float = Field(default=0.38, ge=0.1, le=1.8)
    normalize_numbers: bool = True
    pronunciations: list[SpeechPronunciation] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def coherent_options(self) -> "SpeechOptions":
        if self.paragraph_pause < self.sentence_pause:
            raise ValueError("Paragraph pauses must be at least as long as sentence pauses")
        seen = set()
        for entry in self.pronunciations:
            key = entry.word if entry.case_sensitive else entry.word.casefold()
            identity = (key, entry.case_sensitive)
            if identity in seen:
                raise ValueError("Duplicate pronunciation entry")
            seen.add(identity)
        return self
