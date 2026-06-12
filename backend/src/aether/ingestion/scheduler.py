"""Periodic-task orchestration via APScheduler's AsyncIOScheduler.

A single scheduler instance is created by FastAPI on app startup and
shut down on app shutdown. Jobs registered here are the only things
that ever auto-fire inside the backend process.

Long-running stream consumers (Binance WS, Alpaca WS) are NOT scheduled;
they are spawned as bare asyncio tasks from the FastAPI lifespan.
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from aether.ingestion import akshare_, akshare_news, rss
from aether.pipeline import processor as pipeline_processor
from aether.pipeline import watcher as pipeline_watcher


logger = structlog.get_logger(__name__)


# Default cadences chosen to be polite to upstream while staying responsive.
RSS_INTERVAL_MIN = 5
AKSHARE_INTERVAL_S = 60
AKSHARE_NEWS_INTERVAL_S = 60
PIPELINE_INTERVAL_S = 60
WATCHER_INTERVAL_S = 60


def _register_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        rss.ingest_all_feeds,
        trigger=IntervalTrigger(minutes=RSS_INTERVAL_MIN),
        id="rss.central_banks",
        name="Central bank RSS pull",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        akshare_.tick,
        trigger=IntervalTrigger(seconds=AKSHARE_INTERVAL_S),
        id="akshare.tick",
        name="AKShare polling (SHCOMP / HSI / FX)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        akshare_news.tick,
        trigger=IntervalTrigger(seconds=AKSHARE_NEWS_INTERVAL_S),
        id="akshare.news.tick",
        name="AKShare news pull (5 Chinese sources)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        pipeline_processor.tick,
        trigger=IntervalTrigger(seconds=PIPELINE_INTERVAL_S),
        id="pipeline.process",
        name="Classify new raw_news (rules → LLM)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        pipeline_watcher.tick,
        trigger=IntervalTrigger(seconds=WATCHER_INTERVAL_S),
        id="pipeline.watcher",
        name="Score predictions whose window has elapsed",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def build_scheduler() -> AsyncIOScheduler:
    """Construct a scheduler with all jobs registered, but not yet started."""
    scheduler = AsyncIOScheduler()
    _register_jobs(scheduler)
    logger.info("scheduler.built", job_count=len(scheduler.get_jobs()))
    return scheduler


async def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    scheduler.start()
    # Kick the read-only ingesters once on boot — fire and forget so a slow
    # upstream cannot block FastAPI startup. The pipeline tick is left to the
    # scheduler's first run (60s after boot) so it doesn't race with itself
    # while a long LLM backlog is being chewed through.
    import asyncio

    async def _safe(name: str, fn) -> None:
        try:
            await fn()
        except Exception as exc:
            logger.warning("scheduler.initial_run_failed", job=name, error=str(exc))

    asyncio.create_task(_safe("rss", rss.ingest_all_feeds))
    asyncio.create_task(_safe("akshare", akshare_.tick))


async def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    scheduler.shutdown(wait=False)
