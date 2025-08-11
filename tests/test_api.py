# tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest.mark.anyio
async def test_healthz_testing_mode():
    app = create_app(testing=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/healthz")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"

@pytest.mark.anyio
async def test_hello_path_works_without_kafka():
    app = create_app(testing=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/hello", json={"name": "Ada"})
            assert r.status_code == 200
            assert r.json()["ok"] is True