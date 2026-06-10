"""Binance Vision WS: parsing, flushing, reconnect backoff."""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from aether.ingestion import binance
from aether.models.prices import Price
from aether.storage import db as db_module
from scripts.seed_assets import seed_assets


@pytest_asyncio.fixture
async def assets_and_prices_clean() -> None:
    async with db_module.session_scope() as session:
        await session.execute(text("TRUNCATE TABLE prices, assets RESTART IDENTITY CASCADE"))
        await session.commit()
        await seed_assets(session)


# ---------- parsing -------------------------------------------------------

def test_parse_combined_trade_payload():
    symbol_map = {"btcusdt": "BTC"}
    payload = {
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade", "s": "BTCUSDT",
            "p": "61234.50000000", "T": 1781000000000,
        },
    }
    tick = binance._parse_trade(payload, symbol_map)
    assert tick is not None
    assert tick.asset_id == "BTC"
    assert tick.price == Decimal("61234.50000000")
    assert tick.ts == datetime.fromtimestamp(1781000000000 / 1000, tz=UTC)


def test_parse_raw_single_stream_payload():
    """Some Binance endpoints emit the data directly without the `stream` wrap."""
    symbol_map = {"ethusdt": "ETH"}
    tick = binance._parse_trade(
        {"s": "ETHUSDT", "p": "3000.00", "T": 1781000000000}, symbol_map
    )
    assert tick is not None and tick.asset_id == "ETH"


def test_parse_skips_unknown_symbol():
    symbol_map = {"btcusdt": "BTC"}
    assert binance._parse_trade({"s": "DOGEUSDT", "p": "0.1", "T": 1}, symbol_map) is None


def test_parse_skips_missing_fields():
    symbol_map = {"btcusdt": "BTC"}
    assert binance._parse_trade({"s": "BTCUSDT", "p": "1"}, symbol_map) is None  # no T
    assert binance._parse_trade({"p": "1", "T": 1}, symbol_map) is None  # no S


# ---------- flush -------------------------------------------------------

@pytest.mark.usefixtures("assets_and_prices_clean")
async def test_flush_writes_rows_and_dedups_by_pk():
    ts = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
    buf = [
        binance.TradeTick("BTC", ts, Decimal("60000")),
        binance.TradeTick("BTC", ts, Decimal("60100")),  # same (asset, ts) — coalesces
        binance.TradeTick("ETH", ts, Decimal("3000")),
    ]
    written = await binance._flush(buf)
    assert written == 2  # BTC coalesced + ETH

    async with db_module.session_scope() as session:
        rows = (await session.scalars(select(Price).order_by(Price.asset_id))).all()
    assert {r.asset_id for r in rows} == {"BTC", "ETH"}


@pytest.mark.usefixtures("assets_and_prices_clean")
async def test_flush_empty_returns_zero():
    assert await binance._flush([]) == 0


# ---------- url builder -------------------------------------------------

def test_build_stream_url_appends_streams():
    url = binance._build_stream_url(
        "wss://data-stream.binance.vision/stream",
        {"btcusdt": "BTC", "ethusdt": "ETH"},
    )
    assert url.endswith("streams=btcusdt@trade/ethusdt@trade") or \
           url.endswith("streams=ethusdt@trade/btcusdt@trade")


# ---------- session consumption ------------------------------------------

class _FakeWS:
    def __init__(self, messages):
        self._messages = list(messages)
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return None
    def __aiter__(self):
        return self
    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


@pytest.mark.usefixtures("assets_and_prices_clean")
async def test_consume_one_session_pumps_ticks_into_queue():
    symbol_map = {"btcusdt": "BTC"}
    msgs = [
        json.dumps({"s": "BTCUSDT", "p": "61000", "T": 1781000000000}),
        json.dumps({"s": "BTCUSDT", "p": "61050", "T": 1781000001000}),
    ]
    queue: asyncio.Queue[binance.TradeTick] = asyncio.Queue()

    def fake_connect(*_args, **_kwargs):
        return _FakeWS(msgs)

    await binance._consume_one_session(
        "wss://test", symbol_map, queue, connect_fn=fake_connect
    )
    assert queue.qsize() == 2
    t1 = await queue.get()
    assert t1.asset_id == "BTC"
    assert t1.price == Decimal("61000")


# ---------- symbol map loader -------------------------------------------

@pytest.mark.usefixtures("assets_and_prices_clean")
async def test_load_symbol_map_returns_crypto_assets():
    m = await binance._load_symbol_map()
    # Every binance_symbol from seed_assets should appear (lowercased).
    assert "btcusdt" in m and m["btcusdt"] == "BTC"
    assert "ethusdt" in m and m["ethusdt"] == "ETH"
