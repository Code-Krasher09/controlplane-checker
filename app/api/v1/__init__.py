"""API v1 routers."""

from fastapi import APIRouter
from .health import router as health_router
from .inspect import router as inspect_router
from .preflight import router as preflight_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router, tags=["health"])
api_router.include_router(preflight_router, tags=["preflight"])
api_router.include_router(inspect_router, tags=["gateway"])

__all__ = ["api_router"]
