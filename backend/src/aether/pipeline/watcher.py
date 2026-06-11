"""price_watcher — score each prediction once its time window has elapsed.

For every ImpactPrediction without an ImpactOutcome whose
`event.occurred_at + prediction.timeframe_min` is in the past, we:

  1. Pick t0 = latest price tick at or before the 5-minute bucket
     boundary that the event's occurred_at falls into. Intuition: the
     last "candle close" before the news hit, so we measure the move
     attributable to the event rather than to noise around publish time.
  2. Pick t1 = latest price tick at or before the 5-minute bucket
     boundary that (event.occurred_at + timeframe_min) falls into, plus
     one bucket (so the window is fully formed).
  3. pct = (t1 - t0) / t0 * 100. Score against the prediction's
     direction with a 0.10 percentage-point dead-band — moves smaller
     than that count as "partial" for directional predictions and "hit"
     for neutral predictions.
  4. Persist into impact_outcomes and publish each event's batch on
     the `impacts.outcome` Redis channel so the WS hub can fan out to
     connected clients.

Tolerance: if no tick is found within 30 minutes of a boundary the
outcome row is still written, but with NULL t0/t1/actual_*/accuracy.
That way the prediction is not re-scored on every tick forever.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aether.models.events import Event, ImpactOutcome, ImpactPrediction
from aether.storage import db as db_module
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)


BUCKET_MINUTES = 5
TOLERANCE_MINUTES = 30
DEAD_BAND_PCT = Decimal("0.10")
BATCH_LIMIT = 200


def _floor_bucket(t: datetime, minutes: int = BUCKET_MINUTES) -> datetime:
    """Round t down to the nearest `minutes` boundary."""
    epoch_min = int(t.timestamp() // (minutes * 60)) * (minutes * 60)
    return datetime.fromtimestamp(epoch_min, tz=t.tzinfo)


def _ceil_bucket(t: datetime, minutes: int = BUCKET_MINUTES) -> datetime:
    """Round t up to the next `minutes` boundary (exclusive end of bucket)."""
    floored = _floor_bucket(t, minutes)
    if floored == t:
        return floored
    return floored + timedelta(minutes=minutes)


async def _price_at_or_before(
    session: AsyncSession,
    asset_id: str,
    boundary: datetime,
) -> Decimal | None:
    """Latest tick ts <= boundary, within TOLERANCE_MINUTES of it."""
    earliest = boundary - timedelta(minutes=TOLERANCE_MINUTES)
    stmt = (
        select(text("price"))
        .select_from(text("prices"))
        .where(text("asset_id = :aid"))
        .where(text("ts <= :b"))
        .where(text("ts >= :e"))
        .order_by(text("ts DESC"))
        .limit(1)
    )
    res = await session.execute(
        stmt, {"aid": asset_id, "b": boundary, "e": earliest}
    )
    row = res.first()
    return Decimal(str(row[0])) if row is not None else None


def _direction_from_pct(pct: Decimal) -> str:
    if pct > DEAD_BAND_PCT:
        return "up"
    if pct < -DEAD_BAND_PCT:
        return "down"
    return "flat"


def _accuracy(predicted_direction: str, pct: Decimal) -> str:
    """Map (predicted, actual pct) → hit / miss / partial."""
    if predicted_direction == "neutral":
        return "hit" if abs(pct) < DEAD_BAND_PCT else "miss"
    if abs(pct) < DEAD_BAND_PCT:
        return "partial"
    if predicted_direction == "up":
        return "hit" if pct > 0 else "miss"
    if predicted_direction == "down":
        return "hit" if pct < 0 else "miss"
    return "miss"  # unknown direction, defensive


async def _ready_predictions(session: AsyncSession) -> list[tuple[ImpactPrediction, Event]]:
    """Predictions whose window has elapsed and which have no outcome yet."""
    now = func.now()
    deadline = Event.occurred_at + func.make_interval(
        text("0"), text("0"), text("0"), text("0"), text("0"), ImpactPrediction.timeframe_min * 60
    )
    # SQLAlchemy: easier expressed via raw INTERVAL multiplication.
    stmt = (
        select(ImpactPrediction, Event)
        .join(Event, ImpactPrediction.event_id == Event.id)
        .outerjoin(
            ImpactOutcome, ImpactOutcome.prediction_id == ImpactPrediction.id
        )
        .where(ImpactOutcome.prediction_id.is_(None))
        .where(
            text(
                "events.occurred_at + (impact_predictions.timeframe_min || ' minutes')::interval <= now()"
            )
        )
        .order_by(ImpactPrediction.id)
        .limit(BATCH_LIMIT)
    )
    # `deadline` variable above unused; kept SQL via text() for clarity.
    _ = (now, deadline)
    rows = (await session.execute(stmt)).all()
    return [(p, e) for p, e in rows]


async def _score_one(
    session: AsyncSession, prediction: ImpactPrediction, event: Event
) -> dict[str, Any]:
    """Compute and persist the outcome for one prediction. Returns the
    serialized payload for Redis publish."""
    event_time = event.occurred_at
    boundary_t0 = _floor_bucket(event_time)
    boundary_t1 = _ceil_bucket(event_time + timedelta(minutes=prediction.timeframe_min))

    t0 = await _price_at_or_before(session, prediction.asset_id, boundary_t0)
    t1 = await _price_at_or_before(session, prediction.asset_id, boundary_t1)

    actual_pct: Decimal | None = None
    actual_direction: str | None = None
    accuracy: str | None = None
    if t0 is not None and t1 is not None and t0 != 0:
        actual_pct = ((t1 - t0) / t0) * Decimal("100")
        actual_direction = _direction_from_pct(actual_pct)
        accuracy = _accuracy(prediction.direction, actual_pct)
    else:
        logger.info(
            "watcher.no_price_data",
            prediction_id=prediction.id,
            asset_id=prediction.asset_id,
            event_id=str(event.id),
            t0_found=t0 is not None,
            t1_found=t1 is not None,
        )

    outcome = ImpactOutcome(
        prediction_id=prediction.id,
        t0_price=t0,
        t1_price=t1,
        actual_pct=float(actual_pct) if actual_pct is not None else None,
        actual_direction=actual_direction,
        accuracy=accuracy,
    )
    session.add(outcome)

    return {
        "prediction_id": prediction.id,
        "event_id": str(event.id),
        "asset_id": prediction.asset_id,
        "predicted_direction": prediction.direction,
        "t0_price": str(t0) if t0 is not None else None,
        "t1_price": str(t1) if t1 is not None else None,
        "actual_pct": float(actual_pct) if actual_pct is not None else None,
        "actual_direction": actual_direction,
        "accuracy": accuracy,
    }


async def tick() -> dict[str, int]:
    """One scoring pass. Returns counts: {scored, no_data, by_accuracy}."""
    scored = 0
    no_data = 0
    accuracy_tally: dict[str, int] = {"hit": 0, "miss": 0, "partial": 0}
    by_event: dict[UUID, list[dict[str, Any]]] = {}

    async with db_module.session_scope() as session:
        pairs = await _ready_predictions(session)
        for prediction, event in pairs:
            payload = await _score_one(session, prediction, event)
            scored += 1
            if payload["accuracy"] is None:
                no_data += 1
            else:
                accuracy_tally[payload["accuracy"]] = (
                    accuracy_tally.get(payload["accuracy"], 0) + 1
                )
            by_event.setdefault(event.id, []).append(payload)

    # Publish one message per event so the WS hub can fan-out a complete
    # batch atomically to subscribers.
    for event_id, outcomes in by_event.items():
        try:
            await r.publish(
                r.CHANNEL_IMPACTS_OUTCOME,
                {"event_id": str(event_id), "outcomes": outcomes},
            )
        except Exception as exc:
            logger.warning(
                "watcher.publish_failed", event_id=str(event_id), error=str(exc)
            )

    if scored:
        logger.info(
            "watcher.tick",
            scored=scored,
            no_data=no_data,
            **accuracy_tally,
        )
    return {
        "scored": scored,
        "no_data": no_data,
        **accuracy_tally,
    }
