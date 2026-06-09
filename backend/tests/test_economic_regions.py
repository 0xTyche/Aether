"""Seed correctness checks for the six P0 economic regions."""

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aether.models.regions import CountryEconomicMembership, EconomicRegion
from aether.storage import db as db_module
from scripts.seed_economic_regions import REGIONS, seed_all


@pytest_asyncio.fixture
async def seeded(clean_tables: None) -> None:
    """Run seed_all against the already-bound test engine."""
    async with db_module.session_scope() as session:
        await seed_all(session)


@pytest.mark.usefixtures("seeded")
class TestSeed:
    async def test_six_regions(self, session: AsyncSession) -> None:
        total = await session.scalar(select(func.count()).select_from(EconomicRegion))
        assert total == 6

    async def test_total_membership_count(self, session: AsyncSession) -> None:
        total = await session.scalar(
            select(func.count()).select_from(CountryEconomicMembership)
        )
        expected = sum(len(r["members"]) for r in REGIONS)
        assert total == expected

    @pytest.mark.parametrize(
        ("region_id", "expected_count"),
        [
            ("eurozone", 20),
            ("g7", 7),
            ("g20", 20),
            ("opec_plus", 23),
            ("brics", 9),
            ("asean", 10),
        ],
    )
    async def test_region_member_count(
        self, session: AsyncSession, region_id: str, expected_count: int
    ) -> None:
        count = await session.scalar(
            select(func.count())
            .select_from(CountryEconomicMembership)
            .where(CountryEconomicMembership.region_id == region_id)
        )
        assert count == expected_count

    async def test_g7_subset_of_g20(self, session: AsyncSession) -> None:
        g7 = set(
            (
                await session.scalars(
                    select(CountryEconomicMembership.country_iso).where(
                        CountryEconomicMembership.region_id == "g7"
                    )
                )
            ).all()
        )
        g20 = set(
            (
                await session.scalars(
                    select(CountryEconomicMembership.country_iso).where(
                        CountryEconomicMembership.region_id == "g20"
                    )
                )
            ).all()
        )
        assert g7.issubset(g20)

    @pytest.mark.parametrize(
        ("region_id", "must_have"),
        [
            ("eurozone", "DE"),
            ("eurozone", "HR"),
            ("g7", "JP"),
            ("opec_plus", "SA"),
            ("opec_plus", "RU"),
            ("brics", "CN"),
            ("brics", "IR"),
            ("asean", "VN"),
        ],
    )
    async def test_region_contains_key_member(
        self, session: AsyncSession, region_id: str, must_have: str
    ) -> None:
        row = await session.scalar(
            select(CountryEconomicMembership).where(
                CountryEconomicMembership.region_id == region_id,
                CountryEconomicMembership.country_iso == must_have,
            )
        )
        assert row is not None, f"{region_id} should include {must_have}"

    async def test_seed_is_idempotent(self) -> None:
        """Re-seeding must not raise nor duplicate rows."""
        async with db_module.session_scope() as s:
            await seed_all(s)
            await seed_all(s)

        async with db_module.session_scope() as s:
            total = await s.scalar(
                select(func.count()).select_from(CountryEconomicMembership)
            )
        assert total == sum(len(r["members"]) for r in REGIONS)
