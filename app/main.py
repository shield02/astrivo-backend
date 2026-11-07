from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title=runtime_settings.app_name,
        version=runtime_settings.app_version,
        description="Document intelligence API for commercial real estate due diligence.",
    )

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": runtime_settings.app_name,
            "version": runtime_settings.app_version,
        }

    application.include_router(v1_router, prefix=runtime_settings.api_prefix)
    return application


app = create_app()
