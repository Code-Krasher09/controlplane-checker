"""Pytest fixtures and configuration for testing."""

from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import Settings, get_settings
from app.main import create_app
from app.persistence.database import get_db_session
from app.persistence.models.base import Base


@pytest.fixture
def test_settings() -> Settings:
    """Provide isolated test settings."""
    return Settings(
        app_env="test",
        debug=True,
        database_url="sqlite+aiosqlite:///:memory:",
        model_provider="mock",
    )


@pytest.fixture
async def test_engine(test_settings: Settings):
    """Create in-memory SQLite async engine with foreign keys enabled."""
    engine = create_async_engine(
        test_settings.database_url or "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session for testing."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def async_client(test_settings: Settings, async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client for testing API endpoints."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db_session] = lambda: async_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
