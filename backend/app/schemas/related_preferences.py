"""Personal ranking preferences shared by settings and recommendation previews."""
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RelatedProfile(str, Enum):
    balanced = "balanced"
    process = "process"
    thematic = "thematic"
    custom = "custom"


class RelatedWeight(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class RelatedWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    series: RelatedWeight = RelatedWeight.normal
    title: RelatedWeight = RelatedWeight.normal
    tags: RelatedWeight = RelatedWeight.normal
    correspondent: RelatedWeight = RelatedWeight.normal
    type: RelatedWeight = RelatedWeight.normal


PROFILE_WEIGHTS = {
    RelatedProfile.balanced: {},
    RelatedProfile.process: {"series": "high", "tags": "low", "correspondent": "high"},
    RelatedProfile.thematic: {"series": "low", "title": "high", "tags": "high", "correspondent": "low", "type": "low"},
}


class RelatedPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: RelatedProfile = RelatedProfile.balanced
    weights: RelatedWeights = Field(default_factory=RelatedWeights)

    @model_validator(mode="after")
    def resolve_profile(self):
        if self.profile != RelatedProfile.custom:
            self.weights = RelatedWeights(**PROFILE_WEIGHTS[self.profile])
        return self

    def factors(self) -> dict[str, float]:
        levels = {"low": .5, "normal": 1., "high": 2.}
        return {key: levels[value] for key, value in self.weights.model_dump(mode="json").items()}
