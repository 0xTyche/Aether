"""News feeds via AKShare.

Five Chinese-language financial news streams are wrapped here. Each
fetcher returns a list of `ParsedItem`s with the same shape as the RSS
ingestion module, so the downstream pipeline (rules + LLM + WS hub)
needs zero changes.

Notes:
  - AKShare is sync (HTTP under the hood). We wrap calls in
    `asyncio.to_thread` to keep the event loop responsive.
  - Several sources (sina, futu) sometimes ship items without a stable
    URL or with an empty title — we fall back to a sha256-based
    synthetic URL and the first 60 chars of the content for the title.
  - URL-level dedup goes through the SAME Redis SET the RSS pipeline
    uses (`dedup:news:{sha256(url)}`, 7d TTL). Same item returned by
    every poll therefore never hits the DB twice.
  - `stock_info_global_cls` (财联社) currently returns 404 from this
    VPS; left out of the registered fetchers until reachable from a
    CN-based deploy. Add `_fetch_cls` back when needed.
"""

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import akshare as ak
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from aether.models.news import RawNews
from aether.storage import db as db_module
from aether.storage import redis_ as r


logger = structlog.get_logger(__name__)

# Beijing time — what AKShare's Chinese sources publish in.
CST = timezone(timedelta(hours=8))


@dataclass(frozen=True, slots=True)
class ParsedItem:
    source: str
    url: str
    title: str
    body: str | None
    published_at: datetime
    lang: str = "zh"


# ---------- helpers ------------------------------------------------------

def _parse_cst(raw: Any) -> datetime:
    """Parse '2026-06-12 17:31:14' as Beijing time → UTC datetime."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            raw = raw.replace(tzinfo=CST)
        return raw.astimezone(UTC)
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=CST).astimezone(UTC)
        except ValueError:
            continue
    # Last-ditch: now() so the row at least lands somewhere chronological.
    return datetime.now(UTC)


def _synth_url(source: str, title: str, ts: datetime) -> str:
    """Stable synthetic URL for items the upstream didn't supply one."""
    key = f"{source}|{title}|{ts.isoformat()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"akshare://{source}/{digest}"


def _short_title(text: str, max_len: int = 60) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


# ---------- per-source fetchers (sync, run via to_thread) ---------------

def _fetch_cjzc() -> list[ParsedItem]:
    """东方财富-财经早餐 (daily morning brief)."""
    df = ak.stock_info_cjzc_em()
    if df is None or df.empty:
        return []
    out: list[ParsedItem] = []
    for _, row in df.iterrows():
        ts = _parse_cst(row.get("发布时间"))
        title = str(row.get("标题") or "").strip() or _short_title(str(row.get("摘要") or ""))
        url = (str(row.get("链接") or "").strip() or _synth_url("财经早餐", title, ts))
        out.append(ParsedItem(
            source="财经早餐",
            url=url,
            title=title,
            body=str(row.get("摘要") or "") or None,
            published_at=ts,
        ))
    return out


def _fetch_global_em() -> list[ParsedItem]:
    """东方财富-全球财经快讯."""
    df = ak.stock_info_global_em()
    if df is None or df.empty:
        return []
    out: list[ParsedItem] = []
    for _, row in df.iterrows():
        ts = _parse_cst(row.get("发布时间"))
        title = str(row.get("标题") or "").strip() or _short_title(str(row.get("摘要") or ""))
        url = (str(row.get("链接") or "").strip() or _synth_url("东财快讯", title, ts))
        out.append(ParsedItem(
            source="东财快讯",
            url=url,
            title=title,
            body=str(row.get("摘要") or "") or None,
            published_at=ts,
        ))
    return out


def _fetch_global_sina() -> list[ParsedItem]:
    """新浪财经-全球财经快讯. Only ships 时间 + 内容; no title."""
    df = ak.stock_info_global_sina()
    if df is None or df.empty:
        return []
    out: list[ParsedItem] = []
    for _, row in df.iterrows():
        ts = _parse_cst(row.get("时间"))
        body = str(row.get("内容") or "").strip()
        if not body:
            continue
        title = _short_title(body)
        out.append(ParsedItem(
            source="新浪快讯",
            url=_synth_url("新浪快讯", title, ts),
            title=title,
            body=body,
            published_at=ts,
        ))
    return out


def _fetch_global_futu() -> list[ParsedItem]:
    """富途牛牛-快讯. Title is often empty; fall back to truncated 内容."""
    df = ak.stock_info_global_futu()
    if df is None or df.empty:
        return []
    out: list[ParsedItem] = []
    for _, row in df.iterrows():
        ts = _parse_cst(row.get("发布时间"))
        body = str(row.get("内容") or "").strip()
        title = str(row.get("标题") or "").strip() or _short_title(body)
        if not title and not body:
            continue
        url = (str(row.get("链接") or "").strip() or _synth_url("富途快讯", title, ts))
        out.append(ParsedItem(
            source="富途快讯",
            url=url,
            title=title,
            body=body or None,
            published_at=ts,
        ))
    return out


def _fetch_global_ths() -> list[ParsedItem]:
    """同花顺-全球财经直播."""
    df = ak.stock_info_global_ths()
    if df is None or df.empty:
        return []
    out: list[ParsedItem] = []
    for _, row in df.iterrows():
        ts = _parse_cst(row.get("发布时间"))
        body = str(row.get("内容") or "").strip()
        title = str(row.get("标题") or "").strip() or _short_title(body)
        if not title:
            continue
        url = (str(row.get("链接") or "").strip() or _synth_url("同花顺", title, ts))
        out.append(ParsedItem(
            source="同花顺",
            url=url,
            title=title,
            body=body or None,
            published_at=ts,
        ))
    return out


# ---------- registry ----------------------------------------------------

Fetcher = Callable[[], list[ParsedItem]]

FETCHERS: dict[str, Fetcher] = {
    "财经早餐": _fetch_cjzc,
    "东财快讯": _fetch_global_em,
    "新浪快讯": _fetch_global_sina,
    "富途快讯": _fetch_global_futu,
    "同花顺": _fetch_global_ths,
    # "财联社": _fetch_cls,  # 404 from US VPS; add back when deployed in CN.
}


# ---------- ingest one source -------------------------------------------

async def ingest_source(name: str, fn: Fetcher) -> int:
    """Pull one source and insert any never-seen items. Returns rows written."""
    try:
        items = await asyncio.to_thread(fn)
    except Exception as exc:
        logger.warning("akshare_news.fetch_failed", source=name, error=str(exc))
        return 0

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
    stmt = pg_insert(RawNews).values(rows).on_conflict_do_nothing(
        index_elements=["url"]
    )
    async with db_module.session_scope() as session:
        result = await session.execute(stmt)

    written = result.rowcount or 0
    logger.info(
        "akshare_news.ingested",
        source=name,
        parsed=len(items),
        new=len(fresh),
        written=written,
    )
    return written


async def ingest_all_sources(
    sources: dict[str, Fetcher] | None = None,
) -> dict[str, int]:
    """Pull all sources in parallel; per-source failure is isolated."""
    src = sources if sources is not None else FETCHERS
    results = await asyncio.gather(
        *(ingest_source(name, fn) for name, fn in src.items()),
        return_exceptions=True,
    )
    out: dict[str, int] = {}
    for (name, _), res in zip(src.items(), results, strict=True):
        if isinstance(res, BaseException):
            logger.error("akshare_news.tick_failed", source=name, error=str(res))
            out[name] = 0
        else:
            out[name] = res
    return out


async def tick() -> dict[str, int]:
    """Scheduler entry point."""
    return await ingest_all_sources()
