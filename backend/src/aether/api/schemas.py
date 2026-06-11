"""Pydantic response models for the REST API.

These are pure DTOs — no DB session, no async — so they can be referenced
from both router handlers and tests without pulling in the ORM machinery.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssetDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_class: str
    display_name: str
    country_iso: str | None
    region: str | None
    lat: float | None
    lng: float | None


class RegionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label_zh: str
    label_en: str
    region_type: str
    central_bank: str | None
    members: list[str]


class PriceDTO(BaseModel):
    asset_id: str
    price: Decimal
    ts: datetime
    source: str


class ImpactPredictionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: str
    direction: str
    magnitude: str
    confidence: float | None
    rationale: str | None
    timeframe_min: int


class EventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    classifier: str
    rule_id: str | None
    severity: str
    origin_country: str | None
    origin_lat: float | None
    origin_lng: float | None
    affected_regions: list[str] | None
    title: str
    explanation: str | None
    occurred_at: datetime
    created_at: datetime
    predictions: list[ImpactPredictionDTO] = []


class AccuracyBucketDTO(BaseModel):
    """Aggregate accuracy stats for one slice of impact_outcomes."""

    key: str
    total: int
    scored: int
    hits: int
    misses: int
    partials: int
    hit_rate: float | None  # hits / scored ; None if scored == 0


class AccuracyStatsDTO(BaseModel):
    overall: AccuracyBucketDTO
    by_classifier: list[AccuracyBucketDTO]
    by_severity: list[AccuracyBucketDTO]
    by_rule: list[AccuracyBucketDTO]

