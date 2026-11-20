"""AegisOps cross-module smoke test harness.

Verifies:
1. Shared JSON schemas and OpenAPI snapshot pass strict validation.
2. Shared simulator fixtures & scenario definitions load cleanly.
3. Collector FastAPI inspection app loads and exposes /health.
4. SaaS Backend FastAPI app loads and exposes /health.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "audit"))
sys.path.insert(0, str(REPO_ROOT / "collector" / "src"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from verify_contracts import verify_all as verify_contracts  # noqa: E402


def main() -> int:
    ok, errs = verify_contracts()
    if not ok:
        print(f"[FAIL] Contracts invalid: {errs}")
        return 1

    fixtures_path = REPO_ROOT / "simulator" / "fixtures" / "sample_raw_events.json"
    scenarios_path = REPO_ROOT / "simulator" / "scenarios" / "scenarios.json"
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    assert len(fixtures.get("events", [])) >= 8, "Expected at least 8 synthetic fixture events"
    assert len(scenarios.get("scenarios", [])) == 8, "Expected all 8 official live validation scenarios"

    from aegis_collector.main import app as collector_app  # noqa: E402
    from aegis_collector.main import health as collector_health  # noqa: E402
    from app.main import app as backend_app  # noqa: E402
    from app.main import health as backend_health  # noqa: E402

    col_body = collector_health()
    assert col_body.get("status") == "ok"
    assert "/health" in {getattr(r, "path", None) for r in collector_app.routes}

    be_body = backend_health()
    assert be_body.get("status") == "ok"
    assert "/health" in {getattr(r, "path", None) for r in backend_app.routes}

    print(
        "[PASS] AegisOps smoke test passed: contracts valid, "
        f"{len(fixtures['events'])} fixtures & {len(scenarios['scenarios'])} scenarios loaded, "
        "collector /health=ok, backend /health=ok."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
