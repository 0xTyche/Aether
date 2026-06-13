"""REST endpoints for the frontend dashboard."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from aether.api.schemas import (
    AccuracyBucketDTO,
    AccuracyStatsDTO,
    AssetDTO,
    EventDTO,
    ImpactPredictionDTO,
    PriceDTO,
    RegionDTO,
)
from aether.models.assets import Asset
from aether.models.events import Event, ImpactOutcome, ImpactPrediction
from aether.models.prices import Price
from aether.models.regions import CountryEconomicMembership, EconomicRegion
from aether.storage import db as db_module


router = APIRouter(prefix="/api", tags=["api"])


# ---------- assets ------------------------------------------------------

@router.get("/assets", response_model=list[AssetDTO])
async def list_assets() -> list[AssetDTO]:
    async with db_module.session_scope() as session:
        rows = (await session.scalars(select(Asset).order_by(Asset.id))).all()
    return [AssetDTO.model_validate(r) for r in rows]


# ---------- regions -----------------------------------------------------

@router.get("/regions", response_model=list[RegionDTO])
async def list_regions() -> list[RegionDTO]:
    async with db_module.session_scope() as session:
        regions = (await session.scalars(
            select(EconomicRegion).order_by(EconomicRegion.id)
        )).all()
        memberships = (await session.scalars(
            select(CountryEconomicMembership)
        )).all()

    by_region: dict[str, list[str]] = {}
    for m in memberships:
        by_region.setdefault(m.region_id, []).append(m.country_iso)
    for v in by_region.values():
        v.sort()

    out: list[RegionDTO] = []
    for r in regions:
        out.append(RegionDTO(
            id=r.id,
            label_zh=r.label_zh,
            label_en=r.label_en,
            region_type=r.region_type,
            central_bank=r.central_bank,
            members=by_region.get(r.id, []),
        ))
    return out


# ---------- events ------------------------------------------------------

def _to_event_dto(event: Event) -> EventDTO:
    """Explicit construction so we don't trigger Pydantic's from_attributes
    lazy-load of the predictions relationship after the session closes."""
    return EventDTO(
        id=event.id,
        classifier=event.classifier,
        rule_id=event.rule_id,
        severity=event.severity,
        origin_country=event.origin_country,
        origin_lat=event.origin_lat,
        origin_lng=event.origin_lng,
        affected_regions=event.affected_regions,
        title=event.title,
        explanation=event.explanation,
        analysis=event.analysis,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
        predictions=[
            ImpactPredictionDTO.model_validate(p, from_attributes=True)
            for p in event.predictions
        ],
    )


@router.get("/events", response_model=list[EventDTO])
async def list_events(
    limit: int = Query(50, ge=1, le=500),
    since: datetime | None = Query(None, description="ISO timestamp; events occurred at or after"),
) -> list[EventDTO]:
    async with db_module.session_scope() as session:
        stmt = (
            select(Event)
            .options(selectinload(Event.predictions))
            .order_by(desc(Event.occurred_at))
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(Event.occurred_at >= since)
        events = (await session.scalars(stmt)).all()
        return [_to_event_dto(e) for e in events]


@router.get("/events/{event_id}", response_model=EventDTO)
async def get_event(event_id: str) -> EventDTO:
    async with db_module.session_scope() as session:
        stmt = (
            select(Event)
            .options(selectinload(Event.predictions))
            .where(Event.id == event_id)
        )
        event = (await session.scalars(stmt)).one_or_none()
        if event is None:
            raise HTTPException(status_code=404, detail="event not found")
        return _to_event_dto(event)


# ---------- prices ------------------------------------------------------

@router.get("/prices/latest", response_model=list[PriceDTO])
async def latest_prices() -> list[PriceDTO]:
    """Latest price per asset, computed with DISTINCT ON (asset_id)."""
    from sqlalchemy import text

    async with db_module.session_scope() as session:
        rows = await session.execute(text(
            """
            SELECT DISTINCT ON (asset_id) asset_id, price, ts, source
            FROM prices
            ORDER BY asset_id, ts DESC
            """
        ))
        result = rows.all()
    return [
        PriceDTO(asset_id=r.asset_id, price=r.price, ts=r.ts, source=r.source)
        for r in result
    ]


# ---------- stats -------------------------------------------------------

def _bucket(key: str, rows: list[tuple]) -> AccuracyBucketDTO:
    """Aggregate a list of (accuracy, count) tuples into one bucket DTO."""
    counts = {a: c for a, c in rows}
    hits = counts.get("hit", 0)
    misses = counts.get("miss", 0)
    partials = counts.get("partial", 0)
    no_data = counts.get(None, 0)
    scored = hits + misses + partials
    total = scored + no_data
    return AccuracyBucketDTO(
        key=key,
        total=total,
        scored=scored,
        hits=hits,
        misses=misses,
        partials=partials,
        hit_rate=(hits / scored) if scored > 0 else None,
    )


@router.get("/stats/accuracy", response_model=AccuracyStatsDTO)
async def accuracy_stats() -> AccuracyStatsDTO:
    """Aggregate ImpactOutcome rows by classifier, severity, and rule_id."""
    from sqlalchemy import text

    async with db_module.session_scope() as session:
        overall = (await session.execute(text(
            "SELECT accuracy, COUNT(*) "
            "FROM impact_outcomes "
            "GROUP BY accuracy"
        ))).all()
        by_classifier = (await session.execute(text(
            "SELECT e.classifier, o.accuracy, COUNT(*) "
            "FROM impact_outcomes o "
            "JOIN impact_predictions p ON p.id = o.prediction_id "
            "JOIN events e ON e.id = p.event_id "
            "GROUP BY e.classifier, o.accuracy"
        ))).all()
        by_severity = (await session.execute(text(
            "SELECT e.severity, o.accuracy, COUNT(*) "
            "FROM impact_outcomes o "
            "JOIN impact_predictions p ON p.id = o.prediction_id "
            "JOIN events e ON e.id = p.event_id "
            "GROUP BY e.severity, o.accuracy"
        ))).all()
        by_rule = (await session.execute(text(
            "SELECT e.rule_id, o.accuracy, COUNT(*) "
            "FROM impact_outcomes o "
            "JOIN impact_predictions p ON p.id = o.prediction_id "
            "JOIN events e ON e.id = p.event_id "
            "WHERE e.rule_id IS NOT NULL "
            "GROUP BY e.rule_id, o.accuracy"
        ))).all()

    def grouped(rows: list[tuple]) -> dict[str, list[tuple]]:
        out: dict[str, list[tuple]] = {}
        for key, accuracy, count in rows:
            out.setdefault(str(key), []).append((accuracy, count))
        return out

    overall_bucket = _bucket("overall", [(a, c) for a, c in overall])

    classifier_groups = grouped(by_classifier)
    classifier_buckets = [
        _bucket(k, v) for k, v in sorted(classifier_groups.items())
    ]
    severity_groups = grouped(by_severity)
    severity_buckets = [
        _bucket(k, v) for k, v in sorted(severity_groups.items())
    ]
    rule_groups = grouped(by_rule)
    rule_buckets = sorted(
        (_bucket(k, v) for k, v in rule_groups.items()),
        key=lambda b: -b.scored,
    )

    return AccuracyStatsDTO(
        overall=overall_bucket,
        by_classifier=classifier_buckets,
        by_severity=severity_buckets,
        by_rule=rule_buckets,
    )
