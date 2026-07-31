"""Smoke test: the FastAPI app boots and the health endpoint responds.

Proves the CI pipeline can import the whole application (config, routers, models,
services) and serve a request — without needing a real database.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "1.0.0"}


def test_api_v2_root_ok():
    resp = client.get("/api/v2")
    assert resp.status_code == 200


def test_unknown_route_404():
    resp = client.get("/definitely-not-a-real-route")
    assert resp.status_code == 404
