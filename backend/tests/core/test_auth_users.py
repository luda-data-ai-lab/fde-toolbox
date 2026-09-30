from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit.models import AuditLog
from app.main import create_app
from tests.conftest import PASSWORD, World, login, make_user


def test_login_sets_httponly_cookie_and_me(admin: TestClient, db: Session) -> None:
    make_user(db, "x@luda.test", "luda_admin")
    c = TestClient(create_app())
    r = c.post("/api/v1/auth/login", json={"email": "X@luda.test ", "password": PASSWORD})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert c.get("/api/v1/auth/me").json()["user"]["email"] == "x@luda.test"
    assert "password_hash" not in r.text
    assert c.post("/api/v1/auth/logout").status_code == 204


def test_bad_login_is_audited(db: Session, engine: object) -> None:
    c = TestClient(create_app())
    r = c.post("/api/v1/auth/login", json={"email": "nobody@x.test", "password": "wrong-pass"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    assert db.scalars(select(AuditLog).where(AuditLog.action == "auth.login_failed")).first() is not None


def test_invalid_token_rejected(engine: object) -> None:
    c = TestClient(create_app())
    c.cookies.set("fde_session", "garbage")
    assert c.get("/api/v1/auth/me").status_code == 401


def test_inactive_user_cannot_login(admin: TestClient, db: Session) -> None:
    make_user(db, "gone@luda.test", "luda_admin")
    users = admin.get("/api/v1/admin/users").json()["items"]
    uid = next(u["id"] for u in users if u["email"] == "gone@luda.test")
    assert admin.patch(f"/api/v1/admin/users/{uid}", json={"is_active": False}).status_code == 200
    r = TestClient(create_app()).post("/api/v1/auth/login", json={"email": "gone@luda.test", "password": PASSWORD})
    assert r.status_code == 401


def test_admin_user_management(world: World) -> None:
    admin = world.admin
    r = admin.post(
        "/api/v1/admin/users",
        json={
            "email": "new-fde@luda.test",
            "name": "New",
            "role": "fde",
            "password": PASSWORD,
            "tenant_ids": [world.a.tenant_id],
        },
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    assert r.json()["tenant_ids"] == [world.a.tenant_id]
    assert (
        admin.post(
            "/api/v1/admin/users",
            json={
                "email": "new-fde@luda.test",
                "name": "Dup",
                "role": "fde",
                "password": PASSWORD,
            },
        ).status_code
        == 409
    )
    assert (
        admin.post(
            "/api/v1/admin/users",
            json={
                "email": "c@client.test",
                "name": "C",
                "role": "client_user",
                "password": PASSWORD,
            },
        ).status_code
        == 400
    )
    r = admin.patch(f"/api/v1/admin/users/{uid}", json={"tenant_ids": [world.b.tenant_id]})
    assert r.json()["tenant_ids"] == [world.b.tenant_id]
    fde = login("new-fde@luda.test")
    assert fde.get(f"/api/v1/t/{world.a.tenant_id}/systems").status_code == 404
    assert fde.get(f"/api/v1/t/{world.b.tenant_id}/systems").status_code == 200
    assert admin.get(f"/api/v1/admin/users/{uid}").status_code == 200
    assert admin.get("/api/v1/admin/users/missing").status_code == 404


def test_non_admin_cannot_use_admin_routes(world: World) -> None:
    for client in (world.a.fde, world.a.client_admin, world.a.client_user):
        assert client.get("/api/v1/admin/users").status_code == 403
        assert client.get("/api/v1/admin/tenants").status_code == 403
        assert client.post("/api/v1/admin/tenants", json={"name": "x", "code": "xx"}).status_code == 403
        assert client.get("/api/v1/admin/audit-logs").status_code == 403


def test_client_roles_are_read_only(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}"
    for client in (world.a.client_admin, world.a.client_user):
        assert client.post(f"{base}/systems", json={"name": "x"}).status_code == 403
        assert client.patch(f"{base}/systems/{world.a.ids['system_id']}", json={"name": "x"}).status_code == 403
        assert client.delete(f"{base}/engagements/{world.a.ids['engagement_id']}").status_code == 403
        assert client.get(f"{base}/systems").status_code == 200
