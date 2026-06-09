"""Pytest configuration: point the engine at aether_test, reset tables per session."""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from aether.config import get_settings
from aether.storage import db as db_module


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bind_test_engine() -> AsyncIterator[None]:
    """Bind the global engine to the test DB for the entire session."""
    settings = get_settings()
    db_module.override_engine_for_tests(settings.test_database_url)
    try:
        yield
    finally:
        await db_module.dispose_engine()


@pytest_asyncio.fixture
async def clean_tables() -> AsyncIterator[None]:
    """Truncate region tables before a test that needs a known starting state."""
    async with db_module.session_scope() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE country_economic_memberships, economic_regions "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession scoped to a single test."""
    async with db_module.session_scope() as s:
        yield s
