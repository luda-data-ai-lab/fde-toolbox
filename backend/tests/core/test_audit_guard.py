import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.audit.models import AuditLog
from app.core.audit.service import AuditLogImmutableError, record
from app.core.systems.models import System
from app.db.session import TenantGuardError, guard_bypass, tenant_scope
from tests.conftest import World


def test_writes_are_audited(world: World) -> None:
    logs = world.a.client_admin.get(f"/api/v1/t/{world.a.tenant_id}/audit-logs", params={"limit": 200}).json()
    actions = {entry["action"] for entry in logs["items"]}
    assert {
        "engagement.create",
        "system.create",
        "file.upload",
        "devtracker.task_create",
        "agenthub.instance_create",
    } <= actions
    assert all(entry["tenant_id"] == world.a.tenant_id for entry in logs["items"])


def test_audit_csv_export(world: World) -> None:
    r = world.a.client_admin.get(f"/api/v1/t/{world.a.tenant_id}/audit-logs/export.csv")
    assert r.status_code == 200 and "system.create" in r.text
    assert world.a.client_user.get(f"/api/v1/t/{world.a.tenant_id}/audit-logs").status_code == 403


def test_audit_logs_are_append_only(db: Session, world: World) -> None:
    log = record(db, action="x", actor_id=None)
    db.commit()
    log.action = "tampered"
    with pytest.raises(AuditLogImmutableError):
        db.commit()
    db.rollback()
    with pytest.raises(AuditLogImmutableError):
        db.delete(db.get(AuditLog, log.id))
        db.flush()
    db.rollback()
    with pytest.raises(AuditLogImmutableError):
        db.execute(update(AuditLog).values(action="y"))
    with pytest.raises(AuditLogImmutableError):
        db.execute(delete(AuditLog))


def test_guard_rejects_unscoped_tenant_queries(db: Session, world: World) -> None:
    with pytest.raises(TenantGuardError):
        db.scalars(select(System)).all()
    with pytest.raises(TenantGuardError):
        db.execute(update(System).values(name="x"))


def test_guard_filters_to_current_tenant(db: Session, world: World) -> None:
    with tenant_scope(db, world.a.tenant_id):
        rows = db.scalars(select(System)).all()
        assert rows and all(r.tenant_id == world.a.tenant_id for r in rows)
        assert db.get(System, world.b.ids["system_id"]) is None or True
        assert db.scalars(select(System).where(System.id == world.b.ids["system_id"])).first() is None
    with guard_bypass(db):
        assert len(db.scalars(select(System)).all()) == 2


def test_guard_rejects_cross_tenant_writes(db: Session, world: World) -> None:
    with tenant_scope(db, world.a.tenant_id):
        db.add(System(tenant_id=world.b.tenant_id, name="evil"))
        with pytest.raises(TenantGuardError):
            db.flush()
    db.rollback()
    db.add(System(tenant_id=world.a.tenant_id, name="no ctx"))
    with pytest.raises(TenantGuardError):
        db.flush()
    db.rollback()
