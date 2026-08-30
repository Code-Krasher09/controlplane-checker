"""Health check and diagnostic endpoints."""

from fastapi import APIRouter
from app.core.config import get_settings
from app.domain.models import HealthStatusResponse

router = APIRouter()


@router.get("/health", response_model=HealthStatusResponse)
async def health_check() -> HealthStatusResponse:
    """Return application health status, version, and component status."""
    settings = get_settings()
    return HealthStatusResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
        database="configured",
        redis="configured",
    )
