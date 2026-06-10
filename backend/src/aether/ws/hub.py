"""In-process WebSocket Hub.

Listens to three Redis Pub/Sub channels (events / prices / impacts) and
fans out the payloads to every connected WebSocket client that asked to
subscribe to that channel.

High-frequency `prices.update` messages are accumulated in an in-memory
buffer and flushed every `THROTTLE_MS` so the wire (and the browser) is
not overwhelmed by individual ticks. Within a flush window we coalesce
by asset_id keeping the latest value seen — the client cares about the
freshest price, not every intermediate tick.

The Hub is a singleton owned by the FastAPI app lifespan.
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import WebSocket

from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)


THROTTLE_MS = 200
KNOWN_CHANNELS = ("events", "prices", "impacts")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class Hub:
    """Per-process registry of connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict[WebSocket, set[str]] = {}
        self._price_buffer: list[dict[str, Any]] = []
        self._tasks: list[asyncio.Task] = []
        self._started = False

    # ---------- client lifecycle ----------------------------------------

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients[ws] = set()
        try:
            await ws.send_json({"type": "welcome", "ts": _now_iso()})
        except Exception:
            self._clients.pop(ws, None)
            raise

    def unregister(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    def subscribe(self, ws: WebSocket, channels: list[str]) -> set[str]:
        valid = {c for c in channels if c in KNOWN_CHANNELS}
        subs = self._clients.get(ws)
        if subs is not None:
            subs.update(valid)
            return set(subs)
        return set()

    def unsubscribe(self, ws: WebSocket, channels: list[str]) -> set[str]:
        subs = self._clients.get(ws)
        if subs is None:
            return set()
        subs.difference_update(channels)
        return set(subs)

    def client_count(self) -> int:
        return len(self._clients)

    def subscriptions(self, ws: WebSocket) -> set[str]:
        return set(self._clients.get(ws, set()))

    # ---------- broadcast helpers ---------------------------------------

    async def broadcast(self, channel: str, message: dict[str, Any]) -> int:
        sent = 0
        dead: list[WebSocket] = []
        for ws, subs in list(self._clients.items()):
            if channel not in subs:
                continue
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister(ws)
        if dead:
            logger.info("ws.dropped_dead_clients", count=len(dead))
        return sent

    # ---------- Redis subscriber loops -----------------------------------

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._tasks = [
            asyncio.create_task(self._events_loop(), name="hub.events"),
            asyncio.create_task(self._prices_loop(), name="hub.prices"),
            asyncio.create_task(self._impacts_loop(), name="hub.impacts"),
            asyncio.create_task(self._throttle_loop(), name="hub.throttle"),
        ]
        logger.info("ws.hub_started", tasks=len(self._tasks))

    async def stop(self) -> None:
        if not self._started:
            return
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self._started = False
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()

    async def _subscriber(self, channel: str, on_message) -> None:
        """Generic Redis subscriber wrapper."""
        while True:
            try:
                async with r.subscribe(channel) as sub:
                    async for msg in sub.listen():
                        if msg.get("type") != "message":
                            continue
                        try:
                            payload = json.loads(msg["data"])
                        except (json.JSONDecodeError, TypeError):
                            continue
                        try:
                            await on_message(payload)
                        except Exception:
                            logger.exception("ws.subscriber_handler_failed", channel=channel)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Idle pubsub sockets are reaped by Redis after ~30s; the
                # reconnect path is by design, so we log at debug level
                # to avoid log spam during low-traffic periods.
                logger.debug("ws.subscriber_reconnect",
                             channel=channel, error=str(exc))
                await asyncio.sleep(2)

    async def _events_loop(self) -> None:
        async def handle(payload):
            await self.broadcast("events", {"type": "event.new", "event": payload})
        await self._subscriber(r.CHANNEL_EVENTS_NEW, handle)

    async def _prices_loop(self) -> None:
        async def handle(payload):
            updates = payload.get("updates")
            if isinstance(updates, list):
                self._price_buffer.extend(updates)
        await self._subscriber(r.CHANNEL_PRICES_UPDATE, handle)

    async def _impacts_loop(self) -> None:
        async def handle(payload):
            await self.broadcast(
                "impacts", {"type": "impact.outcome", **payload},
            )
        await self._subscriber(r.CHANNEL_IMPACTS_OUTCOME, handle)

    async def _throttle_loop(self) -> None:
        """Drain the price buffer every THROTTLE_MS and broadcast a batch."""
        try:
            while True:
                await asyncio.sleep(THROTTLE_MS / 1000)
                if not self._price_buffer:
                    continue
                pending = self._price_buffer
                self._price_buffer = []
                # Coalesce by asset_id; keep last (freshest) value.
                by_asset: dict[str, dict[str, Any]] = {}
                for u in pending:
                    aid = u.get("asset_id")
                    if aid:
                        by_asset[aid] = u
                if not by_asset:
                    continue
                await self.broadcast("prices", {
                    "type": "price.update",
                    "ts": _now_iso(),
                    "updates": list(by_asset.values()),
                })
        except asyncio.CancelledError:
            raise


_hub: Hub | None = None


def get_hub() -> Hub:
    global _hub
    if _hub is None:
        _hub = Hub()
    return _hub


def reset_hub_for_tests() -> None:
    """Drop the singleton so tests get a fresh, un-started Hub."""
    global _hub
    _hub = None
