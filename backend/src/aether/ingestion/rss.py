"""Pull central-bank RSS feeds and persist new items to `raw_news`.

Design notes:
  - URL-level dedup goes through Redis (TTL 7d) so a feed restart, a feed
    re-publishing an old item, or two scheduler ticks racing won't insert
    duplicates. The DB `raw_news.url UNIQUE` constraint is a hard backstop.
  - Each feed fetch is wrapped in its own try/except so one broken feed
    cannot stall the tick or wedge other feeds.
  - `feedparser` is sync; we run it in a thread so we don't block the loop.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx
import structlog

from aether.ingestion.common import ParsedItem as StoredItem
from aether.ingestion.common import persist_fresh

logger = structlog.get_logger(__name__)


HTTP_TIMEOUT = httpx.Timeout(10.0)
HTTP_HEADERS = {"User-Agent": "aether-bot/0.1 (+https://github.com/0xTyche/Aether)"}


@dataclass(frozen=True, slots=True)
class Feed:
    name: str
    url: str
    lang: str = "en"


# Four central-bank feeds confirmed to parse cleanly with feedparser.
CENTRAL_BANK_FEEDS: list[Feed] = [
    Feed("Fed", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    Feed("ECB", "https://www.ecb.europa.eu/rss/press.xml"),
    Feed("BoJ", "https://www.boj.or.jp/en/rss/whatsnew.xml"),
    Feed("BoE", "https://www.bankofengland.co.uk/rss/news"),
]


@dataclass(frozen=True, slots=True)
class ParsedItem:
    url: str
    title: str
    body: str | None
    published_at: datetime


def _coerce_published(entry: dict) -> datetime:
    """Best-effort parse of an RSS entry's publish timestamp into UTC."""
    raw = entry.get("published") or entry.get("updated") or entry.get("pubDate")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            dt = None
        if dt is not None:
            return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    # Fall back to now if the feed gave us nothing usable.
    return datetime.now(UTC)


def _parse_feed_bytes(body: bytes) -> list[ParsedItem]:
    parsed = feedparser.parse(body)
    items: list[ParsedItem] = []
    for e in parsed.entries:
        url = e.get("link")
        title = e.get("title")
        if not url or not title:
            continue
        body_text = e.get("summary") or (
            e.get("content")[0].get("value") if e.get("content") else None
        )
        items.append(
            ParsedItem(
                url=url.strip(),
                title=title.strip(),
                body=body_text.strip() if body_text else None,
                published_at=_coerce_published(e),
            )
        )
    return items


async def _fetch_bytes(client: httpx.AsyncClient, url: str) -> bytes:
    res = await client.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    res.raise_for_status()
    return res.content


async def ingest_feed(feed: Feed, client: httpx.AsyncClient) -> int:
    """Pull one feed and insert any never-seen items. Returns rows written."""
    try:
        body = await _fetch_bytes(client, feed.url)
    except Exception as exc:
        logger.warning("rss.fetch_failed", feed=feed.name, error=str(exc))
        return 0

    try:
        items = await asyncio.to_thread(_parse_feed_bytes, body)
    except Exception as exc:
        logger.warning("rss.parse_failed", feed=feed.name, error=str(exc))
        return 0

    if not items:
        return 0

    # Dedup + insert (two-stage: Redis SET fast-path, raw_news.url UNIQUE as the
    # post-TTL backstop) is shared across all news sources; see common.py.
    written = await persist_fresh(
        [
            StoredItem(
                source=feed.name,
                url=it.url,
                title=it.title,
                body=it.body,
                published_at=it.published_at,
                lang=feed.lang,
            )
            for it in items
        ]
    )
    logger.info("rss.ingested", feed=feed.name, parsed=len(items), written=written)
    return written


async def ingest_all_feeds(feeds: list[Feed] | None = None) -> dict[str, int]:
    """Pull all feeds in parallel. One failure does not abort others."""
    feeds = feeds if feeds is not None else CENTRAL_BANK_FEEDS
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(ingest_feed(f, client) for f in feeds),
            return_exceptions=True,
        )

    out: dict[str, int] = {}
    for feed, res in zip(feeds, results, strict=True):
        if isinstance(res, BaseException):
            logger.error("rss.tick_failed", feed=feed.name, error=str(res))
            out[feed.name] = 0
        else:
            out[feed.name] = res
    return out
