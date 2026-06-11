"""price_watcher: bucket math, scoring, persistence, publish."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from aether.models.events import Event, ImpactOutcome, ImpactPrediction
from aether.models.news import RawNews
from aether.models.prices import Price
from aether.pipeline import watcher
from aether.storage import db as db_module
from aether.storage import redis_ as r
from scripts.seed_assets import seed_assets


# ---------- bucket math --------------------------------------------------

def test_floor_bucket_rounds_down_to_5min():
    t = datetime(2026, 6, 11, 14, 32, 17, tzinfo=UTC)
    assert watcher._floor_bucket(t) == datetime(2026, 6, 11, 14, 30, tzinfo=UTC)


def test_floor_bucket_exact_boundary_no_change():
    t = datetime(2026, 6, 11, 14, 35, 0, tzinfo=UTC)
    assert watcher._floor_bucket(t) == t


def test_ceil_bucket_rounds_up_to_next_5min():
    t = datetime(2026, 6, 11, 14, 32, 17, tzinfo=UTC)
    assert watcher._ceil_bucket(t) == datetime(2026, 6, 11, 14, 35, tzinfo=UTC)


def test_ceil_bucket_exact_boundary_no_change():
    t = datetime(2026, 6, 11, 14, 30, 0, tzinfo=UTC)
    assert watcher._ceil_bucket(t) == t


# ---------- accuracy table -----------------------------------------------

@pytest.mark.parametrize(
    ("direction", "pct", "expected"),
    [
        ("up",   Decimal("0.50"),  "hit"),
        ("up",   Decimal("-0.50"), "miss"),
        ("up",   Decimal("0.05"),  "partial"),
        ("up",   Decimal("-0.05"), "partial"),
        ("down", Decimal("-0.50"), "hit"),
        ("down", Decimal("0.50"),  "miss"),
        ("down", Decimal("0.05"),  "partial"),
        ("neutral", Decimal("0.05"),  "hit"),
        ("neutral", Decimal("0.50"),  "miss"),
        ("neutral", Decimal("-0.50"), "miss"),
    ],
)
def test_accuracy_table(direction, pct, expected):
    assert watcher._accuracy(direction, pct) == expected


def test_direction_from_pct_dead_band():
    assert watcher._direction_from_pct(Decimal("0.05")) == "flat"
    assert watcher._direction_from_pct(Decimal("0.50")) == "up"
    assert watcher._direction_from_pct(Decimal("-0.50")) == "down"


# ---------- end-to-end tick ---------------------------------------------

@pytest_asyncio.fixture
async def fresh_db():
    async with db_module.session_scope() as session:
        await session.execute(text(
            "TRUNCATE TABLE impact_outcomes, impact_predictions, events, "
            "raw_news, prices, assets, "
            "country_economic_memberships, economic_regions "
            "RESTART IDENTITY CASCADE"
        ))
        await session.commit()
        await seed_assets(session)


async def _seed_event_and_prediction(
    *, occurred_minutes_ago: int, timeframe_min: int, direction: str
) -> tuple[UUID, int]:
    occurred = datetime.now(UTC) - timedelta(minutes=occurred_minutes_ago)
    async with db_module.session_scope() as session:
        news = RawNews(
            source="Test", url=f"t/{occurred.timestamp()}",
            title="x", published_at=occurred,
        )
        session.add(news)
        await session.flush()
        event = Event(
            raw_news_id=news.id, classifier="rule", severity="high",
            origin_country="JP", origin_lat=35.68, origin_lng=139.70,
            title="x", explanation="x", occurred_at=occurred,
        )
        session.add(event)
        await session.flush()
        pred = ImpactPrediction(
            event_id=event.id, asset_id="BTC", direction=direction,
            magnitude="medium", confidence=0.8, rationale="x",
            timeframe_min=timeframe_min,
        )
        session.add(pred)
        await session.flush()
        return event.id, pred.id


async def _insert_price(asset_id: str, ts: datetime, price: Decimal | str):
    async with db_module.session_scope() as session:
        session.add(Price(asset_id=asset_id, ts=ts, price=Decimal(str(price)), source="test"))


async def _outcomes_count() -> int:
    async with db_module.session_scope() as session:
        return await session.scalar(select(text("count(*)")).select_from(ImpactOutcome))


@pytest.mark.usefixtures("fresh_db")
async def test_tick_scores_prediction_window_elapsed_hit():
    # Event 2 hours ago, timeframe 60 min — fully ready.
    event_id, pred_id = await _seed_event_and_prediction(
        occurred_minutes_ago=120, timeframe_min=60, direction="up",
    )
    occurred = datetime.now(UTC) - timedelta(minutes=120)
    bucket_t0 = watcher._floor_bucket(occurred)
    bucket_t1 = watcher._ceil_bucket(occurred + timedelta(minutes=60))
    # Plant a tick right before each boundary so we have data.
    await _insert_price("BTC", bucket_t0 - timedelta(seconds=10), "60000")
    await _insert_price("BTC", bucket_t1 - timedelta(seconds=10), "60900")  # +1.5%

    counts = await watcher.tick()
    assert counts["scored"] == 1
    assert counts["hit"] == 1

    async with db_module.session_scope() as session:
        out = await session.get(ImpactOutcome, pred_id)
    assert out is not None
    assert out.t0_price == Decimal("60000")
    assert out.t1_price == Decimal("60900")
    assert out.actual_pct is not None and abs(out.actual_pct - 1.5) < 0.001
    assert out.actual_direction == "up"
    assert out.accuracy == "hit"


@pytest.mark.usefixtures("fresh_db")
async def test_tick_records_miss_when_direction_wrong():
    event_id, pred_id = await _seed_event_and_prediction(
        occurred_minutes_ago=120, timeframe_min=60, direction="up",
    )
    occurred = datetime.now(UTC) - timedelta(minutes=120)
    await _insert_price("BTC", watcher._floor_bucket(occurred) - timedelta(seconds=1), "60000")
    await _insert_price("BTC", watcher._ceil_bucket(occurred + timedelta(minutes=60)) - timedelta(seconds=1), "58800")  # -2%

    counts = await watcher.tick()
    assert counts["miss"] == 1
    async with db_module.session_scope() as session:
        out = await session.get(ImpactOutcome, pred_id)
    assert out.accuracy == "miss"
    assert out.actual_direction == "down"


@pytest.mark.usefixtures("fresh_db")
async def test_tick_records_partial_when_small_move():
    event_id, pred_id = await _seed_event_and_prediction(
        occurred_minutes_ago=120, timeframe_min=60, direction="up",
    )
    occurred = datetime.now(UTC) - timedelta(minutes=120)
    await _insert_price("BTC", watcher._floor_bucket(occurred) - timedelta(seconds=1), "60000")
    await _insert_price("BTC", watcher._ceil_bucket(occurred + timedelta(minutes=60)) - timedelta(seconds=1), "60018")  # +0.03%

    counts = await watcher.tick()
    assert counts["partial"] == 1
    async with db_module.session_scope() as session:
        out = await session.get(ImpactOutcome, pred_id)
    assert out.accuracy == "partial"


@pytest.mark.usefixtures("fresh_db")
async def test_tick_writes_null_outcome_when_no_price_data():
    event_id, pred_id = await _seed_event_and_prediction(
        occurred_minutes_ago=120, timeframe_min=60, direction="up",
    )
    # No prices inserted for BTC.

    counts = await watcher.tick()
    assert counts["scored"] == 1
    assert counts["no_data"] == 1

    async with db_module.session_scope() as session:
        out = await session.get(ImpactOutcome, pred_id)
    assert out is not None
    assert out.t0_price is None and out.t1_price is None
    assert out.accuracy is None


@pytest.mark.usefixtures("fresh_db")
async def test_tick_does_not_score_future_predictions():
    # Event 30 min ago, timeframe 120 min — window not elapsed yet.
    await _seed_event_and_prediction(
        occurred_minutes_ago=30, timeframe_min=120, direction="up",
    )
    counts = await watcher.tick()
    assert counts["scored"] == 0
    assert await _outcomes_count() == 0


@pytest.mark.usefixtures("fresh_db")
async def test_tick_is_idempotent():
    event_id, pred_id = await _seed_event_and_prediction(
        occurred_minutes_ago=120, timeframe_min=60, direction="up",
    )
    occurred = datetime.now(UTC) - timedelta(minutes=120)
    await _insert_price("BTC", watcher._floor_bucket(occurred) - timedelta(seconds=1), "60000")
    await _insert_price("BTC", watcher._ceil_bucket(occurred + timedelta(minutes=60)) - timedelta(seconds=1), "60900")

    first = await watcher.tick()
    second = await watcher.tick()
    assert first["scored"] == 1
    assert second["scored"] == 0  # outcome row exists; nothing to re-score
    assert await _outcomes_count() == 1


@pytest.mark.usefixtures("fresh_db")
async def test_tick_publishes_impacts_outcome_on_redis():
    event_id, pred_id = await _seed_event_and_prediction(
        occurred_minutes_ago=120, timeframe_min=60, direction="up",
    )
    occurred = datetime.now(UTC) - timedelta(minutes=120)
    await _insert_price("BTC", watcher._floor_bucket(occurred) - timedelta(seconds=1), "60000")
    await _insert_price("BTC", watcher._ceil_bucket(occurred + timedelta(minutes=60)) - timedelta(seconds=1), "60900")

    received: asyncio.Queue[dict] = asyncio.Queue()

    async def listener():
        async with r.subscribe(r.CHANNEL_IMPACTS_OUTCOME) as sub:
            async for msg in sub.listen():
                if msg["type"] == "message":
                    received.put_nowait(json.loads(msg["data"]))
                    return

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.1)

    await watcher.tick()

    payload = await asyncio.wait_for(received.get(), timeout=2.0)
    await task
    assert payload["event_id"] == str(event_id)
    assert len(payload["outcomes"]) == 1
    o = payload["outcomes"][0]
    assert o["prediction_id"] == pred_id
    assert o["asset_id"] == "BTC"
    assert o["accuracy"] == "hit"
    assert o["actual_direction"] == "up"
