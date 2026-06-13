"""Seed the 75 MVP+ assets across nine categories.

Idempotent: re-runs are safe (upsert by id).

Usage:
    uv run python scripts/seed_assets.py
    uv run python scripts/seed_assets.py --test    # target aether_test DB
"""

import argparse
import asyncio
import sys
from typing import TypedDict

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aether.config import get_settings
from aether.models.assets import Asset
from aether.storage import db as db_module


class AssetSpec(TypedDict, total=False):
    id: str
    asset_class: str
    display_name: str
    country_iso: str | None
    region: str | None
    binance_symbol: str | None
    akshare_func: str | None
    fred_series: str | None


# ---------- FX (10) -------------------------------------------------------
FX: list[AssetSpec] = [
    {"id": "USD/JPY",  "asset_class": "fx", "display_name": "USD/JPY", "country_iso": "JP", "akshare_func": "forex_hist_em"},
    {"id": "EUR/USD",  "asset_class": "fx", "display_name": "EUR/USD", "region": "Eurozone", "akshare_func": "forex_hist_em"},
    {"id": "GBP/USD",  "asset_class": "fx", "display_name": "GBP/USD", "country_iso": "GB", "akshare_func": "forex_hist_em"},
    {"id": "USD/CNH",  "asset_class": "fx", "display_name": "USD/CNH", "country_iso": "CN", "akshare_func": "forex_hist_em"},
    {"id": "AUD/JPY",  "asset_class": "fx", "display_name": "AUD/JPY", "country_iso": "AU", "akshare_func": "forex_hist_em"},
    {"id": "EUR/JPY",  "asset_class": "fx", "display_name": "EUR/JPY", "region": "Eurozone", "akshare_func": "forex_hist_em"},
    {"id": "USD/CHF",  "asset_class": "fx", "display_name": "USD/CHF", "country_iso": "CH", "akshare_func": "forex_hist_em"},
    {"id": "USD/CAD",  "asset_class": "fx", "display_name": "USD/CAD", "country_iso": "CA", "akshare_func": "forex_hist_em"},
    {"id": "NZD/USD",  "asset_class": "fx", "display_name": "NZD/USD", "country_iso": "NZ", "akshare_func": "forex_hist_em"},
    {"id": "EUR/GBP",  "asset_class": "fx", "display_name": "EUR/GBP", "region": "Europe", "akshare_func": "forex_hist_em"},
]

# ---------- Gulf currencies (5) -------------------------------------------
GULF_FX: list[AssetSpec] = [
    {"id": "USD/SAR", "asset_class": "fx", "display_name": "USD/SAR", "country_iso": "SA", "akshare_func": "forex_hist_em"},
    {"id": "USD/AED", "asset_class": "fx", "display_name": "USD/AED", "country_iso": "AE", "akshare_func": "forex_hist_em"},
    {"id": "USD/QAR", "asset_class": "fx", "display_name": "USD/QAR", "country_iso": "QA", "akshare_func": "forex_hist_em"},
    {"id": "USD/KWD", "asset_class": "fx", "display_name": "USD/KWD", "country_iso": "KW", "akshare_func": "forex_hist_em"},
    {"id": "USD/OMR", "asset_class": "fx", "display_name": "USD/OMR", "country_iso": "OM", "akshare_func": "forex_hist_em"},
]

# ---------- Emerging market FX (5) ----------------------------------------
EM_FX: list[AssetSpec] = [
    {"id": "USD/KRW", "asset_class": "fx", "display_name": "USD/KRW", "country_iso": "KR", "akshare_func": "forex_hist_em"},
    {"id": "USD/INR", "asset_class": "fx", "display_name": "USD/INR", "country_iso": "IN", "akshare_func": "forex_hist_em"},
    {"id": "USD/BRL", "asset_class": "fx", "display_name": "USD/BRL", "country_iso": "BR", "akshare_func": "forex_hist_em"},
    {"id": "USD/TRY", "asset_class": "fx", "display_name": "USD/TRY", "country_iso": "TR", "akshare_func": "forex_hist_em"},
    {"id": "USD/ZAR", "asset_class": "fx", "display_name": "USD/ZAR", "country_iso": "ZA", "akshare_func": "forex_hist_em"},
]

# ---------- Equity indices (10) -------------------------------------------
EQUITY_INDICES: list[AssetSpec] = [
    {"id": "SPX",       "asset_class": "equity_index", "display_name": "S&P 500",      "country_iso": "US"},
    {"id": "NDX",       "asset_class": "equity_index", "display_name": "Nasdaq 100",   "country_iso": "US"},
    {"id": "DJI",       "asset_class": "equity_index", "display_name": "Dow Jones",    "country_iso": "US"},
    {"id": "NKY",       "asset_class": "equity_index", "display_name": "Nikkei 225",   "country_iso": "JP", "akshare_func": "stock_zh_index_daily"},
    {"id": "SHCOMP",    "asset_class": "equity_index", "display_name": "上证综指",      "country_iso": "CN", "akshare_func": "stock_zh_index_daily"},
    {"id": "HSI",       "asset_class": "equity_index", "display_name": "恒生指数",      "country_iso": "HK", "akshare_func": "stock_hk_index_daily_em"},
    {"id": "HS300",     "asset_class": "equity_index", "display_name": "沪深 300",     "country_iso": "CN", "akshare_func": "stock_zh_index_daily"},
    {"id": "DAX",       "asset_class": "equity_index", "display_name": "DAX",          "country_iso": "DE"},
    {"id": "CAC40",     "asset_class": "equity_index", "display_name": "CAC 40",       "country_iso": "FR"},
    {"id": "FTSE100",   "asset_class": "equity_index", "display_name": "FTSE 100",     "country_iso": "GB"},
]

# ---------- Government bonds (5) ------------------------------------------
BONDS: list[AssetSpec] = [
    {"id": "US10Y", "asset_class": "bond", "display_name": "US 10Y Yield", "country_iso": "US", "fred_series": "DGS10"},
    {"id": "US2Y",  "asset_class": "bond", "display_name": "US 2Y Yield",  "country_iso": "US", "fred_series": "DGS2"},
    {"id": "DE10Y", "asset_class": "bond", "display_name": "Bund 10Y",     "country_iso": "DE"},
    {"id": "JP10Y", "asset_class": "bond", "display_name": "JGB 10Y",      "country_iso": "JP"},
    {"id": "CN10Y", "asset_class": "bond", "display_name": "中国国债 10Y", "country_iso": "CN", "akshare_func": "bond_zh_us_rate"},
]

# ---------- Commodities (8) -----------------------------------------------
COMMODITIES: list[AssetSpec] = [
    {"id": "BRENT",   "asset_class": "commodity", "display_name": "Brent Crude"},
    {"id": "WTI",     "asset_class": "commodity", "display_name": "WTI Crude"},
    {"id": "GOLD",    "asset_class": "commodity", "display_name": "Gold"},
    {"id": "SILVER",  "asset_class": "commodity", "display_name": "Silver"},
    {"id": "COPPER",  "asset_class": "commodity", "display_name": "Copper"},
    {"id": "NATGAS",  "asset_class": "commodity", "display_name": "Natural Gas"},
    {"id": "CORN",    "asset_class": "commodity", "display_name": "Corn"},
    {"id": "SOYBEAN", "asset_class": "commodity", "display_name": "Soybean"},
]

# ---------- Crypto (16) — Binance WebSocket -------------------------------
CRYPTO: list[AssetSpec] = [
    # Existing core 8
    {"id": "BTC",     "asset_class": "crypto", "display_name": "Bitcoin",  "binance_symbol": "BTCUSDT"},
    {"id": "ETH",     "asset_class": "crypto", "display_name": "Ethereum", "binance_symbol": "ETHUSDT"},
    {"id": "BNB",     "asset_class": "crypto", "display_name": "BNB",      "binance_symbol": "BNBUSDT"},
    {"id": "SOL",     "asset_class": "crypto", "display_name": "Solana",   "binance_symbol": "SOLUSDT"},
    {"id": "XRP",     "asset_class": "crypto", "display_name": "XRP",      "binance_symbol": "XRPUSDT"},
    {"id": "USDT/USD","asset_class": "crypto", "display_name": "USDT peg", "binance_symbol": "USDCUSDT"},
    {"id": "ETH/BTC", "asset_class": "crypto", "display_name": "ETH/BTC ratio", "binance_symbol": "ETHBTC"},
    {"id": "BTC.D",   "asset_class": "crypto", "display_name": "BTC dominance"},
    # Expansion +8 (by market cap, top ten alts as of 2026)
    {"id": "ADA",     "asset_class": "crypto", "display_name": "Cardano",  "binance_symbol": "ADAUSDT"},
    {"id": "DOGE",    "asset_class": "crypto", "display_name": "Dogecoin", "binance_symbol": "DOGEUSDT"},
    {"id": "AVAX",    "asset_class": "crypto", "display_name": "Avalanche","binance_symbol": "AVAXUSDT"},
    {"id": "DOT",     "asset_class": "crypto", "display_name": "Polkadot", "binance_symbol": "DOTUSDT"},
    {"id": "LINK",    "asset_class": "crypto", "display_name": "Chainlink","binance_symbol": "LINKUSDT"},
    {"id": "POL",     "asset_class": "crypto", "display_name": "Polygon (POL)", "binance_symbol": "POLUSDT"},
    {"id": "TRX",     "asset_class": "crypto", "display_name": "TRON",     "binance_symbol": "TRXUSDT"},
    {"id": "SHIB",    "asset_class": "crypto", "display_name": "Shiba Inu","binance_symbol": "SHIBUSDT"},
]

# ---------- US equities (70) ----------------------------------------------
# All Alpaca-verified reachable. ETFs and individual stocks live together
# in the equity class so the Alpaca WS subscriber picks them up uniformly.
US_EQUITIES: list[AssetSpec] = [
    # Mega-cap tech (10)
    {"id": "AAPL",  "asset_class": "equity", "display_name": "Apple",          "country_iso": "US"},
    {"id": "MSFT",  "asset_class": "equity", "display_name": "Microsoft",      "country_iso": "US"},
    {"id": "NVDA",  "asset_class": "equity", "display_name": "NVIDIA",         "country_iso": "US"},
    {"id": "GOOGL", "asset_class": "equity", "display_name": "Alphabet",       "country_iso": "US"},
    {"id": "META",  "asset_class": "equity", "display_name": "Meta Platforms", "country_iso": "US"},
    {"id": "AMZN",  "asset_class": "equity", "display_name": "Amazon",         "country_iso": "US"},
    {"id": "TSLA",  "asset_class": "equity", "display_name": "Tesla",          "country_iso": "US"},
    {"id": "NFLX",  "asset_class": "equity", "display_name": "Netflix",        "country_iso": "US"},
    {"id": "AVGO",  "asset_class": "equity", "display_name": "Broadcom",       "country_iso": "US"},
    {"id": "ORCL",  "asset_class": "equity", "display_name": "Oracle",         "country_iso": "US"},

    # Semis + hardware (4)
    {"id": "AMD",   "asset_class": "equity", "display_name": "AMD",                          "country_iso": "US"},
    {"id": "INTC",  "asset_class": "equity", "display_name": "Intel",                        "country_iso": "US"},
    {"id": "TSM",   "asset_class": "equity", "display_name": "TSMC (ADR)",                   "country_iso": "US"},
    {"id": "MU",    "asset_class": "equity", "display_name": "Micron",                       "country_iso": "US"},

    # AI / hot 2024-26 names (4)
    {"id": "PLTR",  "asset_class": "equity", "display_name": "Palantir",                     "country_iso": "US"},
    {"id": "ARM",   "asset_class": "equity", "display_name": "Arm Holdings",                 "country_iso": "US"},
    {"id": "SMCI",  "asset_class": "equity", "display_name": "Super Micro Computer",         "country_iso": "US"},
    {"id": "ANET",  "asset_class": "equity", "display_name": "Arista Networks",              "country_iso": "US"},

    # Software / cloud (4)
    {"id": "CRM",   "asset_class": "equity", "display_name": "Salesforce",                   "country_iso": "US"},
    {"id": "ADBE",  "asset_class": "equity", "display_name": "Adobe",                        "country_iso": "US"},
    {"id": "NOW",   "asset_class": "equity", "display_name": "ServiceNow",                   "country_iso": "US"},
    {"id": "CRWD",  "asset_class": "equity", "display_name": "CrowdStrike",                  "country_iso": "US"},

    # Banks & finance (5)
    {"id": "JPM",   "asset_class": "equity", "display_name": "JPMorgan Chase",               "country_iso": "US"},
    {"id": "BAC",   "asset_class": "equity", "display_name": "Bank of America",              "country_iso": "US"},
    {"id": "GS",    "asset_class": "equity", "display_name": "Goldman Sachs",                "country_iso": "US"},
    {"id": "MS",    "asset_class": "equity", "display_name": "Morgan Stanley",               "country_iso": "US"},
    {"id": "WFC",   "asset_class": "equity", "display_name": "Wells Fargo",                  "country_iso": "US"},
    {"id": "C",     "asset_class": "equity", "display_name": "Citigroup",                    "country_iso": "US"},

    # Conglomerate + payments (4)
    {"id": "BRK.B", "asset_class": "equity", "display_name": "Berkshire Hathaway B",         "country_iso": "US"},
    {"id": "V",     "asset_class": "equity", "display_name": "Visa",                         "country_iso": "US"},
    {"id": "MA",    "asset_class": "equity", "display_name": "Mastercard",                   "country_iso": "US"},
    {"id": "AXP",   "asset_class": "equity", "display_name": "American Express",             "country_iso": "US"},
    {"id": "BLK",   "asset_class": "equity", "display_name": "BlackRock",                    "country_iso": "US"},

    # Energy (5)
    {"id": "XOM",   "asset_class": "equity", "display_name": "Exxon Mobil",                  "country_iso": "US"},
    {"id": "CVX",   "asset_class": "equity", "display_name": "Chevron",                      "country_iso": "US"},
    {"id": "COP",   "asset_class": "equity", "display_name": "ConocoPhillips",               "country_iso": "US"},
    {"id": "SLB",   "asset_class": "equity", "display_name": "Schlumberger",                 "country_iso": "US"},
    {"id": "OXY",   "asset_class": "equity", "display_name": "Occidental Petroleum",         "country_iso": "US"},

    # Healthcare & pharma (6)
    {"id": "JNJ",   "asset_class": "equity", "display_name": "Johnson & Johnson",            "country_iso": "US"},
    {"id": "UNH",   "asset_class": "equity", "display_name": "UnitedHealth",                 "country_iso": "US"},
    {"id": "LLY",   "asset_class": "equity", "display_name": "Eli Lilly",                    "country_iso": "US"},
    {"id": "PFE",   "asset_class": "equity", "display_name": "Pfizer",                       "country_iso": "US"},
    {"id": "MRK",   "asset_class": "equity", "display_name": "Merck",                        "country_iso": "US"},
    {"id": "ABBV",  "asset_class": "equity", "display_name": "AbbVie",                       "country_iso": "US"},

    # Consumer staples (4)
    {"id": "WMT",   "asset_class": "equity", "display_name": "Walmart",                      "country_iso": "US"},
    {"id": "COST",  "asset_class": "equity", "display_name": "Costco",                       "country_iso": "US"},
    {"id": "KO",    "asset_class": "equity", "display_name": "Coca-Cola",                    "country_iso": "US"},
    {"id": "PEP",   "asset_class": "equity", "display_name": "PepsiCo",                      "country_iso": "US"},

    # Consumer discretionary (4)
    {"id": "MCD",   "asset_class": "equity", "display_name": "McDonald's",                   "country_iso": "US"},
    {"id": "NKE",   "asset_class": "equity", "display_name": "Nike",                         "country_iso": "US"},
    {"id": "HD",    "asset_class": "equity", "display_name": "Home Depot",                   "country_iso": "US"},
    {"id": "DIS",   "asset_class": "equity", "display_name": "Walt Disney",                  "country_iso": "US"},

    # Industrial (4)
    {"id": "CAT",   "asset_class": "equity", "display_name": "Caterpillar",                  "country_iso": "US"},
    {"id": "BA",    "asset_class": "equity", "display_name": "Boeing",                       "country_iso": "US"},
    {"id": "GE",    "asset_class": "equity", "display_name": "General Electric",             "country_iso": "US"},
    {"id": "DE",    "asset_class": "equity", "display_name": "John Deere",                   "country_iso": "US"},

    # Crypto-correlated (2)
    {"id": "COIN",  "asset_class": "equity", "display_name": "Coinbase",                     "country_iso": "US"},
    {"id": "MSTR",  "asset_class": "equity", "display_name": "MicroStrategy",                "country_iso": "US"},

    # ETFs — broad market (6)
    {"id": "SPY",   "asset_class": "equity", "display_name": "SPDR S&P 500 ETF",             "country_iso": "US"},
    {"id": "QQQ",   "asset_class": "equity", "display_name": "Invesco QQQ",                  "country_iso": "US"},
    {"id": "DIA",   "asset_class": "equity", "display_name": "SPDR Dow Jones ETF",           "country_iso": "US"},
    {"id": "IWM",   "asset_class": "equity", "display_name": "iShares Russell 2000",         "country_iso": "US"},
    {"id": "VTI",   "asset_class": "equity", "display_name": "Vanguard Total Stock Market",  "country_iso": "US"},
    {"id": "EEM",   "asset_class": "equity", "display_name": "iShares MSCI EM",              "country_iso": "US"},

    # ETFs — sector + thematic (5)
    {"id": "XLF",   "asset_class": "equity", "display_name": "Financial Sector ETF",         "country_iso": "US"},
    {"id": "XLE",   "asset_class": "equity", "display_name": "Energy Sector ETF",            "country_iso": "US"},
    {"id": "XLK",   "asset_class": "equity", "display_name": "Technology Sector ETF",        "country_iso": "US"},
    {"id": "ARKK",  "asset_class": "equity", "display_name": "ARK Innovation ETF",           "country_iso": "US"},
    {"id": "GLD",   "asset_class": "equity", "display_name": "SPDR Gold Shares",             "country_iso": "US"},

    # ETFs — bond (1)
    {"id": "TLT",   "asset_class": "equity", "display_name": "iShares 20+ Year Treasury",    "country_iso": "US"},
]

# ---------- Central bank policy rates (14) --------------------------------
CB_RATES: list[AssetSpec] = [
    {"id": "FED.RATE",    "asset_class": "rate", "display_name": "Fed Funds Rate",        "country_iso": "US", "fred_series": "FEDFUNDS"},
    {"id": "ECB.RATE",    "asset_class": "rate", "display_name": "ECB Deposit Rate",      "region": "Eurozone"},
    {"id": "BOJ.RATE",    "asset_class": "rate", "display_name": "BoJ Policy Rate",       "country_iso": "JP"},
    {"id": "BOE.RATE",    "asset_class": "rate", "display_name": "BoE Bank Rate",         "country_iso": "GB"},
    {"id": "PBOC.LPR",    "asset_class": "rate", "display_name": "PBoC LPR 1Y",           "country_iso": "CN", "akshare_func": "macro_china_lpr"},
    {"id": "SNB.RATE",    "asset_class": "rate", "display_name": "SNB Policy Rate",       "country_iso": "CH"},
    {"id": "RBA.RATE",    "asset_class": "rate", "display_name": "RBA Cash Rate",         "country_iso": "AU"},
    {"id": "BOC.RATE",    "asset_class": "rate", "display_name": "BoC Overnight Rate",    "country_iso": "CA"},
    {"id": "RBI.RATE",    "asset_class": "rate", "display_name": "RBI Repo Rate",         "country_iso": "IN"},
    {"id": "BOK.RATE",    "asset_class": "rate", "display_name": "BoK Base Rate",         "country_iso": "KR"},
    {"id": "BCB.RATE",    "asset_class": "rate", "display_name": "BCB Selic Rate",        "country_iso": "BR"},
    {"id": "SAMA.RATE",   "asset_class": "rate", "display_name": "SAMA Repo Rate",        "country_iso": "SA"},
    {"id": "BANXICO.RATE","asset_class": "rate", "display_name": "Banxico Overnight Rate","country_iso": "MX"},
    {"id": "CBRT.RATE",   "asset_class": "rate", "display_name": "CBRT One-Week Repo",    "country_iso": "TR"},
]


ALL_ASSETS: list[AssetSpec] = (
    FX + GULF_FX + EM_FX + EQUITY_INDICES + BONDS + COMMODITIES + CRYPTO + US_EQUITIES + CB_RATES
)


async def seed_assets(session: AsyncSession) -> int:
    """Upsert every asset. Returns total rows written."""
    rows = [
        {
            "id": a["id"],
            "asset_class": a["asset_class"],
            "display_name": a["display_name"],
            "country_iso": a.get("country_iso"),
            "region": a.get("region"),
            "binance_symbol": a.get("binance_symbol"),
            "akshare_func": a.get("akshare_func"),
            "fred_series": a.get("fred_series"),
        }
        for a in ALL_ASSETS
    ]
    stmt = pg_insert(Asset).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "asset_class": stmt.excluded.asset_class,
            "display_name": stmt.excluded.display_name,
            "country_iso": stmt.excluded.country_iso,
            "region": stmt.excluded.region,
            "binance_symbol": stmt.excluded.binance_symbol,
            "akshare_func": stmt.excluded.akshare_func,
            "fred_series": stmt.excluded.fred_series,
        },
    )
    await session.execute(stmt)
    return len(rows)


async def main(*, use_test_db: bool) -> None:
    settings = get_settings()
    url = settings.test_database_url if use_test_db else settings.database_url
    db_module.override_engine_for_tests(url)

    async with db_module.session_scope() as session:
        n = await seed_assets(session)

    target = "aether_test" if use_test_db else "aether"
    print(f"seeded {n} assets into '{target}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    try:
        asyncio.run(main(use_test_db=args.test))
    except Exception as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
