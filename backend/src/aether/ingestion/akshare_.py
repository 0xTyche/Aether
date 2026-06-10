"""Periodic AKShare polling for non-Binance, non-Alpaca instruments.

AKShare is a synchronous library that scrapes various Chinese/HK data
sources. Each "producer" function returns 0+ Quote objects in one call;
producers may batch multiple assets to amortize the upstream HTTP cost
(notably the FX producers, which fetch many pairs per call). Sync calls
are off-loaded to a thread to keep the event loop responsive.

Sources used (all confirmed reachable from US IP):
  - sh000001 (上证综指) via stock_zh_index_daily (Sina)
  - HSI (恒生)          via stock_hk_index_daily_sina
  - fx_pair_quote (Sina): 8 majors + AUD/JPY (derived from AUD/USD × USD/JPY)
  - fx_spot_quote (Sina): USD/CNH (proxied by USD/CNY) + 5 EM (derived
                          via USD/CNY × CNY/<X>)

NOT covered (eastmoney.com push2 endpoints — blocked from US IP):
  USD/QAR, USD/KWD, USD/OMR  (pegged to USD; could hardcode later)
  USD/INR, USD/BRL           (free-floating; needs a separate source)
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


Producer = Callable[[], list[Quote]]


# ---------- index / single-asset producers (each returns 0 or 1 Quote) ---

def _fetch_shcomp() -> list[Quote]:
    """上证综指 latest close from Sina daily series."""
    df = ak.stock_zh_index_daily(symbol="sh000001")
    if df is None or df.empty:
        return []
    row = df.iloc[-1]
    return [Quote(
        asset_id="SHCOMP",
        ts=datetime.combine(row["date"], datetime.min.time(), tzinfo=UTC),
        price=Decimal(str(row["close"])),
    )]


def _fetch_hsi() -> list[Quote]:
    """恒生指数 latest close from Sina daily series."""
    df = ak.stock_hk_index_daily_sina(symbol="HSI")
    if df is None or df.empty:
        return []
    row = df.iloc[-1]
    return [Quote(
        asset_id="HSI",
        ts=datetime.combine(row["date"], datetime.min.time(), tzinfo=UTC),
        price=Decimal(str(row["close"])),
    )]


# ---------- FX batch producers -------------------------------------------

def _mid(bid: float, ask: float | None) -> Decimal:
    a = ask if ask is not None else bid
    return Decimal(str((bid + a) / 2))


def _pairs_from_df(df, pair_col: str = "货币对") -> dict[str, Decimal]:
    """Index a Sina FX dataframe by pair → mid price."""
    bid_col = next(c for c in df.columns if "买" in c)
    ask_col = next((c for c in df.columns if "卖" in c), None)
    out: dict[str, Decimal] = {}
    for _, row in df.iterrows():
        try:
            bid = float(row[bid_col])
            ask = float(row[ask_col]) if ask_col else None
        except (TypeError, ValueError):
            continue
        out[str(row[pair_col]).strip().upper()] = _mid(bid, ask)
    return out


def _fetch_fx_majors() -> list[Quote]:
    """8 direct G10 pairs + AUD/JPY derived from AUD/USD × USD/JPY.

    Source: Sina fx_pair_quote (16 non-CNY pairs, real-time mid).
    """
    df = ak.fx_pair_quote()
    if df is None or df.empty:
        return []
    pairs = _pairs_from_df(df)
    ts = datetime.now(UTC)

    direct_map = {
        "USD/JPY": "USD/JPY",
        "EUR/USD": "EUR/USD",
        "GBP/USD": "GBP/USD",
        "USD/CHF": "USD/CHF",
        "USD/CAD": "USD/CAD",
        "NZD/USD": "NZD/USD",
        "EUR/GBP": "EUR/GBP",
        "EUR/JPY": "EUR/JPY",
    }
    quotes: list[Quote] = []
    for asset_id, sina_pair in direct_map.items():
        if sina_pair in pairs:
            quotes.append(Quote(asset_id, ts, pairs[sina_pair]))

    # AUD/JPY = AUD/USD × USD/JPY  (units: AUD→USD then USD→JPY = AUD→JPY)
    if "AUD/USD" in pairs and "USD/JPY" in pairs:
        aud_jpy = pairs["AUD/USD"] * pairs["USD/JPY"]
        quotes.append(Quote("AUD/JPY", ts, aud_jpy))

    return quotes


def _fetch_fx_em() -> list[Quote]:
    """USD/CNH proxied by USD/CNY + 5 EM/Gulf pairs derived via CNY crosses.

    Source: Sina fx_spot_quote (USD/CNY + CNY/X cross pairs).
    """
    df = ak.fx_spot_quote()
    if df is None or df.empty:
        return []
    pairs = _pairs_from_df(df)
    ts = datetime.now(UTC)
    quotes: list[Quote] = []

    usd_cny = pairs.get("USD/CNY")
    if usd_cny is not None:
        # USD/CNH and USD/CNY differ by <0.2%; accept as a proxy until we wire
        # a true offshore source.
        quotes.append(Quote("USD/CNH", ts, usd_cny))

        # USD/<X> = USD/CNY × CNY/<X>
        cny_crosses = {
            "USD/SAR": "CNY/SAR",
            "USD/AED": "CNY/AED",
            "USD/KRW": "CNY/KRW",
            "USD/TRY": "CNY/TRY",
            "USD/ZAR": "CNY/ZAR",
        }
        for asset_id, cny_pair in cny_crosses.items():
            cross = pairs.get(cny_pair)
            if cross is not None:
                quotes.append(Quote(asset_id, ts, usd_cny * cross))

    return quotes


# ---------- producer registry --------------------------------------------

PRODUCERS: dict[str, Producer] = {
    "shcomp": _fetch_shcomp,
    "hsi": _fetch_hsi,
    "fx_majors": _fetch_fx_majors,
    "fx_em": _fetch_fx_em,
}


# ---------- async orchestration ------------------------------------------

async def _safe_produce(name: str, fn: Producer) -> list[Quote]:
    try:
        return await asyncio.to_thread(fn)
    except Exception as exc:
        logger.warning("akshare.producer_failed", producer=name, error=str(exc))
        return []


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


async def tick() -> dict[str, list[str]]:
    """Run every producer once. Returns {producer_name: [asset_ids written]}."""
    per_producer = await asyncio.gather(
        *(_safe_produce(name, fn) for name, fn in PRODUCERS.items())
    )
    all_quotes: list[Quote] = []
    out: dict[str, list[str]] = {}
    for (name, _), quotes in zip(PRODUCERS.items(), per_producer, strict=True):
        out[name] = [q.asset_id for q in quotes]
        all_quotes.extend(quotes)

    written = await _write_quotes(all_quotes)
    logger.info(
        "akshare.tick",
        producers=len(PRODUCERS),
        quotes=len(all_quotes),
        rows_written=written,
    )
    return out
