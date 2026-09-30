import pytest

from app.config import get_settings
from tests.conftest import World


def test_upload_download_delete(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}/files"
    fde = world.a.fde
    r = fde.post(
        base,
        files={"file": ("../../evil name.csv", b"a,b\n1,2", "text/csv")},
        data={"owner_type": "dev_task", "owner_id": world.a.ids["task_id"]},
    )
    assert r.status_code == 201, r.text
    meta = r.json()
    assert meta["filename"] == "evil name.csv" and meta["size"] == 7
    assert (get_settings().data_dir / "files" / world.a.tenant_id).is_dir()
    d = world.a.client_user.get(f"{base}/{meta['id']}/download")
    assert d.status_code == 200 and d.content == b"a,b\n1,2"
    listed = fde.get(base, params={"owner_type": "dev_task", "owner_id": world.a.ids["task_id"]}).json()["items"]
    assert [f["id"] for f in listed] == [meta["id"]]
    assert fde.delete(f"{base}/{meta['id']}").status_code == 204
    assert fde.get(f"{base}/{meta['id']}").status_code == 404


def test_rejects_disallowed_extension(world: World) -> None:
    r = world.a.fde.post(f"/api/v1/t/{world.a.tenant_id}/files", files={"file": ("x.exe", b"MZ", "application/x")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "file_type_not_allowed"


def test_rejects_too_large(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    r = world.a.fde.post(f"/api/v1/t/{world.a.tenant_id}/files", files={"file": ("x.txt", b"x", "text/plain")})
    assert r.status_code == 413
