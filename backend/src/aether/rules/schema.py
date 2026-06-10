"""Pydantic models for YAML rule files.

A rule encodes: "if a news item from source S contains these keywords,
treat it as event E originating in country C, influencing region R,
with the following per-asset impact predictions."
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["low", "medium", "high"]
Direction = Literal["up", "down", "neutral"]
Magnitude = Literal["small", "medium", "large"]


class Trigger(BaseModel):
    """When does this rule fire?"""

    model_config = ConfigDict(extra="forbid")

    source: list[str] = Field(
        default_factory=list,
        description="Whitelist of raw_news.source values. Empty = any source.",
    )
    keywords_all: list[str] = Field(
        default_factory=list,
        description="Every keyword must appear in title|body (case-insensitive).",
    )
    keywords_any: list[str] = Field(
        default_factory=list,
        description="At least one keyword must appear. Empty = no constraint.",
    )
    keywords_none: list[str] = Field(
        default_factory=list,
        description="None of these may appear (exclusion guard).",
    )
    severity: Severity = "medium"


class Origin(BaseModel):
    """Geographic source of the event (for the map arc origin)."""

    model_config = ConfigDict(extra="forbid")

    country: str = Field(..., description="ISO 3166-1 alpha-2.")
    lat: float
    lng: float

    @field_validator("country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class Impact(BaseModel):
    """One predicted per-asset reaction."""

    model_config = ConfigDict(extra="forbid")

    asset: str = Field(..., description="Asset id from the `assets` table.")
    direction: Direction
    magnitude: Magnitude = "medium"
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    rationale: str = ""
    timeframe_minutes: int = Field(60, ge=1)


class Rule(BaseModel):
    """A single rule file's schema."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=64)
    name: str
    description: str = ""
    priority: int = Field(50, description="Higher fires first.")
    trigger: Trigger
    origin: Origin
    affected_regions: list[str] = Field(
        default_factory=list,
        description="Economic region ids (eurozone / g7 / opec_plus / ...).",
    )
    impacts: list[Impact] = Field(default_factory=list, min_length=1)
