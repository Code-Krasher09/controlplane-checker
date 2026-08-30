"""FastAPI Application Entrypoint for ControlPlane Checker Round 2 Prototype."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_router
from app.api.v1.health import health_check
from app.api.v1.inspect import inspect_request
from app.api.v1.preflight import evaluate_preflight
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifespan context."""
    settings = get_settings()
    if settings.debug:
        print(f"Starting {settings.app_name} v{settings.app_version} [{settings.app_env}]")
    try:
        from app.persistence.database import init_db
        await init_db()
    except Exception as e:
        if settings.debug:
            print(f"Database init info: {e}")
    yield
    if settings.debug:
        print(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ControlPlane Checker",
        description=(
            "Model-Agnostic, Policy-Aware, Risk-Adaptive Runtime Control Plane "
            "for Enterprise AI (Round 2 Prototype)"
        ),
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount versioned API routers (/api/v1/...)
    app.include_router(api_router, prefix="/api")

    # Root convenience mappings (/health, /preflight, /inspect)
    app.add_api_route("/health", health_check, methods=["GET"], tags=["health"])
    app.add_api_route("/preflight", evaluate_preflight, methods=["POST"], tags=["preflight"])
    app.add_api_route("/inspect", inspect_request, methods=["POST"], tags=["gateway"])

    # Mount built frontend if available
    import os
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
    if os.path.exists(dist_path):
        app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")

        @app.get("/ui", tags=["ui"])
        async def ui_index():
            return FileResponse(os.path.join(dist_path, "index.html"))

    @app.get("/", tags=["root"])
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "docs": "/docs",
            "health": "/health",
            "ui": "/ui",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
