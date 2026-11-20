"""Baseline scaffold verification test for Tier 1 Collector."""

from aegis_collector.main import app, health


def test_collector_health_endpoint() -> None:
    body = health()
    assert body["status"] == "ok"
    assert body["service"] == "aegisops-collector"
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths
