from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit.models import AuditLog
from tests.conftest import World


def test_tenant_crud_and_code_unique(world: World) -> None:
    admin = world.admin
    assert admin.post("/api/v1/admin/tenants", json={"name": "Dup", "code": "TA"}).status_code == 409
    r = admin.patch(f"/api/v1/admin/tenants/{world.a.tenant_id}", json={"status": "archived", "notes": "n"})
    assert r.status_code == 200 and r.json()["status"] == "archived"
    assert len(admin.get("/api/v1/admin/tenants").json()["items"]) == 2
    assert admin.get("/api/v1/admin/tenants/nope").status_code == 404


def test_pagination_cursor(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}/systems"
    for i in range(5):
        world.a.fde.post(base, json={"name": f"S{i}"})
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        page = world.a.fde.get(base, params=params).json()
        seen.extend(i["id"] for i in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 6
    assert world.a.fde.get(base, params={"cursor": "!!bad"}).status_code == 400


def test_engagement_and_system_crud(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}"
    fde = world.a.fde
    r = fde.patch(f"{base}/engagements/{world.a.ids['engagement_id']}", json={"status": "in_progress"})
    assert r.json()["status"] == "in_progress"
    sid = fde.post(f"{base}/systems", json={"name": "MES", "type": "MES", "hosting": "on_premise"}).json()["id"]
    assert fde.patch(f"{base}/systems/{sid}", json={"db_type": "MSSQL"}).json()["db_type"] == "MSSQL"
    assert fde.delete(f"{base}/systems/{sid}").status_code == 204
    assert fde.get(f"{base}/systems/{sid}").status_code == 404
    assert fde.post(f"{base}/systems", json={"name": "x", "type": "nonsense"}).status_code == 422


def test_error_format(world: World) -> None:
    r = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/systems/missing")
    assert r.json() == {"error": {"code": "not_found", "message": "errors.not_found"}}
    r = world.a.fde.post(f"/api/v1/t/{world.a.tenant_id}/systems", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_delete_tenant_purges_everything(world: World, db: Session) -> None:
    tid = world.b.tenant_id
    files_dir = get_settings().data_dir / "files" / tid
    assert files_dir.exists()
    assert world.admin.delete(f"/api/v1/admin/tenants/{tid}").status_code == 204
    assert not files_dir.exists()
    assert db.scalars(select(AuditLog).where(AuditLog.tenant_id == tid)).first() is None
    assert db.scalars(select(AuditLog).where(AuditLog.action == "tenant.delete")).first() is not None
    assert world.b.fde.get(f"/api/v1/t/{tid}/systems").status_code == 404
    assert world.b.client_user.get("/api/v1/auth/me").json()["tenants"] == []
    assert world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/systems").status_code == 200
    assert Path(get_settings().data_dir / "files" / world.a.tenant_id).exists()
