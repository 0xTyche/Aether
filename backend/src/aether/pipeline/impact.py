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
from math import prod
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aether.mechanisms.catalog import default_library
from aether.mechanisms.loader import MechanismLibrary
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


def _known_mechanism(mechanism_id: str | None, library: MechanismLibrary) -> str | None:
    """Keep a card id only if the library has it; the model may invent one."""
    if mechanism_id is None:
        return None
    if library.card(mechanism_id) is None:
        logger.warning("pipeline.unknown_mechanism_filtered", mechanism_id=mechanism_id)
        return None
    return mechanism_id


def _mechanism_summary(
    ids: list[str], library: MechanismLibrary
) -> tuple[list[dict[str, Any]], float | None]:
    """Resolve the model's chain of card ids and multiply their priors.

    The priors are unreviewed drafts, so each entry carries its evidence
    tier and review status for the UI to show next to the number.
    """
    cards: list[dict[str, Any]] = []
    for card_id in ids:
        if _known_mechanism(card_id, library) is None:
            continue
        card = library.cards[card_id]
        cards.append({
            "id": card.id,
            "name": card.name,
            "prior": card.prior,
            "evidence_tier": card.evidence_tier,
            "review_status": card.review.status,
        })
    if not cards:
        return [], None
    return cards, round(prod(c["prior"] for c in cards), 4)


def _impact_metadata(imp: llm.LLMImpactBase, library: MechanismLibrary) -> dict[str, Any]:
    """Fields shared by in-pool predictions and off-pool entries."""
    return {
        "direction": imp.direction,
        "magnitude": imp.magnitude,
        "confidence": imp.confidence,
        "timeframe_min": imp.horizon_min,
        "crowding": imp.crowding,
        "mechanism_id": _known_mechanism(imp.mechanism_id, library),
        "role": imp.role,
        "rationale": imp.rationale,
    }


def _off_pool_from_llm(
    analysis: llm.LLMAnalysis, known_assets: set[str], library: MechanismLibrary
) -> list[dict[str, Any]]:
    """Assets outside the pool, kept for display instead of thrown away.

    Includes in-pool slots whose asset_id we do not know: the model was
    told to pick from the list, but a made-up ticker still says which
    asset it had in mind.
    """
    out: list[dict[str, Any]] = []
    for imp in analysis.impacts:
        if imp.asset_id in known_assets:
            continue
        logger.warning("pipeline.unknown_asset_moved_off_pool", asset_id=imp.asset_id)
        out.append({
            "name": imp.asset_id,
            "ticker": imp.asset_id,
            "market": "",
            **_impact_metadata(imp, library),
        })
    for imp in analysis.off_pool:
        out.append({
            "name": imp.name,
            "ticker": imp.ticker,
            "market": imp.market,
            **_impact_metadata(imp, library),
        })
    return out


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


def _build_event_from_llm(
    news: RawNews,
    analysis: llm.LLMAnalysis,
    *,
    library: MechanismLibrary,
    off_pool: list[dict[str, Any]],
) -> Event:
    # Persist the richer LLM reasoning into events.analysis so the frontend
    # can surface it in the collapsible "deep analysis" panel.
    extra: dict = {}
    if analysis.classification is not None:
        cls = analysis.classification
        extra["classification"] = {
            "primary_category": cls.primary_category,
            "shock_nature": list(cls.shock_nature),
        }
    if analysis.premise_check:
        extra["premise_check"] = analysis.premise_check
    mechanisms, chain_prior = _mechanism_summary(analysis.mechanisms, library)
    if mechanisms:
        extra["mechanisms"] = mechanisms
        extra["chain_prior"] = chain_prior
    if analysis.transmission_chain:
        extra["transmission_chain"] = list(analysis.transmission_chain)
    if off_pool:
        extra["off_pool"] = off_pool
    if analysis.rejected:
        extra["rejected"] = [rej.model_dump() for rej in analysis.rejected]

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
        analysis=extra or None,
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
    event: Event,
    analysis: llm.LLMAnalysis,
    known_assets: set[str],
    library: MechanismLibrary,
) -> list[ImpactPrediction]:
    """Scoreable predictions: in-pool assets only.

    Unknown asset_ids are skipped here; `_off_pool_from_llm` keeps them.
    """
    return [
        ImpactPrediction(
            event_id=event.id,
            asset_id=imp.asset_id,
            **_impact_metadata(imp, library),
        )
        for imp in analysis.impacts
        if imp.asset_id in known_assets
    ]


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
        "analysis": event.analysis,
        "occurred_at": event.occurred_at.isoformat(),
        "predictions": [
            {
                "asset_id": p.asset_id,
                "direction": p.direction,
                "magnitude": p.magnitude,
                "confidence": p.confidence,
                "rationale": p.rationale,
                "timeframe_min": p.timeframe_min,
                "crowding": p.crowding,
                "mechanism_id": p.mechanism_id,
                "role": p.role,
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
    library: MechanismLibrary | None = None,
) -> UUID | None:
    """Classify one news item end-to-end. Returns event.id or None if skipped.

    An LLM event is kept even when every affected asset is outside the
    pool: it then has no scoreable predictions, only `analysis.off_pool`.
    """
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
        if not analysis.is_market_relevant or not (analysis.impacts or analysis.off_pool):
            logger.info("pipeline.skipped_irrelevant", news_id=news.id)
            return None

        known = await _known_asset_ids(session)
        library = library if library is not None else default_library()
        off_pool = _off_pool_from_llm(analysis, known, library)
        event = _build_event_from_llm(news, analysis, library=library, off_pool=off_pool)
        predictions = _predictions_from_llm(event, analysis, known, library)
        logger.info(
            "pipeline.llm_classified",
            news_id=news.id,
            impacts=len(predictions),
            off_pool=len(off_pool),
            severity=event.severity,
        )

    session.add(event)
    await session.flush()  # populate event.id before building predictions' FK
    for p in predictions:
        p.event_id = event.id
    session.add_all(predictions)
    await session.flush()

    await r.publish(r.CHANNEL_EVENTS_NEW, _serialize_for_pubsub(event, predictions))
    return event.id
