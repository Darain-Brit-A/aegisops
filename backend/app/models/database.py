"""Database engine, session factory, and deterministic multi-tenant dev seed."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import BackendConfig
from app.models.entities import Base, Collector, Environment, OperatorCredential, Tenant


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        if ":memory:" in database_url:
            return create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        db_file = database_url.replace("sqlite:///", "", 1)
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


class DatabaseManager:
    def __init__(self, config: BackendConfig | None = None) -> None:
        self.config = config or BackendConfig.from_env()
        self.engine = build_engine(self.config.database_url)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def init_db_and_seed(self) -> None:
        Base.metadata.create_all(bind=self.engine)
        with self.session_factory() as db:
            self._seed_tenant(
                db,
                tenant_id=self.config.tenant_a_id,
                name="Acme Enterprise Operations",
                region_id="ap-south-1",
                environment_id="env-blr-dc1",
                env_label="Bengaluru Primary DC",
                collector_id=self.config.tenant_a_collector_id,
                collector_token=self.config.tenant_a_collector_token,
                operator_id="op-acme-sre",
                operator_token=self.config.tenant_a_operator_token,
            )
            self._seed_tenant(
                db,
                tenant_id=self.config.tenant_b_id,
                name="Globex Cloud Infrastructure",
                region_id="eu-central-1",
                environment_id="env-fra-cloud1",
                env_label="Frankfurt Regulated Cloud",
                collector_id=self.config.tenant_b_collector_id,
                collector_token=self.config.tenant_b_collector_token,
                operator_id="op-globex-sre",
                operator_token=self.config.tenant_b_operator_token,
            )
            db.commit()

    def _seed_tenant(
        self,
        db: Session,
        *,
        tenant_id: str,
        name: str,
        region_id: str,
        environment_id: str,
        env_label: str,
        collector_id: str,
        collector_token: str,
        operator_id: str,
        operator_token: str,
    ) -> None:
        if db.get(Tenant, tenant_id) is None:
            db.add(Tenant(tenant_id=tenant_id, name=name, region_id=region_id))
            db.flush()

        if db.get(Environment, environment_id) is None:
            db.add(
                Environment(
                    environment_id=environment_id,
                    tenant_id=tenant_id,
                    region_id=region_id,
                    display_label=env_label,
                )
            )
            db.flush()

        if db.get(Collector, collector_id) is None:
            db.add(
                Collector(
                    collector_id=collector_id,
                    tenant_id=tenant_id,
                    environment_id=environment_id,
                    region_id=region_id,
                    token_hash=hash_token(collector_token),
                    policy_version=self.config.policy_version,
                )
            )

        op_hash = hash_token(operator_token)
        existing_op = db.scalar(select(OperatorCredential).where(OperatorCredential.token_hash == op_hash))
        if existing_op is None:
            db.add(
                OperatorCredential(
                    tenant_id=tenant_id,
                    operator_id=operator_id,
                    role="admin",
                    token_hash=op_hash,
                )
            )

    def get_session(self) -> Generator[Session, None, None]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()
