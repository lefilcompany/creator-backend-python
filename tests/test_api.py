import pytest
from httpx import ASGITransport, AsyncClient

from creator.main import app


@pytest.mark.anyio
async def test_live_health_returns_contract_envelope() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["meta"]["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_reserved_route_returns_structured_error() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/images/generate")

    assert response.status_code == 501
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"
    assert response.json()["meta"]["request_id"]
