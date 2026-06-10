"""WebSocket Hub: client lifecycle, broadcast filter, Redis fan-out, throttle."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from aether.main import app
from aether.storage import redis_ as r
from aether.ws import hub as hub_module
from aether.ws.hub import Hub


class FakeWS:
    """Minimal WebSocket double for direct Hub testing."""

    def __init__(self, *, raise_on_send: bool = False):
        self.sent: list[dict[str, Any]] = []
        self.accepted = False
        self.raise_on_send = raise_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.raise_on_send:
            raise ConnectionError("client gone")
        self.sent.append(payload)

    async def close(self) -> None:
        pass


# ---------- client lifecycle --------------------------------------------

async def test_register_sends_welcome_and_tracks_client():
    hub = Hub()
    ws = FakeWS()
    await hub.register(ws)
    assert ws.accepted
    assert hub.client_count() == 1
    assert ws.sent[0]["type"] == "welcome"
    assert "ts" in ws.sent[0]


async def test_unregister_removes_client():
    hub = Hub()
    ws = FakeWS()
    await hub.register(ws)
    hub.unregister(ws)
    assert hub.client_count() == 0


async def test_subscribe_only_accepts_known_channels():
    hub = Hub()
    ws = FakeWS()
    await hub.register(ws)
    subs = hub.subscribe(ws, ["events", "prices", "garbage"])
    assert subs == {"events", "prices"}
    assert hub.subscriptions(ws) == {"events", "prices"}


async def test_unsubscribe_drops_channels():
    hub = Hub()
    ws = FakeWS()
    await hub.register(ws)
    hub.subscribe(ws, ["events", "prices"])
    remaining = hub.unsubscribe(ws, ["events"])
    assert remaining == {"prices"}


# ---------- broadcast filter --------------------------------------------

async def test_broadcast_skips_unsubscribed_clients():
    hub = Hub()
    a = FakeWS()
    b = FakeWS()
    await hub.register(a)
    await hub.register(b)
    hub.subscribe(a, ["events"])
    hub.subscribe(b, ["prices"])

    sent = await hub.broadcast("events", {"type": "event.new"})
    assert sent == 1
    assert any(m.get("type") == "event.new" for m in a.sent)
    assert not any(m.get("type") == "event.new" for m in b.sent)


async def test_broadcast_drops_dead_clients():
    hub = Hub()
    good = FakeWS()
    bad = FakeWS()
    await hub.register(good)
    await hub.register(bad)
    hub.subscribe(good, ["events"])
    hub.subscribe(bad, ["events"])
    # Simulate that `bad` died after registration but before this broadcast.
    bad.raise_on_send = True

    sent = await hub.broadcast("events", {"type": "event.new"})
    assert sent == 1  # only good received
    assert hub.client_count() == 1  # bad was dropped


# ---------- throttle ----------------------------------------------------

async def test_throttle_coalesces_buffer_by_asset_id():
    hub = Hub()
    ws = FakeWS()
    await hub.register(ws)
    hub.subscribe(ws, ["prices"])

    # Inject directly into the buffer (bypass Redis for unit test).
    hub._price_buffer.extend([
        {"asset_id": "BTC", "price": "60000", "source": "binance", "ts": "2026-01-01T00:00:00Z"},
        {"asset_id": "BTC", "price": "60100", "source": "binance", "ts": "2026-01-01T00:00:01Z"},
        {"asset_id": "ETH", "price": "1600", "source": "binance", "ts": "2026-01-01T00:00:00Z"},
    ])

    # Run throttle loop briefly to trigger one flush.
    task = asyncio.create_task(hub._throttle_loop())
    await asyncio.sleep(0.35)  # > 200ms so we see at least one flush
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    price_msgs = [m for m in ws.sent if m.get("type") == "price.update"]
    assert len(price_msgs) == 1
    updates = price_msgs[0]["updates"]
    assert len(updates) == 2  # BTC + ETH; BTC coalesced
    by_id = {u["asset_id"]: u for u in updates}
    assert by_id["BTC"]["price"] == "60100"  # latest


# ---------- Redis subscriber end-to-end ---------------------------------

@pytest_asyncio.fixture
async def started_hub():
    """A fresh Hub with subscriber loops running."""
    hub = Hub()
    await hub.start()
    yield hub
    await hub.stop()


async def test_event_published_to_redis_reaches_subscribed_client(started_hub):
    ws = FakeWS()
    await started_hub.register(ws)
    started_hub.subscribe(ws, ["events"])

    # Give the subscriber loop a moment to be ready.
    await asyncio.sleep(0.1)

    await r.publish(r.CHANNEL_EVENTS_NEW, {"title": "Test event"})

    # Wait briefly for the message to land.
    for _ in range(20):
        if any(m.get("type") == "event.new" for m in ws.sent):
            break
        await asyncio.sleep(0.05)
    event_msgs = [m for m in ws.sent if m.get("type") == "event.new"]
    assert len(event_msgs) == 1
    assert event_msgs[0]["event"] == {"title": "Test event"}


async def test_price_published_to_redis_is_throttled(started_hub):
    ws = FakeWS()
    await started_hub.register(ws)
    started_hub.subscribe(ws, ["prices"])

    await asyncio.sleep(0.1)

    # Publish several ticks rapidly.
    for i in range(5):
        await r.publish(r.CHANNEL_PRICES_UPDATE, {
            "updates": [
                {"asset_id": "BTC", "price": f"6000{i}", "source": "binance",
                 "ts": f"2026-01-01T00:00:0{i}Z"},
            ],
        })

    # Wait for one throttle window to flush.
    for _ in range(20):
        if any(m.get("type") == "price.update" for m in ws.sent):
            break
        await asyncio.sleep(0.05)

    price_msgs = [m for m in ws.sent if m.get("type") == "price.update"]
    assert len(price_msgs) >= 1
    # All 5 BTC updates should coalesce into 1 latest value per flush.
    first_batch = price_msgs[0]["updates"]
    assert len(first_batch) == 1
    assert first_batch[0]["asset_id"] == "BTC"
    assert first_batch[0]["price"] == "60004"  # latest of the burst


# ---------- /ws endpoint integration ------------------------------------

def test_ws_endpoint_handshake_and_ping_pong():
    """Connect, receive welcome, subscribe, ping, expect pong, disconnect."""
    # Reset hub singleton so it can re-start cleanly under the lifespan.
    hub_module.reset_hub_for_tests()

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"

        ws.send_json({"type": "subscribe", "channels": ["events", "garbage"]})
        sub_ack = ws.receive_json()
        assert sub_ack["type"] == "subscribed"
        assert sub_ack["channels"] == ["events"]

        ws.send_json({"type": "ping", "ts": "abc"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert pong["ts"] == "abc"

        ws.send_json({"type": "wat"})
        err = ws.receive_json()
        assert err["type"] == "error"
