"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aether import __version__
from aether.ingestion.scheduler import build_scheduler, start_scheduler, stop_scheduler
from aether.storage import db, redis_


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the ingestion scheduler on boot, shut it down on exit."""
    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    await start_scheduler(scheduler)
    try:
        yield
    finally:
        await stop_scheduler(scheduler)
        await db.dispose_engine()
        await redis_.close_redis()


app = FastAPI(
    title="Aether API",
    description="Macro events propagating through the global financial aether.",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "project": "aether", "version": __version__}
