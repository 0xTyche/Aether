"""Async Redis client + thin helpers for the patterns we use repeatedly.

Two roles:
  - Dedup cache for incoming news URLs / LLM input hashes.
  - Pub/Sub channels decoupling ingestion writers from WebSocket fanout.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis_async

from aether.config import get_settings


_client: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    """Return a process-wide async Redis client."""
    global _client
    if _client is None:
        _client = redis_async.from_url(
            get_settings().redis_url,
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ---------- Dedup ---------------------------------------------------------

async def dedup_seen(key: str, *, ttl_seconds: int = 7 * 24 * 3600) -> bool:
    """Atomic "have I seen this before" check.

    Returns True if the key was already present; False if it was just added.
    The presence record auto-expires after `ttl_seconds`.
    """
    client = get_redis()
    # SET NX returns None when the key exists, "OK" when it was created.
    written = await client.set(key, "1", nx=True, ex=ttl_seconds)
    return written is None


def news_dedup_key(url: str) -> str:
    from hashlib import sha256

    digest = sha256(url.encode("utf-8")).hexdigest()
    return f"dedup:news:{digest}"


# ---------- Pub/Sub --------------------------------------------------------

CHANNEL_EVENTS_NEW = "events.new"
CHANNEL_PRICES_UPDATE = "prices.update"
CHANNEL_IMPACTS_OUTCOME = "impacts.outcome"


async def publish(channel: str, payload: dict[str, Any]) -> int:
    """Publish a JSON payload to a channel. Returns subscriber count."""
    client = get_redis()
    return await client.publish(channel, json.dumps(payload, default=str))


@asynccontextmanager
async def subscribe(*channels: str) -> AsyncIterator[redis_async.client.PubSub]:
    """Context manager yielding a PubSub on a *dedicated* connection.

    We deliberately bypass the shared client because long-lived subscribe
    connections cannot be reused for normal commands, and contending for the
    shared client's connection pool gives us spurious read timeouts.
    """
    cli = redis_async.from_url(
        get_settings().redis_url,
        decode_responses=True,
    )
    pubsub = cli.pubsub()
    try:
        await pubsub.subscribe(*channels)
        yield pubsub
    finally:
        try:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()
        finally:
            await cli.aclose()
