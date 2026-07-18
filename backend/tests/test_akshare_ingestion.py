"""AKShare ingestion: per-producer safe wrapping, batch write, FX derivation."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import select, text

from aether.ingestion import akshare_
from aether.models.prices import Price
from aether.storage import db as db_module
from scripts.seed_assets import seed_assets


@pytest_asyncio.fixture
async def prices_clean() -> None:
    async with db_module.session_scope() as session:
        await session.execute(text("TRUNCATE TABLE prices, assets RESTART IDENTITY CASCADE"))
        await session.commit()
        await seed_assets(session)


# ---------- tick orchestration ------------------------------------------

@pytest.mark.usefixtures("prices_clean")
async def test_tick_writes_all_successful_producers():
    ts = datetime(2026, 6, 10, tzinfo=UTC)
    producers = {
        "shcomp": lambda: [akshare_.Quote("SHCOMP", ts, Decimal("4010"))],
        "hsi": lambda: [akshare_.Quote("HSI", ts, Decimal("24565"))],
        "fx": lambda: [
            akshare_.Quote("USD/JPY", ts, Decimal("160.38")),
            akshare_.Quote("EUR/USD", ts, Decimal("1.155")),
        ],
    }
    with patch.object(akshare_, "PRODUCERS", producers):
        result = await akshare_.tick()
    assert sorted(result["shcomp"]) == ["SHCOMP"]
    assert sorted(result["fx"]) == ["EUR/USD", "USD/JPY"]

    async with db_module.session_scope() as session:
        ids = {r.asset_id for r in (await session.scalars(select(Price))).all()}
    assert ids == {"SHCOMP", "HSI", "USD/JPY", "EUR/USD"}


@pytest.mark.usefixtures("prices_clean")
async def test_tick_isolates_per_producer_failure():
    ts = datetime(2026, 6, 10, tzinfo=UTC)

    def boom():
        raise RuntimeError("simulated upstream blip")

    producers = {
        "shcomp": lambda: [akshare_.Quote("SHCOMP", ts, Decimal("4010"))],
        "hsi": boom,
        "fx_em": lambda: [akshare_.Quote("USD/CNH", ts, Decimal("7.10"))],
    }
    with patch.object(akshare_, "PRODUCERS", producers):
        result = await akshare_.tick()
    assert result["shcomp"] == ["SHCOMP"]
    assert result["hsi"] == []
    assert result["fx_em"] == ["USD/CNH"]

    async with db_module.session_scope() as session:
        ids = {r.asset_id for r in (await session.scalars(select(Price))).all()}
    assert ids == {"SHCOMP", "USD/CNH"}


@pytest.mark.usefixtures("prices_clean")
async def test_tick_handles_empty_producers():
    producers = {name: (lambda: []) for name in akshare_.PRODUCERS}
    with patch.object(akshare_, "PRODUCERS", producers):
        result = await akshare_.tick()
    assert all(v == [] for v in result.values())


# ---------- FX majors producer ------------------------------------------

def _fake_fx_pair_df() -> pd.DataFrame:
    """Mimic Sina fx_pair_quote() output."""
    return pd.DataFrame(
        [
            ("AUD/USD", 0.70181, 0.70181),
            ("EUR/JPY", 185.30600, 185.30700),
            ("EUR/USD", 1.15541, 1.15543),
            ("GBP/USD", 1.33906, 1.33909),
            ("USD/CAD", 1.39370, 1.39373),
            ("USD/CHF", 0.79831, 0.79833),
            ("USD/JPY", 160.38000, 160.38100),
            ("NZD/USD", 0.58147, 0.58147),
            ("EUR/GBP", 0.86285, 0.86286),
            ("USD/HKD", 7.83636, 7.83640),  # not in our asset list
        ],
        columns=["货币对", "买报价", "卖报价"],
    )


def test_fetch_fx_majors_returns_8_direct_and_aud_jpy_derived():
    with patch.object(akshare_.ak, "fx_pair_quote", return_value=_fake_fx_pair_df()):
        quotes = akshare_._fetch_fx_majors()

    by_id = {q.asset_id: q.price for q in quotes}
    # 8 direct
    for direct in ("USD/JPY", "EUR/USD", "GBP/USD", "USD/CHF",
                   "USD/CAD", "NZD/USD", "EUR/GBP", "EUR/JPY"):
        assert direct in by_id, f"missing {direct}"
    # AUD/JPY = AUD/USD × USD/JPY (multiply the mids — match the actual code path).
    assert "AUD/JPY" in by_id
    expected = akshare_._mid(0.70181, 0.70181) * akshare_._mid(160.38000, 160.38100)
    assert by_id["AUD/JPY"] == expected
    # USD/HKD is in Sina but we don't list it as an asset — should be skipped
    assert "USD/HKD" not in by_id


def test_fetch_fx_majors_returns_empty_when_upstream_fails():
    with patch.object(akshare_.ak, "fx_pair_quote", return_value=pd.DataFrame()):
        assert akshare_._fetch_fx_majors() == []


# ---------- FX EM producer ----------------------------------------------

def _fake_fx_spot_df() -> pd.DataFrame:
    """Mimic Sina fx_spot_quote() output — CNY-denominated pairs."""
    return pd.DataFrame(
        [
            ("USD/CNY", 7.10, 7.10),
            ("CNY/SAR", 0.5285, 0.5285),
            ("CNY/AED", 0.5174, 0.5174),
            ("CNY/KRW", 191.20, 191.20),
            ("CNY/TRY", 4.55, 4.55),
            ("CNY/ZAR", 2.50, 2.50),
            ("CNY/THB", 4.85, 4.85),  # not in our asset list
        ],
        columns=["货币对", "买报价", "卖报价"],
    )


def test_fetch_fx_em_proxies_usdcnh_and_derives_via_cny_cross():
    with patch.object(akshare_.ak, "fx_spot_quote", return_value=_fake_fx_spot_df()):
        quotes = akshare_._fetch_fx_em()

    by_id = {q.asset_id: q.price for q in quotes}
    # USD/CNH proxied by USD/CNY mid (7.10)
    assert by_id["USD/CNH"] == Decimal("7.10")
    # Derived: USD/<X> = USD/CNY × CNY/<X>
    assert by_id["USD/SAR"] == Decimal("7.10") * Decimal("0.5285")
    assert by_id["USD/AED"] == Decimal("7.10") * Decimal("0.5174")
    assert by_id["USD/KRW"] == Decimal("7.10") * Decimal("191.20")
    assert by_id["USD/TRY"] == Decimal("7.10") * Decimal("4.55")
    assert by_id["USD/ZAR"] == Decimal("7.10") * Decimal("2.50")


def test_fetch_fx_em_returns_empty_when_usdcny_missing():
    df = pd.DataFrame(
        [("CNY/SAR", 0.5, 0.5)],
        columns=["货币对", "买报价", "卖报价"],
    )
    with patch.object(akshare_.ak, "fx_spot_quote", return_value=df):
        assert akshare_._fetch_fx_em() == []


# ---------- NaN quotes (weekend / market closed) -------------------------

def _fake_fx_pair_df_all_nan() -> pd.DataFrame:
    """What Sina actually returns while the FX market is closed."""
    return pd.DataFrame(
        [
            ("AUD/USD", float("nan"), float("nan")),
            ("USD/JPY", float("nan"), float("nan")),
            ("EUR/USD", float("nan"), float("nan")),
        ],
        columns=["货币对", "买报价", "卖报价"],
    )


def test_fx_majors_drops_nan_quotes_instead_of_writing_them():
    # float("nan") passes float() without raising, so the parse guard alone
    # let NaN through and it reached the DB as Decimal('NaN').
    with patch.object(
        akshare_.ak, "fx_pair_quote", return_value=_fake_fx_pair_df_all_nan()
    ):
        assert akshare_._fetch_fx_majors() == []


def test_fx_majors_does_not_derive_crosses_from_a_nan_leg():
    df = pd.DataFrame(
        [
            ("AUD/USD", 0.70181, 0.70185),
            ("USD/JPY", float("nan"), float("nan")),
        ],
        columns=["货币对", "买报价", "卖报价"],
    )
    with patch.object(akshare_.ak, "fx_pair_quote", return_value=df):
        quotes = akshare_._fetch_fx_majors()

    assert [q.asset_id for q in quotes] == []


@pytest.mark.usefixtures("prices_clean")
async def test_write_quotes_drops_non_finite_prices():
    ts = datetime.now(UTC)
    quotes = [
        akshare_.Quote("BTC", ts, Decimal("61000")),
        akshare_.Quote("USD/JPY", ts, Decimal("NaN")),
        akshare_.Quote("EUR/USD", ts, Decimal("Infinity")),
    ]
    written = await akshare_._write_quotes(quotes)

    assert written == 1
    async with db_module.session_scope() as session:
        rows = (await session.execute(
            text("SELECT asset_id FROM prices WHERE ts = :ts"), {"ts": ts}
        )).scalars().all()
    assert sorted(rows) == ["BTC"]
