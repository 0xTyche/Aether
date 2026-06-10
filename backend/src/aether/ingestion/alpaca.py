"""US-stocks trade ingestion from Alpaca's IEX feed.

WS protocol reference: https://docs.alpaca.markets/docs/streaming-market-data

Handshake on `wss://stream.data.alpaca.markets/v2/iex`:
  1. Server sends {"T":"success","msg":"connected"}
  2. Client sends {"action":"auth","key":...,"secret":...}
  3. Server sends {"T":"success","msg":"authenticated"}
  4. Client sends {"action":"subscribe","trades":["AAPL","MSFT",...]}
  5. Server streams {"T":"t","S":"AAPL","p":...,"t":"2026-...",...}

We treat US-listed equities (asset_class IN ('equity') AND country_iso='US')
as Alpaca-driven and use the asset id as the ticker.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
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

FLUSH_INTERVAL_MS = 500
BACKOFF_INITIAL_S = 1.0
BACKOFF_MAX_S = 60.0
PING_INTERVAL_S = 20
PING_TIMEOUT_S = 20

SOURCE = "alpaca"


@dataclass(slots=True)
class TradeTick:
    asset_id: str
    ts: datetime
    price: Decimal


async def _load_symbols() -> list[str]:
    """Tickers for every US-listed equity. The asset id IS the ticker."""
    async with db_module.session_scope() as session:
        rows = await session.scalars(
            select(Asset.id).where(
                Asset.asset_class == "equity", Asset.country_iso == "US"
            )
        )
    return list(rows.all())


def _parse_trade(msg: dict, symbol_set: set[str]) -> TradeTick | None:
    if msg.get("T") != "t":  # not a trade message
        return None
    sym = msg.get("S")
    price = msg.get("p")
    ts_str = msg.get("t")
    if not sym or price is None or not ts_str or sym not in symbol_set:
        return None
    return TradeTick(
        asset_id=sym,
        ts=datetime.fromisoformat(ts_str.replace("Z", "+00:00")),
        price=Decimal(str(price)),
    )


async def _flush(buffer: list[TradeTick]) -> int:
    if not buffer:
        return 0
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
        logger.warning("alpaca.publish_failed", error=str(exc))

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
                logger.debug("alpaca.flushed", n=len(drained), written=written)
            except Exception as exc:
                logger.exception("alpaca.flush_failed", error=str(exc))


async def _authenticate(ws, key: str, secret: str) -> None:
    """Send auth and wait for the "authenticated" ack. Raises on failure."""
    await ws.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        msgs = json.loads(raw)
        if not isinstance(msgs, list):
            msgs = [msgs]
        for m in msgs:
            t = m.get("T")
            if t == "success" and m.get("msg") == "authenticated":
                return
            if t == "error":
                raise RuntimeError(f"alpaca auth error: {m}")


async def _subscribe(ws, symbols: list[str]) -> None:
    await ws.send(json.dumps({"action": "subscribe", "trades": symbols}))


async def _consume_one_session(
    url: str,
    key: str,
    secret: str,
    symbols: list[str],
    queue: asyncio.Queue[TradeTick],
    *,
    connect_fn: Callable[..., Awaitable] | None = None,
) -> None:
    connector = connect_fn or websockets.connect
    symbol_set = set(symbols)
    async with connector(
        url, ping_interval=PING_INTERVAL_S, ping_timeout=PING_TIMEOUT_S
    ) as ws:
        # Drain the initial "connected" greeting.
        _greet = await asyncio.wait_for(ws.recv(), timeout=10)
        await _authenticate(ws, key, secret)
        await _subscribe(ws, symbols)
        logger.info("alpaca.connected", subscriptions=len(symbols))

        async for raw in ws:
            try:
                msgs = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msgs, list):
                msgs = [msgs]
            for m in msgs:
                tick = _parse_trade(m, symbol_set)
                if tick is not None:
                    await queue.put(tick)


async def run_forever(stop: asyncio.Event | None = None) -> None:
    stop = stop or asyncio.Event()
    settings = get_settings()

    if not settings.alpaca_api_key or not settings.alpaca_api_secret:
        logger.warning("alpaca.no_credentials; skipping")
        await stop.wait()
        return

    symbols = await _load_symbols()
    if not symbols:
        logger.warning("alpaca.no_symbols; sleeping")
        await stop.wait()
        return

    url = settings.alpaca_stream_url
    queue: asyncio.Queue[TradeTick] = asyncio.Queue(maxsize=10_000)
    flusher = asyncio.create_task(_flusher_loop(queue, stop))

    backoff = BACKOFF_INITIAL_S
    try:
        while not stop.is_set():
            try:
                await _consume_one_session(
                    url, settings.alpaca_api_key, settings.alpaca_api_secret,
                    symbols, queue,
                )
                backoff = BACKOFF_INITIAL_S
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "alpaca.session_failed", error=str(exc), backoff_s=backoff
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
