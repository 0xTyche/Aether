"""Accuracy stats endpoint: aggregates over impact_outcomes."""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from aether.models.events import Event, ImpactOutcome, ImpactPrediction
from aether.models.news import RawNews
from aether.storage import db as db_module
from scripts.seed_assets import seed_assets


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


@pytest_asyncio.fixture
async def client(fresh_db):
    from aether.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _insert_outcome(
    *,
    classifier: str,
    severity: str,
    rule_id: str | None,
    asset_id: str,
    accuracy: str | None,
    direction: str = "up",
) -> None:
    async with db_module.session_scope() as session:
        news = RawNews(
            source="t", url=f"t/{datetime.now(UTC).timestamp()}-{accuracy}-{rule_id}",
            title="x", published_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(news)
        await session.flush()
        event = Event(
            raw_news_id=news.id, classifier=classifier, rule_id=rule_id,
            severity=severity, origin_country="US",
            title="x", explanation="x",
            occurred_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        prediction = ImpactPrediction(
            event_id=event.id, asset_id=asset_id, direction=direction,
            magnitude="medium", confidence=0.8, timeframe_min=60,
        )
        session.add(prediction)
        await session.flush()
        session.add(ImpactOutcome(
            prediction_id=prediction.id,
            t0_price=100 if accuracy else None,
            t1_price=101 if accuracy else None,
            actual_pct=1.0 if accuracy else None,
            actual_direction="up" if accuracy else None,
            accuracy=accuracy,
        ))


async def test_stats_empty(client):
    res = await client.get("/api/stats/accuracy")
    assert res.status_code == 200
    body = res.json()
    assert body["overall"]["scored"] == 0
    assert body["overall"]["hit_rate"] is None
    assert body["by_classifier"] == []


async def test_stats_overall_and_classifier_breakdown(client):
    await _insert_outcome(classifier="rule", severity="high", rule_id="fed_rate_hike",
                          asset_id="USD/JPY", accuracy="hit")
    await _insert_outcome(classifier="rule", severity="high", rule_id="fed_rate_hike",
                          asset_id="SPX", accuracy="hit")
    await _insert_outcome(classifier="rule", severity="high", rule_id="fed_rate_hike",
                          asset_id="GOLD", accuracy="miss")
    await _insert_outcome(classifier="llm", severity="medium", rule_id=None,
                          asset_id="BRENT", accuracy="partial")
    await _insert_outcome(classifier="llm", severity="medium", rule_id=None,
                          asset_id="WTI", accuracy=None)  # no data

    res = await client.get("/api/stats/accuracy")
    body = res.json()

    # Overall
    o = body["overall"]
    assert o["total"] == 5
    assert o["scored"] == 4
    assert o["hits"] == 2
    assert o["misses"] == 1
    assert o["partials"] == 1
    assert abs(o["hit_rate"] - 0.5) < 1e-9

    # By classifier
    classifiers = {b["key"]: b for b in body["by_classifier"]}
    assert classifiers["rule"]["hits"] == 2
    assert classifiers["rule"]["misses"] == 1
    assert classifiers["rule"]["scored"] == 3
    assert abs(classifiers["rule"]["hit_rate"] - (2 / 3)) < 1e-9
    assert classifiers["llm"]["partials"] == 1
    assert classifiers["llm"]["scored"] == 1
    assert classifiers["llm"]["hits"] == 0
    assert classifiers["llm"]["hit_rate"] == 0.0


async def test_stats_severity_and_rule_breakdown(client):
    await _insert_outcome(classifier="rule", severity="high", rule_id="fed_rate_hike",
                          asset_id="USD/JPY", accuracy="hit")
    await _insert_outcome(classifier="rule", severity="low", rule_id="fed_rate_hold",
                          asset_id="SPX", accuracy="partial")

    res = await client.get("/api/stats/accuracy")
    body = res.json()

    sev_keys = {b["key"]: b for b in body["by_severity"]}
    assert "high" in sev_keys and "low" in sev_keys
    assert sev_keys["high"]["hits"] == 1
    assert sev_keys["low"]["partials"] == 1

    rule_keys = {b["key"]: b for b in body["by_rule"]}
    assert "fed_rate_hike" in rule_keys
    assert "fed_rate_hold" in rule_keys
    # Rules with no rule_id (LLM events) are excluded from by_rule.
    assert "None" not in rule_keys
