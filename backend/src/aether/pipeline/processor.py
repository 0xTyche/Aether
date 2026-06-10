"""Scheduled job that pulls fresh raw_news and runs them through the pipeline.

Design:
  - One tick processes at most BATCH_SIZE recently-fetched, never-classified
    news items in the order they were stored.
  - Per-item dedup via Redis SET `processed:news:{id}` (TTL long enough to
    survive a restart). DB is the long-term truth — if the Redis key is
    missing but events.raw_news_id already contains this id, we still skip.
  - Items are processed sequentially (not in parallel) so the LLM rate
    limit applies cleanly and one stuck LLM call cannot wedge others.
"""

import structlog
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from aether.models.assets import Asset
from aether.models.events import Event
from aether.models.news import RawNews
from aether.models.regions import EconomicRegion
from aether.pipeline import impact
from aether.rules.loader import RuleStore, load_rules
from aether.pipeline import llm
from aether.storage import db as db_module
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)


BATCH_SIZE = 25
DEDUP_TTL_SECONDS = 30 * 24 * 3600  # 30 days

_rule_store: RuleStore | None = None
_system_prompt: str | None = None


def _dedup_key(news_id: int) -> str:
    return f"processed:news:{news_id}"


async def _is_already_processed(news_id: int) -> bool:
    client = r.get_redis()
    return bool(await client.exists(_dedup_key(news_id)))


async def _mark_processed(news_id: int) -> None:
    client = r.get_redis()
    await client.set(_dedup_key(news_id), "1", ex=DEDUP_TTL_SECONDS)


async def _ensure_loaded() -> tuple[RuleStore, str]:
    """Load rules + build the static system prompt once per process."""
    global _rule_store, _system_prompt
    if _rule_store is not None and _system_prompt is not None:
        return _rule_store, _system_prompt
    _rule_store = load_rules()
    async with db_module.session_scope() as session:
        asset_ids = (await session.scalars(select(Asset.id))).all()
        region_ids = (await session.scalars(select(EconomicRegion.id))).all()
    _system_prompt = llm.build_system_prompt(asset_ids, region_ids)
    logger.info("pipeline.loaded",
                rules=len(_rule_store), assets=len(asset_ids), regions=len(region_ids))
    return _rule_store, _system_prompt


def reset_cache_for_tests() -> None:
    """Discard the cached rule store / system prompt — test isolation only."""
    global _rule_store, _system_prompt
    _rule_store = None
    _system_prompt = None


async def _fetch_unprocessed_ids(limit: int) -> list[int]:
    """Newest-first raw_news ids that have no existing Event row yet."""
    async with db_module.session_scope() as session:
        sub = select(Event.raw_news_id).where(Event.raw_news_id.is_not(None))
        rows = await session.scalars(
            select(RawNews.id)
            .where(RawNews.id.notin_(sub))
            .order_by(desc(RawNews.id))
            .limit(limit)
        )
    return list(rows.all())


async def _process_one(news_id: int, rules, system_prompt: str) -> str:
    """Returns one of: 'events', 'skip', 'dup', 'error'."""
    if await _is_already_processed(news_id):
        return "dup"
    try:
        async with db_module.session_scope() as session:
            news = await session.get(RawNews, news_id)
            if news is None:
                return "skip"
            event_id = await impact.analyze_raw_news(
                news, session, rules=rules, system_prompt=system_prompt,
            )
        await _mark_processed(news_id)
        return "events" if event_id else "skip"
    except IntegrityError as exc:
        logger.warning("pipeline.integrity_error", news_id=news_id, error=str(exc))
        await _mark_processed(news_id)
        return "error"
    except Exception as exc:
        logger.exception("pipeline.unexpected_error", news_id=news_id, error=str(exc))
        return "error"


async def tick() -> dict[str, int]:
    """One processing pass; returns counts by outcome."""
    rules, system_prompt = await _ensure_loaded()
    ids = await _fetch_unprocessed_ids(BATCH_SIZE)
    counts = {"events": 0, "skip": 0, "dup": 0, "error": 0}
    for news_id in ids:
        outcome = await _process_one(news_id, rules.rules, system_prompt)
        counts[outcome] += 1
    if any(counts.values()):
        logger.info("pipeline.tick", counts=counts)
    return counts
