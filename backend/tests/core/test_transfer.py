import io
import json
import zipfile

from sqlalchemy.orm import Session

from tests.conftest import World, login, make_user


def test_export_import_roundtrip(world: World, db: Session) -> None:
    bundle = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/export").content
    r = world.admin.post(
        "/api/v1/admin/tenants/import",
        files={"file": ("a.zip", bundle, "application/zip")},
        data={"code": "TA-COPY", "name": "Copy of A"},
    )
    assert r.status_code == 201, r.text
    new_tid = r.json()["id"]
    assert new_tid != world.a.tenant_id
    make_user(db, "copy@luda.test", "fde", tenant_ids=[new_tid])
    c = login("copy@luda.test")
    base = f"/api/v1/t/{new_tid}"
    instances = c.get(f"{base}/agenthub/instances").json()["items"]
    assert len(instances) == 1
    inst = instances[0]
    assert inst["id"] != world.a.ids["instance_id"]
    systems = c.get(f"{base}/systems").json()["items"]
    assert inst["system_ids"] == [systems[0]["id"]]
    assert inst["template_ref"]["asset_id"] == world.template["asset_id"]
    files = {f["filename"]: f for f in c.get(f"{base}/files").json()["items"]}
    assert c.get(f"{base}/files/{files['note-TA.txt']['id']}/download").content == b"secret of TA"
    tasks = c.get(f"{base}/devtracker/projects/{inst['dev_project_id']}/tasks").json()["items"]
    assert tasks[0]["title"] == "Task TA"
    original = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/systems").json()["items"]
    assert len(original) == 1


def test_import_rejects_bad_bundles(world: World) -> None:
    def post(data: bytes, code: str = "NEW") -> int:
        return world.admin.post(
            "/api/v1/admin/tenants/import", files={"file": ("x.zip", data, "application/zip")}, data={"code": code}
        ).status_code

    assert post(b"not a zip") == 400
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"kind": "tenant_export", "schema_version": 9}))
    assert post(buf.getvalue()) == 400
    bundle = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/export").content
    assert post(bundle, code="TB") == 409
