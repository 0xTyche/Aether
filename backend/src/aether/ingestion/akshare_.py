"""Periodic AKShare polling for non-Binance, non-Alpaca instruments.

AKShare is a synchronous library that scrapes various Chinese/HK data
sources. We dispatch a handful of fetchers per asset, each producing
the *latest* observation, and write into `prices`. Sync calls are
off-loaded to a thread to keep the event loop responsive.

Sources used (all confirmed reachable from US IP):
  - sh000001 (上证综指)   via stock_zh_index_daily (Sina)
  - HSI (恒生)            via stock_hk_index_daily_sina
  - USD/CNH               via fx_spot_quote (Sina)
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import akshare as ak
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from aether.models.prices import Price
from aether.storage import db as db_module


logger = structlog.get_logger(__name__)

SOURCE = "akshare"


@dataclass(slots=True)
class Quote:
    asset_id: str
    ts: datetime
    price: Decimal


# ---------- per-symbol fetchers (sync, run via to_thread) ----------------

def _fetch_shcomp() -> Quote | None:
    """上证综指 latest close from Sina daily series."""
    df = ak.stock_zh_index_daily(symbol="sh000001")
    if df is None or df.empty:
        return None
    row = df.iloc[-1]
    return Quote(
        asset_id="SHCOMP",
        ts=datetime.combine(row["date"], datetime.min.time(), tzinfo=UTC),
        price=Decimal(str(row["close"])),
    )


def _fetch_hsi() -> Quote | None:
    """恒生指数 latest close from Sina daily series."""
    df = ak.stock_hk_index_daily_sina(symbol="HSI")
    if df is None or df.empty:
        return None
    row = df.iloc[-1]
    return Quote(
        asset_id="HSI",
        ts=datetime.combine(row["date"], datetime.min.time(), tzinfo=UTC),
        price=Decimal(str(row["close"])),
    )


def _fetch_usdcnh() -> Quote | None:
    """USD/CNH spot quote — pick the row matching USD/CNH from fx_spot_quote."""
    df = ak.fx_spot_quote()
    if df is None or df.empty:
        return None
    pair_col = next(
        (c for c in df.columns if "对" in c or "pair" in c.lower()),
        df.columns[0],
    )
    bid_col = next(
        (c for c in df.columns if "买" in c or "bid" in c.lower()),
        df.columns[1] if len(df.columns) > 1 else None,
    )
    ask_col = next(
        (c for c in df.columns if "卖" in c or "ask" in c.lower()),
        None,
    )
    if bid_col is None:
        return None
    matches = df[df[pair_col].astype(str).str.contains("USD/CNH", case=False, na=False)]
    if matches.empty:
        # AKShare sometimes labels it USDCNH (no slash).
        matches = df[df[pair_col].astype(str).str.replace("/", "").str.upper() == "USDCNH"]
    if matches.empty:
        return None
    row = matches.iloc[0]
    bid = float(row[bid_col])
    ask = float(row[ask_col]) if ask_col and not (row[ask_col] is None) else bid
    mid = (bid + ask) / 2
    return Quote(asset_id="USD/CNH", ts=datetime.now(UTC), price=Decimal(str(mid)))


FETCHERS: dict[str, Callable[[], Quote | None]] = {
    "SHCOMP": _fetch_shcomp,
    "HSI": _fetch_hsi,
    "USD/CNH": _fetch_usdcnh,
}


# ---------- async orchestration ------------------------------------------

async def _safe_fetch(name: str, fn: Callable[[], Quote | None]) -> Quote | None:
    try:
        return await asyncio.to_thread(fn)
    except Exception as exc:
        logger.warning("akshare.fetch_failed", asset=name, error=str(exc))
        return None


async def _write_quotes(quotes: list[Quote]) -> int:
    if not quotes:
        return 0
    rows = [
        {"asset_id": q.asset_id, "ts": q.ts, "price": q.price, "source": SOURCE}
        for q in quotes
    ]
    stmt = pg_insert(Price).values(rows).on_conflict_do_nothing(
        index_elements=["asset_id", "ts"]
    )
    async with db_module.session_scope() as session:
        result = await session.execute(stmt)
    return result.rowcount or 0


async def tick() -> dict[str, bool]:
    """Pull every fetcher once. Returns {asset_id: was_written}."""
    results = await asyncio.gather(
        *(_safe_fetch(name, fn) for name, fn in FETCHERS.items())
    )
    quotes = [q for q in results if q is not None]
    written = await _write_quotes(quotes)
    out = {name: False for name in FETCHERS}
    for q in quotes:
        out[q.asset_id] = True
    logger.info("akshare.tick", quotes_fetched=len(quotes), rows_written=written)
    return out
