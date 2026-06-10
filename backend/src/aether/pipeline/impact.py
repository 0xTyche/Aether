"""Orchestrator: classify one RawNews item, persist Event + impact predictions.

Decision order:
  1. Try the rule engine (deterministic, free, zero-latency).
  2. If no rule fires, ask the LLM. If the LLM reports the news as not
     market-relevant, do nothing.

Either path produces an Event row plus N ImpactPrediction rows. The event
id is then published on the `events.new` Redis channel so a future
WebSocket hub (Phase 3) can fan out to clients.
"""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aether.models.assets import Asset
from aether.models.events import Event, ImpactPrediction
from aether.models.news import RawNews
from aether.pipeline import llm
from aether.rules.matcher import MatchInput, match
from aether.rules.schema import Rule
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)


async def _known_asset_ids(session: AsyncSession) -> set[str]:
    rows = await session.scalars(select(Asset.id))
    return set(rows.all())


def _build_event_from_rule(news: RawNews, rule: Rule) -> Event:
    return Event(
        raw_news_id=news.id,
        rule_id=rule.id,
        classifier="rule",
        severity=rule.trigger.severity,
        origin_country=rule.origin.country,
        origin_lat=rule.origin.lat,
        origin_lng=rule.origin.lng,
        affected_regions=list(rule.affected_regions) or None,
        title=news.title,
        explanation=rule.description or rule.name,
        occurred_at=news.published_at or datetime.now(UTC),
    )


def _build_event_from_llm(news: RawNews, analysis: llm.LLMAnalysis) -> Event:
    return Event(
        raw_news_id=news.id,
        rule_id=None,
        classifier="llm",
        severity=analysis.severity,
        origin_country=analysis.origin_country_iso2,
        # Lat/lng not provided by LLM; frontend looks them up by country code.
        origin_lat=None,
        origin_lng=None,
        affected_regions=list(analysis.affected_regions) or None,
        title=news.title,
        explanation=analysis.explanation,
        occurred_at=news.published_at or datetime.now(UTC),
    )


def _predictions_from_rule(event: Event, rule: Rule) -> list[ImpactPrediction]:
    return [
        ImpactPrediction(
            event_id=event.id,
            asset_id=imp.asset,
            direction=imp.direction,
            magnitude=imp.magnitude,
            confidence=imp.confidence,
            rationale=imp.rationale,
            timeframe_min=imp.timeframe_minutes,
        )
        for imp in rule.impacts
    ]


def _predictions_from_llm(
    event: Event, analysis: llm.LLMAnalysis, known_assets: set[str]
) -> list[ImpactPrediction]:
    """Filter out asset_ids the LLM hallucinated."""
    out: list[ImpactPrediction] = []
    for imp in analysis.impacts:
        if imp.asset_id not in known_assets:
            logger.warning(
                "pipeline.unknown_asset_filtered",
                asset_id=imp.asset_id,
                event_title=event.title[:80],
            )
            continue
        out.append(ImpactPrediction(
            event_id=event.id,
            asset_id=imp.asset_id,
            direction=imp.direction,
            magnitude=imp.magnitude,
            confidence=imp.confidence,
            rationale=imp.rationale,
        ))
    return out


def _serialize_for_pubsub(event: Event, predictions: list[ImpactPrediction]) -> dict:
    return {
        "id": str(event.id),
        "classifier": event.classifier,
        "severity": event.severity,
        "origin_country": event.origin_country,
        "origin_lat": event.origin_lat,
        "origin_lng": event.origin_lng,
        "affected_regions": event.affected_regions or [],
        "title": event.title,
        "explanation": event.explanation,
        "occurred_at": event.occurred_at.isoformat(),
        "predictions": [
            {
                "asset_id": p.asset_id,
                "direction": p.direction,
                "magnitude": p.magnitude,
                "confidence": p.confidence,
                "rationale": p.rationale,
                "timeframe_min": p.timeframe_min,
            }
            for p in predictions
        ],
    }


async def analyze_raw_news(
    news: RawNews,
    session: AsyncSession,
    *,
    rules: list[Rule],
    system_prompt: str,
) -> UUID | None:
    """Classify one news item end-to-end. Returns event.id or None if skipped."""
    item = MatchInput(source=news.source, title=news.title, body=news.body or "")
    rule = match(rules, item)

    event: Event
    predictions: list[ImpactPrediction]

    if rule is not None:
        event = _build_event_from_rule(news, rule)
        predictions = _predictions_from_rule(event, rule)
        logger.info("pipeline.rule_match", rule=rule.id, news_id=news.id)
    else:
        try:
            analysis = await llm.analyze_news(
                system_prompt=system_prompt,
                source=news.source,
                title=news.title,
                body=news.body,
            )
        except llm.LLMRateLimited:
            logger.warning("pipeline.llm_rate_limited", news_id=news.id)
            return None

        if analysis is None:
            logger.warning("pipeline.llm_failed", news_id=news.id)
            return None
        if not analysis.is_market_relevant or not analysis.impacts:
            logger.info("pipeline.skipped_irrelevant", news_id=news.id)
            return None

        known = await _known_asset_ids(session)
        event = _build_event_from_llm(news, analysis)
        predictions = _predictions_from_llm(event, analysis, known)
        if not predictions:
            logger.warning("pipeline.llm_all_assets_unknown", news_id=news.id)
            return None
        logger.info(
            "pipeline.llm_classified",
            news_id=news.id, impacts=len(predictions), severity=event.severity,
        )

    session.add(event)
    await session.flush()  # populate event.id before building predictions' FK
    for p in predictions:
        p.event_id = event.id
    session.add_all(predictions)
    await session.flush()

    await r.publish(r.CHANNEL_EVENTS_NEW, _serialize_for_pubsub(event, predictions))
    return event.id
