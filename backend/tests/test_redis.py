"""Redis dedup + pub/sub roundtrip sanity checks."""

import asyncio
import json
import uuid

import pytest

from aether.storage import redis_ as r


@pytest.fixture(autouse=True)
async def _flush_test_keys():
    """Clear any test-prefixed keys between tests."""
    client = r.get_redis()
    async for key in client.scan_iter(match="test:*"):
        await client.delete(key)
    yield
    async for key in client.scan_iter(match="test:*"):
        await client.delete(key)


async def test_dedup_first_call_returns_false_second_returns_true():
    key = f"test:dedup:{uuid.uuid4()}"
    first = await r.dedup_seen(key)
    second = await r.dedup_seen(key)
    assert first is False
    assert second is True


async def test_news_dedup_key_is_stable_and_unique_per_url():
    a = r.news_dedup_key("https://example.com/a")
    b = r.news_dedup_key("https://example.com/b")
    a_again = r.news_dedup_key("https://example.com/a")
    assert a == a_again
    assert a != b


async def test_publish_subscribe_roundtrip():
    channel = "test:events.new"
    payload = {"hello": "aether", "n": 42}

    received: asyncio.Queue[dict] = asyncio.Queue()

    async def listener():
        async with r.subscribe(channel) as sub:
            async for message in sub.listen():
                if message["type"] == "message":
                    received.put_nowait(json.loads(message["data"]))
                    return

    task = asyncio.create_task(listener())
    # Give the subscription a moment to wire up before publishing.
    await asyncio.sleep(0.1)
    n = await r.publish(channel, payload)
    assert n >= 1

    got = await asyncio.wait_for(received.get(), timeout=2.0)
    assert got == payload
    await task
