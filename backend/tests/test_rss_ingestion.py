"""RSS ingestion: parsing, dedup, error isolation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from aether.ingestion import rss
from aether.models.news import RawNews
from aether.storage import db as db_module
from aether.storage import redis_ as r


SAMPLE_FEED_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Mock Bank Press Releases</title>
    <link>https://mock.example/</link>
    <description>Mock</description>
    <item>
      <title>Mock Bank holds rates at 4.50%</title>
      <link>https://mock.example/release/{id}-a</link>
      <pubDate>Tue, 09 Jun 2026 14:00:00 +0000</pubDate>
      <description>Mock Bank's Monetary Policy Committee voted to hold rates...</description>
    </item>
    <item>
      <title>Mock Bank governor speech at central banking conference</title>
      <link>https://mock.example/release/{id}-b</link>
      <pubDate>Mon, 08 Jun 2026 09:30:00 +0000</pubDate>
      <description>The governor delivered remarks emphasising...</description>
    </item>
  </channel>
</rss>
"""


@pytest_asyncio.fixture
async def clean_news_and_redis() -> None:
    """Truncate raw_news and clear any dedup keys touching mock.example URLs."""
    async with db_module.session_scope() as session:
        await session.execute(text("TRUNCATE TABLE raw_news RESTART IDENTITY CASCADE"))

    client = r.get_redis()
    # mock.example URLs all hash differently, so just nuke the whole dedup
    # namespace for the test run.
    async for key in client.scan_iter(match="dedup:news:*"):
        await client.delete(key)


def _mock_response(text_body: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=text_body.encode("utf-8"),
        request=httpx.Request("GET", "https://mock.example/feed.xml"),
    )


# ---------- parsing -------------------------------------------------------

def test_parse_feed_bytes_extracts_two_items():
    items = rss._parse_feed_bytes(SAMPLE_FEED_TEMPLATE.format(id="x").encode())
    assert len(items) == 2
    assert all(it.url.startswith("https://mock.example/") for it in items)
    assert all(it.title.startswith("Mock Bank") for it in items)
    assert items[0].published_at == datetime(2026, 6, 9, 14, 0, tzinfo=UTC)


def test_parse_feed_bytes_skips_entries_missing_link_or_title():
    body = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <title>x</title><link>x</link><description>x</description>
      <item><title>has title, no link</title></item>
      <item><link>https://mock.example/no-title</link></item>
    </channel></rss>"""
    assert rss._parse_feed_bytes(body.encode()) == []


# ---------- end-to-end ingest_feed ----------------------------------------

@pytest.mark.usefixtures("clean_news_and_redis")
async def test_first_run_writes_all_items_second_run_writes_none():
    feed = rss.Feed("MockBank", "https://mock.example/feed.xml")
    body = SAMPLE_FEED_TEMPLATE.format(id="first")

    with patch.object(rss, "_fetch_bytes", AsyncMock(return_value=body.encode())):
        async with httpx.AsyncClient() as client:
            n1 = await rss.ingest_feed(feed, client)
            n2 = await rss.ingest_feed(feed, client)

    assert n1 == 2
    assert n2 == 0  # all dedup'd via Redis

    async with db_module.session_scope() as session:
        rows = await session.scalar(select(func.count()).select_from(RawNews))
        assert rows == 2


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_different_feeds_use_independent_dedup():
    """Same URL across runs dedups; different URLs don't."""
    feed = rss.Feed("MockBank", "https://mock.example/feed.xml")
    body_a = SAMPLE_FEED_TEMPLATE.format(id="aaa")
    body_b = SAMPLE_FEED_TEMPLATE.format(id="bbb")

    async with httpx.AsyncClient() as client:
        with patch.object(rss, "_fetch_bytes", AsyncMock(return_value=body_a.encode())):
            n1 = await rss.ingest_feed(feed, client)
        with patch.object(rss, "_fetch_bytes", AsyncMock(return_value=body_b.encode())):
            n2 = await rss.ingest_feed(feed, client)

    assert n1 == 2
    assert n2 == 2  # different URLs, no overlap

    async with db_module.session_scope() as session:
        total = await session.scalar(select(func.count()).select_from(RawNews))
        assert total == 4


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_fetch_failure_returns_zero_without_raising():
    feed = rss.Feed("Broken", "https://mock.example/dead.xml")

    async def boom(*_args, **_kwargs):
        raise httpx.ConnectError("simulated dead host")

    with patch.object(rss, "_fetch_bytes", side_effect=boom):
        async with httpx.AsyncClient() as client:
            n = await rss.ingest_feed(feed, client)

    assert n == 0
    async with db_module.session_scope() as session:
        rows = await session.scalar(select(func.count()).select_from(RawNews))
        assert rows == 0


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_ingest_all_feeds_isolates_per_feed_failure():
    """One broken feed must not block the rest."""
    good = rss.Feed("Good", "https://mock.example/good.xml")
    bad = rss.Feed("Bad", "https://mock.example/bad.xml")

    good_body = SAMPLE_FEED_TEMPLATE.format(id="good")

    async def fake_fetch(_client, url):
        if "good" in url:
            return good_body.encode()
        raise httpx.ConnectError("bad host")

    with patch.object(rss, "_fetch_bytes", side_effect=fake_fetch):
        result = await rss.ingest_all_feeds([good, bad])

    assert result == {"Good": 2, "Bad": 0}
