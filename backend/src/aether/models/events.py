"""Events (classified raw_news) + impact predictions & outcomes."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from aether.models.base import Base


class Event(Base):
    """A raw_news entry promoted to a market-moving event."""

    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_occurred", "occurred_at"),
        Index("idx_events_regions", "affected_regions", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    raw_news_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("raw_news.id"), nullable=True
    )
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classifier: Mapped[str] = mapped_column(String(16), nullable=False)  # rule | llm
    severity: Mapped[str] = mapped_column(String(8), nullable=False)  # low | med | high
    origin_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    origin_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    affected_regions: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(32)), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional richer reasoning from the LLM (classification, transmission_chain).
    # NULL for rule-engine events.
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    predictions: Mapped[list["ImpactPrediction"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class ImpactPrediction(Base):
    """Per-asset prediction emitted by rule engine or LLM for an event."""

    __tablename__ = "impact_predictions"
    __table_args__ = (Index("idx_impact_event", "event_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("assets.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # up | down | neutral
    magnitude: Mapped[str] = mapped_column(String(8), nullable=False)  # small | med | large
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeframe_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    event: Mapped[Event] = relationship(back_populates="predictions")
    outcome: Mapped["ImpactOutcome | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )


class ImpactOutcome(Base):
    """Realised price move after the prediction window closes."""

    __tablename__ = "impact_outcomes"

    prediction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("impact_predictions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    t0_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    t1_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    actual_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    accuracy: Mapped[str | None] = mapped_column(String(8), nullable=True)  # hit | miss | partial
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    prediction: Mapped[ImpactPrediction] = relationship(back_populates="outcome")
