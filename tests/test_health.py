import httpx
import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_health_returns_service_status() -> None:
    application = create_app()

    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Abstrivo Backend",
        "version": "0.1.0",
    }


@pytest.mark.asyncio
async def test_openapi_describes_health_endpoint() -> None:
    application = create_app()

    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
