"""REST API contract tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from aether.api.schemas import AssetDTO, EventDTO, RegionDTO
from aether.models.events import Event, ImpactPrediction
from aether.models.news import RawNews
from aether.models.prices import Price
from aether.storage import db as db_module
from scripts.seed_assets import seed_assets
from scripts.seed_economic_regions import seed_all as seed_regions


@pytest_asyncio.fixture
async def app_state_clean():
    """A clean DB seeded with assets + regions; no events/prices yet."""
    async with db_module.session_scope() as session:
        await session.execute(text(
            "TRUNCATE TABLE impact_outcomes, impact_predictions, events, "
            "raw_news, prices, assets, "
            "country_economic_memberships, economic_regions "
            "RESTART IDENTITY CASCADE"
        ))
        await session.commit()
        await seed_assets(session)
        await seed_regions(session)


@pytest_asyncio.fixture
async def client(app_state_clean):
    """ASGI httpx client bypassing TCP — avoids tripping the lifespan."""
    from aether.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------- /api/assets -------------------------------------------------

async def test_assets_returns_seeded_set(client):
    res = await client.get("/api/assets")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 143
    # Sanity check on shape via Pydantic.
    AssetDTO.model_validate(data[0])
    ids = {a["id"] for a in data}
    assert {"BTC", "USD/JPY", "SPX", "GOLD", "GOOGL", "ADA"}.issubset(ids)


async def test_assets_have_expected_classes(client):
    res = await client.get("/api/assets")
    by_class: dict[str, int] = {}
    for a in res.json():
        by_class[a["asset_class"]] = by_class.get(a["asset_class"], 0) + 1
    assert by_class["fx"] == 20
    assert by_class["crypto"] == 16
    assert by_class["equity"] == 70
    assert by_class["rate"] == 14


# ---------- /api/regions ------------------------------------------------

async def test_regions_returns_seeded_6_with_members(client):
    res = await client.get("/api/regions")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 6
    RegionDTO.model_validate(data[0])

    by_id = {r["id"]: r for r in data}
    assert len(by_id["eurozone"]["members"]) == 20
    assert len(by_id["g7"]["members"]) == 7
    assert "JP" in by_id["g7"]["members"]


# ---------- /api/events -------------------------------------------------

async def _insert_event_with_predictions(*, age_minutes: int = 0) -> UUID:
    occurred = datetime.now(UTC) - timedelta(minutes=age_minutes)
    async with db_module.session_scope() as session:
        news = RawNews(
            source="BoJ",
            url=f"https://t/{age_minutes}-{occurred.timestamp()}",
            title=f"Test event ({age_minutes}m old)",
            published_at=occurred,
        )
        session.add(news)
        await session.flush()
        event = Event(
            raw_news_id=news.id,
            rule_id="boj_rate_hike",
            classifier="rule",
            severity="high",
            origin_country="JP",
            origin_lat=35.68,
            origin_lng=139.70,
            affected_regions=["g7"],
            title=news.title,
            explanation="testing",
            occurred_at=occurred,
        )
        session.add(event)
        await session.flush()
        session.add_all([
            ImpactPrediction(
                event_id=event.id, asset_id="USD/JPY", direction="down",
                magnitude="large", confidence=0.9, rationale="rates",
            ),
            ImpactPrediction(
                event_id=event.id, asset_id="NKY", direction="down",
                magnitude="medium", confidence=0.7, rationale="equities",
            ),
        ])
        await session.flush()
        return event.id


async def test_events_empty_when_none(client):
    res = await client.get("/api/events")
    assert res.status_code == 200
    assert res.json() == []


async def test_events_returns_with_predictions_newest_first(client):
    old = await _insert_event_with_predictions(age_minutes=120)
    new = await _insert_event_with_predictions(age_minutes=5)

    res = await client.get("/api/events?limit=10")
    data = res.json()
    assert len(data) == 2
    # newest first
    assert data[0]["id"] == str(new)
    assert data[1]["id"] == str(old)
    # predictions hydrated
    assert {p["asset_id"] for p in data[0]["predictions"]} == {"USD/JPY", "NKY"}
    EventDTO.model_validate(data[0])


async def test_events_since_filter(client):
    await _insert_event_with_predictions(age_minutes=200)
    new = await _insert_event_with_predictions(age_minutes=2)
    cutoff = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    res = await client.get("/api/events", params={"since": cutoff})
    data = res.json()
    assert len(data) == 1, f"expected 1, got {data}"
    assert data[0]["id"] == str(new)


async def test_event_detail(client):
    eid = await _insert_event_with_predictions(age_minutes=1)
    res = await client.get(f"/api/events/{eid}")
    assert res.status_code == 200
    assert res.json()["id"] == str(eid)
    assert len(res.json()["predictions"]) == 2


async def test_event_detail_404(client):
    bogus = "00000000-0000-0000-0000-000000000000"
    res = await client.get(f"/api/events/{bogus}")
    assert res.status_code == 404


# ---------- /api/prices/latest -----------------------------------------

async def test_prices_latest_returns_latest_per_asset(client):
    older = datetime.now(UTC) - timedelta(minutes=2)
    newer = datetime.now(UTC) - timedelta(seconds=10)
    async with db_module.session_scope() as session:
        session.add_all([
            Price(asset_id="BTC", ts=older, price=60000, source="binance"),
            Price(asset_id="BTC", ts=newer, price=61000, source="binance"),
            Price(asset_id="ETH", ts=older, price=1600, source="binance"),
        ])

    res = await client.get("/api/prices/latest")
    assert res.status_code == 200
    by_asset = {p["asset_id"]: p for p in res.json()}
    assert by_asset["BTC"]["price"] == "61000"
    assert by_asset["ETH"]["price"] == "1600"
