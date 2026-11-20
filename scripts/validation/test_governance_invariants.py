"""Governance, Contract, Security & Architecture Invariant Test Suite.

Owned by Member 01 (Mishael). Verifies:
1. Strict default-deny contracts reject secrets, raw logs, IPs, hostnames, and non-UTC timestamps.
2. Docker Compose enforces physical network separation (collector cannot reach postgres on saas-internal).
3. Ownership boundaries strictly isolate Sherwin, Praveen, Darain, and Mishael.
4. Synthetic baseline stream generator produces >= 8 baseline points + anomaly spike cleanly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "audit"))
sys.path.insert(0, str(REPO_ROOT / "simulator" / "adapters"))

from check_ownership import is_path_owned  # noqa: E402
from check_secrets import scan_repository  # noqa: E402
from stream_generator import generate_baseline_series, load_static_fixtures  # noqa: E402
from verify_contracts import verify_all as verify_contracts  # noqa: E402


def test_all_contracts_and_adversarial_rejections_pass() -> None:
    ok, errors = verify_contracts()
    assert ok, f"Contract verification failed: {errors}"


def test_secret_scan_clean() -> None:
    ok, findings = scan_repository()
    assert ok, f"Secret scan findings: {findings}"


def test_docker_compose_network_isolation() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    pg_nets = set(services["postgres"]["networks"])
    collector_nets = set(services["collector"]["networks"])
    backend_nets = set(services["backend"]["networks"])

    assert "saas-internal" in pg_nets
    assert "saas-internal" not in collector_nets, "SECURITY VIOLATION: collector must NOT share postgres network"
    assert "ingest-boundary" in collector_nets
    assert "ingest-boundary" in backend_nets


def test_ownership_boundaries_enforced() -> None:
    assert is_path_owned("sherwin", "collector/src/aegis_collector/main.py")
    assert not is_path_owned("sherwin", "backend/app/main.py")
    assert not is_path_owned("sherwin", "contracts/metadata.schema.json")

    assert is_path_owned("praveen", "backend/app/main.py")
    assert not is_path_owned("praveen", "collector/src/aegis_collector/main.py")

    assert is_path_owned("darain", "frontend/src/App.tsx")
    assert not is_path_owned("darain", "backend/app/main.py")

    assert is_path_owned("mishael", "contracts/metadata.schema.json")
    assert is_path_owned("mishael", "docs/ARCHITECTURE.md")
    assert is_path_owned("mishael", ".github/workflows/ci.yml")
    assert is_path_owned("mishael", ".env.example")
    assert not is_path_owned("mishael", "collector/src/aegis_collector/main.py")


def test_simulator_fixtures_and_baseline_generator() -> None:
    fixtures = load_static_fixtures()
    assert len(fixtures) >= 8

    series = generate_baseline_series(count=10, include_spike=True)
    assert len(series) == 11
    assert series[-1]["metric_value"] > 90.0
    assert all(ev["event_time_utc"].endswith("Z") for ev in series)
