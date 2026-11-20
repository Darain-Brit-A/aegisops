"""Baseline scaffold verification test for Tier 2 SaaS Backend."""

from app.main import app, health


def test_backend_health_endpoint() -> None:
    body = health()
    assert body["status"] == "ok"
    assert body["service"] == "aegisops-backend"
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths
