PYTHON ?= python
ACTOR ?= mishael

.PHONY: help bootstrap hooks verify-contracts check-secrets check-ownership audit report test test-collector test-backend test-frontend smoke gate up down

help:
	@echo "AegisOps Makefile Targets:"
	@echo "  make hooks            - Install local git pre-commit and pre-push audit hooks"
	@echo "  make verify-contracts - Validate JSON schemas and OpenAPI snapshot"
	@echo "  make check-secrets    - Scan tracked files for accidental secrets or local DBs"
	@echo "  make check-ownership  - Verify modified files match ACTOR ownership (ACTOR=$(ACTOR))"
	@echo "  make audit            - Run full local engineering audit for ACTOR=$(ACTOR)"
	@echo "  make report           - Generate audit summary from audit/activity.jsonl"
	@echo "  make test             - Run collector and backend pytest suites"
	@echo "  make smoke            - Run contract + service scaffold smoke tests"
	@echo "  make gate             - Run full integration gate"
	@echo "  make up / down        - Start / stop Docker Compose stack"

hooks:
	$(PYTHON) scripts/bootstrap/install_hooks.py

verify-contracts:
	$(PYTHON) scripts/audit/verify_contracts.py

check-secrets:
	$(PYTHON) scripts/audit/check_secrets.py

check-ownership:
	$(PYTHON) scripts/audit/check_ownership.py --actor $(ACTOR)

audit:
	$(PYTHON) scripts/audit/check.py --actor $(ACTOR) --action manual_audit

report:
	$(PYTHON) scripts/audit/report.py

test-collector:
	pytest collector/tests -v

test-backend:
	pytest backend/tests -v

test-frontend:
	cd frontend && npm test -- --run

test: test-collector test-backend

smoke:
	$(PYTHON) scripts/validation/smoke_test.py

gate:
	$(PYTHON) scripts/audit/integration_gate.py

up:
	docker compose up --build

down:
	docker compose down
