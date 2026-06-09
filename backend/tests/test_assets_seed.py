"""Asset seed sanity checks."""

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aether.models.assets import Asset
from aether.storage import db as db_module
from scripts.seed_assets import ALL_ASSETS, seed_assets


@pytest_asyncio.fixture
async def assets_seeded(session: AsyncSession) -> None:
    # Tests for assets share the test DB; truncate then seed.
    from sqlalchemy import text

    await session.execute(text("TRUNCATE TABLE assets RESTART IDENTITY CASCADE"))
    await session.commit()
    await seed_assets(session)
    await session.commit()


@pytest.mark.usefixtures("assets_seeded")
class TestAssetsSeed:
    async def test_total_count_is_75(self, session: AsyncSession) -> None:
        total = await session.scalar(select(func.count()).select_from(Asset))
        assert total == 75
        assert total == len(ALL_ASSETS)

    @pytest.mark.parametrize(
        ("asset_class", "expected"),
        [
            ("fx", 20),  # 10 majors + 5 gulf + 5 EM
            ("rate", 14),
            ("equity", 10),
            ("equity_index", 10),
            ("commodity", 8),
            ("crypto", 8),
            ("bond", 5),
        ],
    )
    async def test_class_count(
        self, session: AsyncSession, asset_class: str, expected: int
    ) -> None:
        n = await session.scalar(
            select(func.count())
            .select_from(Asset)
            .where(Asset.asset_class == asset_class)
        )
        assert n == expected, f"{asset_class} should have {expected}"

    async def test_no_duplicate_ids(self) -> None:
        ids = [a["id"] for a in ALL_ASSETS]
        assert len(set(ids)) == len(ids), "asset ids must be unique"

    @pytest.mark.parametrize(
        "asset_id",
        ["BTC", "ETH", "BNB", "SOL", "XRP", "USDT/USD", "ETH/BTC"],
    )
    async def test_crypto_has_binance_symbol(
        self, session: AsyncSession, asset_id: str
    ) -> None:
        a = await session.get(Asset, asset_id)
        assert a is not None
        assert a.binance_symbol, f"{asset_id} should have a binance_symbol"

    async def test_us10y_has_fred_series(self, session: AsyncSession) -> None:
        a = await session.get(Asset, "US10Y")
        assert a is not None
        assert a.fred_series == "DGS10"

    async def test_gulf_currencies_present(self, session: AsyncSession) -> None:
        for iso in ("USD/SAR", "USD/AED", "USD/QAR", "USD/KWD", "USD/OMR"):
            assert await session.get(Asset, iso) is not None, f"missing {iso}"

    async def test_seed_is_idempotent(self, session: AsyncSession) -> None:
        n1 = await seed_assets(session)
        n2 = await seed_assets(session)
        total = await session.scalar(select(func.count()).select_from(Asset))
        assert n1 == n2 == 75
        assert total == 75
