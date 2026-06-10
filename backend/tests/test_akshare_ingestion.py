"""AKShare ingestion: per-fetcher safe wrapping, write batch."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

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


@pytest.mark.usefixtures("prices_clean")
async def test_tick_writes_all_successful_fetchers():
    ts = datetime(2026, 6, 10, tzinfo=UTC)
    fake = {
        "SHCOMP": akshare_.Quote("SHCOMP", ts, Decimal("4010.03")),
        "HSI":    akshare_.Quote("HSI",    ts, Decimal("24565.90")),
        "USD/CNH":akshare_.Quote("USD/CNH",ts, Decimal("7.10")),
    }
    fetchers = {k: (lambda v=v: v) for k, v in fake.items()}
    with patch.object(akshare_, "FETCHERS", fetchers):
        result = await akshare_.tick()
    assert result == {"SHCOMP": True, "HSI": True, "USD/CNH": True}

    async with db_module.session_scope() as session:
        rows = (await session.scalars(select(Price))).all()
    assert {r.asset_id for r in rows} == {"SHCOMP", "HSI", "USD/CNH"}


@pytest.mark.usefixtures("prices_clean")
async def test_tick_isolates_per_fetcher_failure():
    ts = datetime(2026, 6, 10, tzinfo=UTC)
    def boom():
        raise RuntimeError("simulated network blip")

    fetchers = {
        "SHCOMP": lambda: akshare_.Quote("SHCOMP", ts, Decimal("4010")),
        "HSI": boom,
        "USD/CNH": lambda: akshare_.Quote("USD/CNH", ts, Decimal("7.1")),
    }
    with patch.object(akshare_, "FETCHERS", fetchers):
        result = await akshare_.tick()
    assert result["SHCOMP"] is True
    assert result["HSI"] is False
    assert result["USD/CNH"] is True

    async with db_module.session_scope() as session:
        ids = {r.asset_id for r in (await session.scalars(select(Price))).all()}
    assert ids == {"SHCOMP", "USD/CNH"}


@pytest.mark.usefixtures("prices_clean")
async def test_tick_returns_all_false_when_all_fetchers_return_none():
    fetchers = {k: (lambda: None) for k in akshare_.FETCHERS}
    with patch.object(akshare_, "FETCHERS", fetchers):
        result = await akshare_.tick()
    assert all(v is False for v in result.values())
    async with db_module.session_scope() as session:
        n = (await session.scalars(select(Price))).all()
    assert len(n) == 0
