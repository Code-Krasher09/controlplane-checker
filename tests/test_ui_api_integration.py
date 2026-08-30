"""Integration tests verifying UI API endpoints and /inspect payload compatibility."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ActionType
from app.main import app
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    seed_database_async,
)


@pytest.fixture(autouse=True)
async def seed_data(async_session: AsyncSession):
    await seed_database_async(async_session)


@pytest.mark.asyncio
async def test_ui_health_endpoint(async_client: AsyncClient):
    """Verify GET /health returns online status and version for UI."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_ui_root_endpoint(async_client: AsyncClient):
    """Verify GET / returns root service information with /ui route."""
    resp = await async_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["docs"] == "/docs"
    assert data["ui"] == "/ui"


@pytest.mark.asyncio
async def test_ui_inspect_live_fast_path(async_client: AsyncClient):
    """Verify POST /inspect returns rich trace data compatible with LiveTraceView."""
    payload = {
        "application_id": str(CUSTOMER_SUPPORT_APP_ID),
        "prompt": "What is the return policy?",
        "response": "The retail policy allows returns within 30 days of delivery.",
    }
    resp = await async_client.post("/inspect", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "ALLOW"
    assert "timing_telemetry" in data
    assert "cost_telemetry" in data
    assert "risk_assessment" in data


@pytest.mark.asyncio
async def test_ui_inspect_pii_hard_block(async_client: AsyncClient):
    """Verify POST /inspect returns BLOCK on SSN input for UI."""
    payload = {
        "application_id": str(CUSTOMER_SUPPORT_APP_ID),
        "prompt": "Customer SSN is 111-22-3301. Please look up account.",
    }
    resp = await async_client.post("/inspect", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "BLOCK"
    assert len(data["policy_events"]) >= 1
    assert data["policy_events"][0]["event_type"] == "PII"
