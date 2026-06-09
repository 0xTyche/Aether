"""Seed the six P0 economic regions with their country memberships.

Idempotent: re-runs upsert; safe to invoke multiple times.

Usage:
    uv run python scripts/seed_economic_regions.py
    uv run python scripts/seed_economic_regions.py --test   # target aether_test DB
"""

import argparse
import asyncio
import sys
from typing import TypedDict

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aether.config import get_settings
from aether.models.regions import CountryEconomicMembership, EconomicRegion
from aether.storage import db as db_module


class RegionSpec(TypedDict):
    id: str
    label_zh: str
    label_en: str
    region_type: str
    central_bank: str | None
    members: list[str]


REGIONS: list[RegionSpec] = [
    {
        "id": "eurozone",
        "label_zh": "欧元区",
        "label_en": "Eurozone",
        "region_type": "monetary_union",
        "central_bank": "ECB",
        "members": [
            "DE", "FR", "IT", "ES", "NL", "BE", "AT", "PT", "FI", "IE",
            "GR", "LU", "CY", "MT", "SK", "SI", "EE", "LV", "LT", "HR",
        ],
    },
    {
        "id": "g7",
        "label_zh": "G7",
        "label_en": "G7",
        "region_type": "economic_bloc",
        "central_bank": None,
        "members": ["US", "JP", "DE", "GB", "FR", "IT", "CA"],
    },
    {
        "id": "g20",
        "label_zh": "G20",
        "label_en": "G20",
        "region_type": "economic_bloc",
        "central_bank": None,
        "members": [
            # G7
            "US", "JP", "DE", "GB", "FR", "IT", "CA",
            # rest of G20
            "CN", "IN", "BR", "RU", "AU", "KR", "ID", "MX", "TR", "SA", "ZA", "AR",
            # European Union (ISO 3166-1 exceptionally reserved)
            "EU",
        ],
    },
    {
        "id": "opec_plus",
        "label_zh": "OPEC+",
        "label_en": "OPEC+",
        "region_type": "commodity_alliance",
        "central_bank": None,
        "members": [
            # OPEC core
            "SA", "AE", "IQ", "IR", "KW", "VE", "NG", "DZ", "AO", "GQ", "LY", "CG", "GA",
            # OPEC+ partners
            "RU", "MX", "KZ", "OM", "AZ", "BH", "BN", "MY", "SD", "SS",
        ],
    },
    {
        "id": "brics",
        "label_zh": "BRICS",
        "label_en": "BRICS",
        "region_type": "economic_bloc",
        "central_bank": None,
        # Post-2024 expansion: original five + Iran, UAE, Egypt, Ethiopia.
        "members": ["BR", "RU", "IN", "CN", "ZA", "IR", "AE", "EG", "ET"],
    },
    {
        "id": "asean",
        "label_zh": "ASEAN",
        "label_en": "ASEAN",
        "region_type": "economic_bloc",
        "central_bank": None,
        "members": ["ID", "TH", "SG", "MY", "PH", "VN", "MM", "KH", "LA", "BN"],
    },
]


async def upsert_region(session: AsyncSession, spec: RegionSpec) -> None:
    region_stmt = pg_insert(EconomicRegion).values(
        id=spec["id"],
        label_zh=spec["label_zh"],
        label_en=spec["label_en"],
        region_type=spec["region_type"],
        central_bank=spec["central_bank"],
    )
    region_stmt = region_stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "label_zh": region_stmt.excluded.label_zh,
            "label_en": region_stmt.excluded.label_en,
            "region_type": region_stmt.excluded.region_type,
            "central_bank": region_stmt.excluded.central_bank,
        },
    )
    await session.execute(region_stmt)

    if spec["members"]:
        membership_rows = [
            {"country_iso": iso, "region_id": spec["id"]} for iso in spec["members"]
        ]
        membership_stmt = pg_insert(CountryEconomicMembership).values(membership_rows)
        membership_stmt = membership_stmt.on_conflict_do_nothing(
            index_elements=["country_iso", "region_id"],
        )
        await session.execute(membership_stmt)


async def seed_all(session: AsyncSession) -> int:
    """Upsert every region in REGIONS. Returns total membership rows written."""
    total = 0
    for spec in REGIONS:
        await upsert_region(session, spec)
        total += len(spec["members"])
    return total


async def main(*, use_test_db: bool) -> None:
    """CLI entry: builds its own engine then calls seed_all in a session."""
    settings = get_settings()
    url = settings.test_database_url if use_test_db else settings.database_url
    db_module.override_engine_for_tests(url)

    async with db_module.session_scope() as session:
        total = await seed_all(session)

    target = "aether_test" if use_test_db else "aether"
    print(f"seeded {len(REGIONS)} regions / {total} memberships into '{target}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--test",
        action="store_true",
        help="Target the aether_test database instead of aether.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(use_test_db=args.test))
    except Exception as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
