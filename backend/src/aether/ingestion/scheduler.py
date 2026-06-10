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

from aether.ingestion import akshare_, rss
from aether.pipeline import processor as pipeline_processor


logger = structlog.get_logger(__name__)


# Default cadences chosen to be polite to upstream while staying responsive.
RSS_INTERVAL_MIN = 5
AKSHARE_INTERVAL_S = 60
PIPELINE_INTERVAL_S = 60


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
        pipeline_processor.tick,
        trigger=IntervalTrigger(seconds=PIPELINE_INTERVAL_S),
        id="pipeline.process",
        name="Classify new raw_news (rules → LLM)",
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
    # Run pull-style ingesters once at boot so users don't wait an interval.
    try:
        await rss.ingest_all_feeds()
    except Exception as exc:
        logger.warning("scheduler.initial_rss_failed", error=str(exc))
    try:
        await akshare_.tick()
    except Exception as exc:
        logger.warning("scheduler.initial_akshare_failed", error=str(exc))
    try:
        await pipeline_processor.tick()
    except Exception as exc:
        logger.warning("scheduler.initial_pipeline_failed", error=str(exc))


async def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    scheduler.shutdown(wait=False)
