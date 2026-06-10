"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from aether import __version__
from aether.ingestion import alpaca as alpaca_stream
from aether.ingestion import binance as binance_stream
from aether.ingestion.scheduler import build_scheduler, start_scheduler, stop_scheduler
from aether.storage import db, redis_


logger = structlog.get_logger(__name__)


async def _spawn_stream(name: str, runner, stop: asyncio.Event) -> asyncio.Task:
    """Wrap a stream runner in a task and log unexpected exits."""
    async def runner_with_log() -> None:
        try:
            await runner(stop)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("stream.crashed", stream=name, error=str(exc))
    return asyncio.create_task(runner_with_log(), name=f"stream.{name}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start scheduler + long-running streams on boot; tear down on exit."""
    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    await start_scheduler(scheduler)

    # Long-running WS consumers run as bare asyncio tasks (not jobs).
    stop_event = asyncio.Event()
    app.state.stream_stop = stop_event
    app.state.stream_tasks = [
        await _spawn_stream("binance", binance_stream.run_forever, stop_event),
        await _spawn_stream("alpaca", alpaca_stream.run_forever, stop_event),
    ]

    try:
        yield
    finally:
        stop_event.set()
        for t in app.state.stream_tasks:
            t.cancel()
        await asyncio.gather(*app.state.stream_tasks, return_exceptions=True)
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
