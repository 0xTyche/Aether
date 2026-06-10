"""Crypto trade ingestion from Binance's public data CDN.

We connect to `wss://data-stream.binance.vision/stream` (the public, geo-
unrestricted data feed) and subscribe to one `<symbol>@trade` channel per
asset whose `binance_symbol` is set. Each tick is written into `prices`.

Design notes:
  - One persistent connection; subscriptions are bundled via the
    /stream?streams=... multiplex endpoint so we don't burn one socket
    per symbol.
  - Automatic reconnect with exponential backoff (cap 30s) — Binance
    occasionally closes idle sockets and routine maintenance windows
    drop connections cleanly.
  - Writes are batched: each tick goes into an in-memory queue; a
    flusher coroutine drains the queue every `FLUSH_INTERVAL_MS` and
    inserts in one round-trip. Keeps DB I/O light even under bursts.
  - `run_forever()` is the public entry point; cancel it (asyncio.Task
    .cancel) to shut down cleanly.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import structlog
import websockets
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from aether.config import get_settings
from aether.models.assets import Asset
from aether.models.prices import Price
from aether.storage import db as db_module
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)

FLUSH_INTERVAL_MS = 500   # batch DB writes every 0.5s
BACKOFF_INITIAL_S = 1.0
BACKOFF_MAX_S = 30.0
PING_INTERVAL_S = 20
PING_TIMEOUT_S = 20

SOURCE = "binance"


@dataclass(slots=True)
class TradeTick:
    asset_id: str
    ts: datetime
    price: Decimal


async def _load_symbol_map() -> dict[str, str]:
    """Map binance_symbol (lower-case) → asset_id, for assets we're subscribing to."""
    async with db_module.session_scope() as session:
        rows = await session.scalars(
            select(Asset).where(Asset.binance_symbol.is_not(None))
        )
        assets = rows.all()
    return {a.binance_symbol.lower(): a.id for a in assets if a.binance_symbol}


def _build_stream_url(base_url: str, symbol_map: dict[str, str]) -> str:
    streams = "/".join(f"{sym}@trade" for sym in symbol_map.keys())
    sep = "?streams=" if "?" not in base_url else "&streams="
    return f"{base_url}{sep}{streams}"


def _parse_trade(payload: dict, symbol_map: dict[str, str]) -> TradeTick | None:
    """Parse one combined-stream payload into a TradeTick, or None to skip."""
    data = payload.get("data") if "data" in payload else payload
    sym = data.get("s")
    price_str = data.get("p")
    ts_ms = data.get("T")
    if not sym or not price_str or not ts_ms:
        return None
    asset_id = symbol_map.get(sym.lower())
    if not asset_id:
        return None
    return TradeTick(
        asset_id=asset_id,
        ts=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
        price=Decimal(price_str),
    )


async def _flush(buffer: list[TradeTick]) -> int:
    if not buffer:
        return 0
    # Coalesce by (asset_id, ts) keeping the last value seen. Binance can
    # publish the same trade ms more than once during reconnect overlap.
    coalesced: dict[tuple[str, datetime], TradeTick] = {}
    for t in buffer:
        coalesced[(t.asset_id, t.ts)] = t
    rows = [
        {"asset_id": t.asset_id, "ts": t.ts, "price": t.price, "source": SOURCE}
        for t in coalesced.values()
    ]
    stmt = pg_insert(Price).values(rows).on_conflict_do_nothing(
        index_elements=["asset_id", "ts"]
    )
    async with db_module.session_scope() as session:
        result = await session.execute(stmt)

    # Forward to the WS hub via Redis Pub/Sub (best-effort; do not raise).
    try:
        await r.publish(r.CHANNEL_PRICES_UPDATE, {
            "updates": [
                {
                    "asset_id": t.asset_id,
                    "price": str(t.price),
                    "ts": t.ts.isoformat(),
                    "source": SOURCE,
                }
                for t in coalesced.values()
            ],
        })
    except Exception as exc:
        logger.warning("binance.publish_failed", error=str(exc))

    return result.rowcount or 0


async def _flusher_loop(queue: asyncio.Queue[TradeTick], stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.sleep(FLUSH_INTERVAL_MS / 1000)
        drained: list[TradeTick] = []
        while True:
            try:
                drained.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if drained:
            try:
                written = await _flush(drained)
                logger.debug("binance.flushed", n=len(drained), written=written)
            except Exception as exc:
                logger.exception("binance.flush_failed", error=str(exc))


async def _consume_one_session(
    url: str,
    symbol_map: dict[str, str],
    queue: asyncio.Queue[TradeTick],
    *,
    connect_fn: Callable[..., Awaitable] | None = None,
) -> None:
    """Open one WS connection and pump ticks into the queue until it closes."""
    connector = connect_fn or websockets.connect
    async with connector(
        url, ping_interval=PING_INTERVAL_S, ping_timeout=PING_TIMEOUT_S
    ) as ws:
        logger.info("binance.connected", subscriptions=len(symbol_map))
        async for raw in ws:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            tick = _parse_trade(payload, symbol_map)
            if tick is not None:
                await queue.put(tick)


async def run_forever(stop: asyncio.Event | None = None) -> None:
    """Main entry point — call as `asyncio.create_task(run_forever())`."""
    stop = stop or asyncio.Event()
    settings = get_settings()

    symbol_map = await _load_symbol_map()
    if not symbol_map:
        logger.warning("binance.no_subscriptions; sleeping")
        await stop.wait()
        return

    url = _build_stream_url(settings.binance_ws_url, symbol_map)
    queue: asyncio.Queue[TradeTick] = asyncio.Queue(maxsize=10_000)
    flusher = asyncio.create_task(_flusher_loop(queue, stop))

    backoff = BACKOFF_INITIAL_S
    try:
        while not stop.is_set():
            try:
                await _consume_one_session(url, symbol_map, queue)
                backoff = BACKOFF_INITIAL_S  # clean close — reset
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "binance.session_failed", error=str(exc), backoff_s=backoff
                )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=backoff)
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, BACKOFF_MAX_S)
    finally:
        stop.set()
        flusher.cancel()
        try:
            await flusher
        except (asyncio.CancelledError, Exception):
            pass
