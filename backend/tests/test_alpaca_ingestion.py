"""Alpaca WS: parsing, auth handshake, flush."""

import asyncio
import json
from collections import deque
from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from aether.ingestion import alpaca
from aether.models.prices import Price
from aether.storage import db as db_module
from scripts.seed_assets import seed_assets


@pytest_asyncio.fixture
async def assets_clean() -> None:
    async with db_module.session_scope() as session:
        await session.execute(text("TRUNCATE TABLE prices, assets RESTART IDENTITY CASCADE"))
        await session.commit()
        await seed_assets(session)


# ---------- parsing -----------------------------------------------------

def test_parse_trade_message():
    msg = {
        "T": "t", "S": "AAPL",
        "p": 290.73, "t": "2026-06-10T13:30:00.123456789Z",
        "s": 100, "x": "V",
    }
    tick = alpaca._parse_trade(msg, {"AAPL", "MSFT"})
    assert tick is not None
    assert tick.asset_id == "AAPL"
    assert tick.price == Decimal("290.73")


def test_parse_skips_non_trade_messages():
    assert alpaca._parse_trade({"T": "success", "msg": "ok"}, {"AAPL"}) is None
    assert alpaca._parse_trade({"T": "q", "S": "AAPL"}, {"AAPL"}) is None  # quote


def test_parse_skips_unknown_symbol():
    msg = {"T": "t", "S": "DOGE", "p": 0.1, "t": "2026-06-10T00:00:00Z"}
    assert alpaca._parse_trade(msg, {"AAPL"}) is None


# ---------- handshake ----------------------------------------------------

class _FakeWS:
    def __init__(self, incoming):
        self._incoming = deque(incoming)
        self.sent: list[str] = []

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def send(self, data): self.sent.append(data)
    async def recv(self):
        if not self._incoming:
            await asyncio.sleep(60)  # hang
        return self._incoming.popleft()
    def __aiter__(self): return self
    async def __anext__(self):
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.popleft()


async def test_authenticate_succeeds_on_ack():
    ws = _FakeWS([json.dumps([{"T": "success", "msg": "authenticated"}])])
    await alpaca._authenticate(ws, "K", "S")
    sent = json.loads(ws.sent[0])
    assert sent == {"action": "auth", "key": "K", "secret": "S"}


async def test_authenticate_raises_on_error():
    ws = _FakeWS([json.dumps([{"T": "error", "code": 402, "msg": "auth failed"}])])
    with pytest.raises(RuntimeError, match="auth"):
        await alpaca._authenticate(ws, "K", "S")


async def test_authenticate_skips_non_auth_messages_then_acks():
    """The protocol may interleave a 'connected' greeting before the ack."""
    ws = _FakeWS([
        json.dumps([{"T": "subscription", "trades": []}]),
        json.dumps([{"T": "success", "msg": "authenticated"}]),
    ])
    await alpaca._authenticate(ws, "K", "S")


# ---------- end-to-end session ------------------------------------------

@pytest.mark.usefixtures("assets_clean")
async def test_consume_session_runs_auth_subscribe_then_pumps():
    symbols = ["AAPL", "MSFT"]
    incoming = [
        json.dumps([{"T": "success", "msg": "connected"}]),
        json.dumps([{"T": "success", "msg": "authenticated"}]),
        json.dumps([
            {"T": "t", "S": "AAPL", "p": 290.73, "t": "2026-06-10T13:30:00Z"},
            {"T": "t", "S": "MSFT", "p": 403.92, "t": "2026-06-10T13:30:01Z"},
        ]),
    ]
    ws = _FakeWS(incoming)
    def fake_connect(*_args, **_kwargs):
        return ws

    queue: asyncio.Queue[alpaca.TradeTick] = asyncio.Queue()
    await alpaca._consume_one_session(
        "wss://test", "K", "S", symbols, queue, connect_fn=fake_connect
    )

    # auth + subscribe sent
    actions = [json.loads(s)["action"] for s in ws.sent]
    assert "auth" in actions and "subscribe" in actions

    # two ticks pumped
    assert queue.qsize() == 2
    syms = {(await queue.get()).asset_id for _ in range(2)}
    assert syms == {"AAPL", "MSFT"}


# ---------- symbol loader -----------------------------------------------

@pytest.mark.usefixtures("assets_clean")
async def test_load_symbols_returns_only_us_equities():
    symbols = await alpaca._load_symbols()
    # Seed contains 10 US equities — see scripts/seed_assets.py.
    assert len(symbols) == 10
    for must in ("AAPL", "MSFT", "NVDA", "TSLA", "SPY"):
        assert must in symbols


# ---------- flush -------------------------------------------------------

@pytest.mark.usefixtures("assets_clean")
async def test_flush_writes_and_coalesces():
    ts = datetime.fromisoformat("2026-06-10T13:30:00+00:00")
    buf = [
        alpaca.TradeTick("AAPL", ts, Decimal("290.00")),
        alpaca.TradeTick("AAPL", ts, Decimal("290.10")),  # coalesces
        alpaca.TradeTick("MSFT", ts, Decimal("400.00")),
    ]
    written = await alpaca._flush(buf)
    assert written == 2

    async with db_module.session_scope() as session:
        rows = (await session.scalars(select(Price).order_by(Price.asset_id))).all()
    assert {r.asset_id for r in rows} == {"AAPL", "MSFT"}
