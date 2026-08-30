"""Health and root endpoint verification tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test root status endpoint returns 200 and valid JSON metadata."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ControlPlane Checker"
    assert data["status"] == "online"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint_direct(async_client: AsyncClient):
    """Test /health root mapping."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "configured"
    assert data["redis"] == "configured"


@pytest.mark.asyncio
async def test_health_endpoint_v1(async_client: AsyncClient):
    """Test /api/v1/health API route."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.2.0"
