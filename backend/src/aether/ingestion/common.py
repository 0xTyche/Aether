"""Shared ingestion primitives: the normalized item shape and the
dedup → insert step every news source funnels through.

Extracted so new sources (jin10, …) don't re-copy the Redis-dedup +
`on_conflict_do_nothing` insert that `rss.py` / `akshare_news.py` each grew
their own copy of. Those two keep their local copies for now; folding them
onto this helper is a separate, test-covered refactor.
"""

from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from aether.models.news import RawNews
from aether.storage import db as db_module
from aether.storage import redis_ as r

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ParsedItem:
    """A source-agnostic news item ready for dedup + persistence.

    Downstream only ever sees `raw_news` rows, so every fetcher converges on
    this shape and hands batches to `persist_fresh`.
    """

    source: str
    url: str
    title: str
    body: str | None
    published_at: datetime
    lang: str = "en"


def short_title(text: str, max_len: int = 60) -> str:
    """Display title for items whose upstream omits one — first `max_len` chars."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


async def persist_fresh(items: list[ParsedItem]) -> int:
    """Dedup a batch and insert the never-seen items into `raw_news`.

    Two-stage dedup mirrors the other fetchers: a Redis SET (fast path, marks
    on check) with the `raw_news.url` UNIQUE constraint as the backstop for
    URLs evicted after their Redis TTL. Returns rows actually written.
    """
    if not items:
        return 0

    fresh: list[ParsedItem] = []
    for it in items:
        seen = await r.dedup_seen(r.news_dedup_key(it.url))
        if not seen:
            fresh.append(it)
    if not fresh:
        return 0

    rows = [
        {
            "source": it.source,
            "url": it.url,
            "title": it.title,
            "body": it.body,
            "published_at": it.published_at,
            "lang": it.lang,
        }
        for it in fresh
    ]
    stmt = pg_insert(RawNews).values(rows).on_conflict_do_nothing(index_elements=["url"])
    async with db_module.session_scope() as session:
        result = await session.execute(stmt)
    return result.rowcount or 0
