"""Pipeline orchestrator: rule match, LLM fallback, dedup, publish."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from aether.models.events import Event, ImpactPrediction
from aether.models.news import RawNews
from aether.pipeline import impact, processor
from aether.pipeline import llm
from aether.rules.matcher import MatchInput
from aether.rules.schema import Impact as RuleImpact
from aether.rules.schema import Origin, Rule, Trigger
from aether.storage import db as db_module
from aether.storage import redis_ as r
from scripts.seed_assets import seed_assets
from scripts.seed_economic_regions import seed_all as seed_regions


@pytest_asyncio.fixture
async def fresh_pipeline_state():
    """Clean DB tables and Redis state for a deterministic pipeline run."""
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

    client = r.get_redis()
    async for key in client.scan_iter(match="processed:news:*"):
        await client.delete(key)
    async for key in client.scan_iter(match="rate:llm:*"):
        await client.delete(key)

    processor.reset_cache_for_tests()
    yield


def _sample_rule() -> Rule:
    return Rule(
        id="test_boj_hike",
        name="Test BoJ rate hike",
        priority=100,
        trigger=Trigger(
            source=["BoJ"],
            keywords_all=["policy rate"],
            keywords_any=["raise", "hike"],
            keywords_none=["unchanged"],
            severity="high",
        ),
        origin=Origin(country="JP", lat=35.68, lng=139.70),
        affected_regions=["g7"],
        impacts=[
            RuleImpact(asset="USD/JPY", direction="down", magnitude="large",
                       confidence=0.9, rationale="rates"),
            RuleImpact(asset="NKY", direction="down", magnitude="medium",
                       confidence=0.7, rationale="equities"),
        ],
    )


async def _insert_news(source: str, title: str, body: str = "") -> int:
    async with db_module.session_scope() as session:
        news = RawNews(
            source=source, url=f"https://test.example/{title[:30]}",
            title=title, body=body,
            published_at=datetime.now(UTC),
        )
        session.add(news)
        await session.flush()
        nid = news.id
    return nid


# ---------- impact.analyze_raw_news --------------------------------------

@pytest.mark.usefixtures("fresh_pipeline_state")
async def test_rule_match_writes_event_and_predictions():
    nid = await _insert_news("BoJ", "BoJ raises policy rate to 0.50%", "")
    async with db_module.session_scope() as session:
        news = await session.get(RawNews, nid)
        eid = await impact.analyze_raw_news(
            news, session, rules=[_sample_rule()], system_prompt="unused",
        )
    assert eid is not None

    async with db_module.session_scope() as session:
        evt = await session.get(Event, eid)
        preds = (await session.scalars(
            select(ImpactPrediction).where(ImpactPrediction.event_id == eid)
        )).all()
    assert evt is not None
    assert evt.classifier == "rule"
    assert evt.rule_id == "test_boj_hike"
    assert evt.affected_regions == ["g7"]
    assert {p.asset_id for p in preds} == {"USD/JPY", "NKY"}


@pytest.mark.usefixtures("fresh_pipeline_state")
async def test_no_rule_falls_through_to_llm_and_persists():
    nid = await _insert_news("Reuters", "Some unique unmatched headline X42", "")
    llm_payload = json.dumps({
        "is_market_relevant": True,
        "severity": "medium",
        "origin_country_iso2": "US",
        "explanation": "ad-hoc analysis",
        "affected_regions": ["g7"],
        "impacts": [
            {"asset_id": "SPX", "direction": "up", "magnitude": "small",
             "confidence": 0.6, "rationale": "from LLM"},
        ],
    })
    fake_completions = AsyncMock()
    fake_completions.create = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=llm_payload))]
    ))
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

    with patch.object(llm, "_get_client", return_value=fake_client):
        async with db_module.session_scope() as session:
            news = await session.get(RawNews, nid)
            eid = await impact.analyze_raw_news(
                news, session, rules=[], system_prompt="sys",
            )
    assert eid is not None

    async with db_module.session_scope() as session:
        evt = await session.get(Event, eid)
        preds = (await session.scalars(
            select(ImpactPrediction).where(ImpactPrediction.event_id == eid)
        )).all()
    assert evt.classifier == "llm"
    assert evt.rule_id is None
    assert [p.asset_id for p in preds] == ["SPX"]


@pytest.mark.usefixtures("fresh_pipeline_state")
async def test_llm_irrelevant_returns_none():
    nid = await _insert_news("Reuters", "Some sport game story", "")
    payload = json.dumps({
        "is_market_relevant": False, "severity": "low", "impacts": [],
    })
    fake_completions = AsyncMock(create=AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
    )))
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))
    with patch.object(llm, "_get_client", return_value=fake_client):
        async with db_module.session_scope() as session:
            news = await session.get(RawNews, nid)
            eid = await impact.analyze_raw_news(
                news, session, rules=[], system_prompt="sys",
            )
    assert eid is None

    async with db_module.session_scope() as session:
        n = await session.scalar(select(Event).where(Event.raw_news_id == nid))
    assert n is None


@pytest.mark.usefixtures("fresh_pipeline_state")
async def test_llm_unknown_asset_ids_filtered():
    nid = await _insert_news("Reuters", "Headline mentioning AAAA1234", "")
    payload = json.dumps({
        "is_market_relevant": True,
        "severity": "medium",
        "origin_country_iso2": "US",
        "explanation": "test",
        "affected_regions": [],
        "impacts": [
            {"asset_id": "SPX", "direction": "up"},
            {"asset_id": "FAKE_NOT_REAL_ASSET", "direction": "down"},
        ],
    })
    fake_completions = AsyncMock(create=AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
    )))
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))
    with patch.object(llm, "_get_client", return_value=fake_client):
        async with db_module.session_scope() as session:
            news = await session.get(RawNews, nid)
            eid = await impact.analyze_raw_news(
                news, session, rules=[], system_prompt="sys",
            )
    assert eid is not None
    async with db_module.session_scope() as session:
        preds = (await session.scalars(
            select(ImpactPrediction).where(ImpactPrediction.event_id == eid)
        )).all()
    assert [p.asset_id for p in preds] == ["SPX"]


@pytest.mark.usefixtures("fresh_pipeline_state")
async def test_publishes_to_events_new_channel():
    nid = await _insert_news("BoJ", "BoJ raises policy rate", "")
    received: asyncio.Queue[dict] = asyncio.Queue()

    async def listener():
        async with r.subscribe(r.CHANNEL_EVENTS_NEW) as sub:
            async for msg in sub.listen():
                if msg["type"] == "message":
                    received.put_nowait(json.loads(msg["data"]))
                    return

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.1)

    async with db_module.session_scope() as session:
        news = await session.get(RawNews, nid)
        await impact.analyze_raw_news(
            news, session, rules=[_sample_rule()], system_prompt="sys",
        )

    got = await asyncio.wait_for(received.get(), timeout=2.0)
    await task
    assert got["classifier"] == "rule"
    assert {p["asset_id"] for p in got["predictions"]} == {"USD/JPY", "NKY"}


# ---------- processor.tick ----------------------------------------------

@pytest.mark.usefixtures("fresh_pipeline_state")
async def test_processor_only_processes_unseen_news():
    # Insert two news items, one matches our rule, one doesn't.
    a = await _insert_news("BoJ", "BoJ raises policy rate alpha", "")
    b = await _insert_news("BoJ", "BoJ raises policy rate beta", "")

    rule = _sample_rule()
    with patch.object(processor, "_ensure_loaded",
                      AsyncMock(return_value=(
                          SimpleNamespace(rules=[rule]),
                          "sys",
                      ))):
        first = await processor.tick()
    assert first["events"] == 2

    # Run again immediately — both should be deduped.
    with patch.object(processor, "_ensure_loaded",
                      AsyncMock(return_value=(
                          SimpleNamespace(rules=[rule]),
                          "sys",
                      ))):
        second = await processor.tick()
    assert second["events"] == 0
    # `dup` only fires when Redis key exists; the DB-side notin_() filter
    # might also exclude them. Either way no new events should be created.
    async with db_module.session_scope() as session:
        n = await session.scalar(
            select(text("count(*)")).select_from(Event)
        )
    assert n == 2  # still just the 2 originals
