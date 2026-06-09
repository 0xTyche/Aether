"""Async SQLAlchemy engine + session factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aether.config import get_settings


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _build_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


def get_engine() -> AsyncEngine:
    global _engine, _session_maker
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
        _session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        get_engine()
    assert _session_maker is not None
    return _session_maker


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager yielding a session with commit/rollback semantics."""
    maker = get_session_maker()
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None


def override_engine_for_tests(url: str) -> AsyncEngine:
    """Replace the global engine for the test suite. Returns the new engine."""
    global _engine, _session_maker
    _engine = _build_engine(url)
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine
