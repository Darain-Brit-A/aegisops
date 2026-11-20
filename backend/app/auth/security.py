"""Server-bound collector and operator authentication & tenant authorization."""

from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import hash_token
from app.models.entities import AuditEvent, Collector, OperatorCredential


@dataclass(frozen=True)
class AuthenticatedOperator:
    tenant_id: str
    operator_id: str
    role: str


def authenticate_collector_token(db: Session, token: str | None) -> Collector:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "MISSING_COLLECTOR_TOKEN", "message": "X-Collector-Token header is required."},
        )
    collector = db.scalar(select(Collector).where(Collector.token_hash == hash_token(token)))
    if collector is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_COLLECTOR_TOKEN", "message": "Collector credential is not valid."},
        )
    return collector


def verify_collector_binding(
    db: Session,
    collector: Collector,
    declared_tenant_id: str,
    declared_collector_id: str,
) -> None:
    """Enforce server-bound tenant & collector identity — never trust caller-supplied tenant_id alone."""
    if declared_tenant_id != collector.tenant_id or declared_collector_id != collector.collector_id:
        db.add(
            AuditEvent(
                tenant_id=collector.tenant_id,
                actor=collector.collector_id,
                action="TENANT_BINDING_VIOLATION",
                target_id=declared_tenant_id,
                details_json=json.dumps(
                    {
                        "auth_tenant_id": collector.tenant_id,
                        "declared_tenant_id": declared_tenant_id,
                        "auth_collector_id": collector.collector_id,
                        "declared_collector_id": declared_collector_id,
                    }
                ),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "TENANT_BINDING_MISMATCH",
                "message": "Declared tenant_id or collector_id does not match authenticated collector credential.",
            },
        )


def authenticate_operator_token(db: Session, token: str | None) -> AuthenticatedOperator:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "MISSING_TENANT_TOKEN", "message": "X-Tenant-Token header is required."},
        )
    cred = db.scalar(select(OperatorCredential).where(OperatorCredential.token_hash == hash_token(token)))
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_TENANT_TOKEN", "message": "Operator credential is not valid."},
        )
    return AuthenticatedOperator(tenant_id=cred.tenant_id, operator_id=cred.operator_id, role=cred.role)
