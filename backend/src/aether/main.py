"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from aether import __version__
from aether.api import router as api_router
from aether.ingestion import alpaca as alpaca_stream
from aether.ingestion import binance as binance_stream
from aether.ingestion.scheduler import build_scheduler, start_scheduler, stop_scheduler
from aether.storage import db, redis_
from aether.ws.hub import get_hub


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
    """Start scheduler + long-running streams + WS hub on boot."""
    hub = get_hub()
    await hub.start()

    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    await start_scheduler(scheduler)

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
        await hub.stop()
        await db.dispose_engine()
        await redis_.close_redis()


app = FastAPI(
    title="Aether API",
    description="Macro events propagating through the global financial aether.",
    version=__version__,
    lifespan=lifespan,
)

# Vite dev server runs on :5173 and proxies /api/* to backend, but allow direct
# cross-origin for the rare cases (e.g. opening the built dist via file:// or a
# non-localhost host).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "project": "aether", "version": __version__}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """Bidirectional channel for subscribe / unsubscribe / ping plus
    server-pushed event/price/impact messages."""
    hub = get_hub()
    await hub.register(ws)
    logger.info("ws.client_connected", total=hub.client_count())
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                break
            except Exception as exc:
                await ws.send_json({"type": "error", "message": f"invalid message: {exc}"})
                continue

            t = msg.get("type") if isinstance(msg, dict) else None
            if t == "subscribe":
                channels = msg.get("channels", []) or []
                subs = hub.subscribe(ws, channels)
                await ws.send_json({"type": "subscribed", "channels": sorted(subs)})
            elif t == "unsubscribe":
                channels = msg.get("channels", []) or []
                subs = hub.unsubscribe(ws, channels)
                await ws.send_json({"type": "subscribed", "channels": sorted(subs)})
            elif t == "ping":
                await ws.send_json({"type": "pong", "ts": msg.get("ts")})
            else:
                await ws.send_json(
                    {"type": "error", "message": f"unknown message type: {t}"}
                )
    finally:
        hub.unregister(ws)
        logger.info("ws.client_disconnected", total=hub.client_count())
