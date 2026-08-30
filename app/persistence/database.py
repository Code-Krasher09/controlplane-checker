"""Database engine, session management, and lifecycle hooks."""

from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import Settings, get_settings
from .models.base import Base

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_engine = None
_sync_session_factory = None


def get_async_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return or create singleton async SQLAlchemy engine."""
    global _async_engine
    if _async_engine is None:
        cfg = settings or get_settings()
        url = cfg.async_database_url

        # Configure connection arguments depending on dialect
        connect_args = {}
        if "sqlite" in url:
            connect_args = {"check_same_thread": False}

        _async_engine = create_async_engine(
            url,
            echo=cfg.debug and cfg.app_env == "development",
            future=True,
            connect_args=connect_args,
        )
    return _async_engine


def get_async_sessionmaker(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """Return or create singleton async sessionmaker factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine(settings)
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db_context(settings: Settings | None = None) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for standalone CLI scripts and evaluators."""
    session_factory = get_async_sessionmaker(settings)
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_sync_engine(settings: Settings | None = None):
    """Return or create sync SQLAlchemy engine."""
    global _sync_engine
    if _sync_engine is None:
        cfg = settings or get_settings()
        url = cfg.sync_database_url
        connect_args = {}
        if "sqlite" in url:
            connect_args = {"check_same_thread": False}
        _sync_engine = create_engine(
            url,
            echo=cfg.debug and cfg.app_env == "development",
            connect_args=connect_args,
        )
    return _sync_engine


def get_sync_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    """Provide a synchronous session for seed scripts and management commands."""
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = get_sync_engine(settings)
        _sync_session_factory = sessionmaker(bind=engine, autoflush=False)

    session = _sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Create all schema tables directly and seed default applications."""
    eng = engine or get_async_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        session_factory = get_async_sessionmaker()
        async with session_factory() as session:
            from .seed import seed_database_async
            await seed_database_async(session)
    except Exception:
        pass


async def drop_db(engine: AsyncEngine | None = None) -> None:
    """Drop all schema tables directly (for testing teardown)."""
    eng = engine or get_async_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_db() -> None:
    """Dispose of engine connections."""
    global _async_engine, _async_session_factory, _sync_engine, _sync_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None
