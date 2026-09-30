import io
import json
import re
import zipfile

import pytest

from app.main import create_app
from tests.conftest import World

PARAM = re.compile(r"{(\w+)}")


def list_routes() -> list[str]:
    spec = create_app().openapi()
    return [p for p, ops in spec["paths"].items() if p.startswith("/api/v1/t/{tenant_id}") and "get" in ops]


def _b_markers(world: World) -> list[str]:
    return [world.b.tenant_id, *world.b.ids.values(), "Tenant TB", "secret of TB"]


@pytest.mark.parametrize("path", list_routes())
def test_responses_never_contain_other_tenant(world: World, path: str) -> None:
    url = PARAM.sub(lambda m: world.a.tenant_id if m.group(1) == "tenant_id" else world.a.ids[m.group(1)], path)
    for client in (world.a.fde, world.a.client_admin, world.a.client_user):
        r = client.get(url)
        if r.status_code in (403,):
            continue
        assert r.status_code == 200, (url, r.text)
        body = r.content.decode("utf-8", errors="ignore")
        for marker in _b_markers(world):
            assert marker not in body, (url, marker)


def test_home_and_me_scoped(world: World) -> None:
    for client in (world.a.fde, world.a.client_admin, world.a.client_user):
        for url in ("/api/v1/home", "/api/v1/auth/me"):
            body = client.get(url).text
            for marker in _b_markers(world):
                assert marker not in body, (url, marker)


def test_tenant_export_contains_only_own_data(world: World) -> None:
    r = world.a.client_admin.get(f"/api/v1/t/{world.a.tenant_id}/export")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    blob = "".join(zf.read(n).decode("utf-8", errors="ignore") for n in zf.namelist())
    for marker in _b_markers(world):
        assert marker not in blob, marker
    manifest = json.loads(zf.read("manifest.json"))
    for rows in manifest["tables"].values():
        assert all(row["tenant_id"] == world.a.tenant_id for row in rows)
    assert "secret of TA" in blob


def test_client_user_cannot_export(world: World) -> None:
    assert world.a.client_user.get(f"/api/v1/t/{world.a.tenant_id}/export").status_code == 403


def test_body_tenant_id_is_ignored(world: World) -> None:
    r = world.a.fde.post(
        f"/api/v1/t/{world.a.tenant_id}/systems", json={"name": "Sneaky", "tenant_id": world.b.tenant_id}
    )
    assert r.status_code == 201
    assert r.json()["tenant_id"] == world.a.tenant_id
    names = [s["name"] for s in world.b.fde.get(f"/api/v1/t/{world.b.tenant_id}/systems").json()["items"]]
    assert "Sneaky" not in names


def test_body_references_to_other_tenant_rejected(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}"
    r = world.a.fde.post(
        f"{base}/devtracker/projects", json={"engagement_id": world.b.ids["engagement_id"], "name": "x"}
    )
    assert r.status_code == 422
    ref = {"asset_id": world.template["asset_id"], "version": 2}
    r = world.a.fde.post(
        f"{base}/agenthub/instances",
        json={
            "name": "x",
            "template_ref": ref,
            "engagement_id": world.a.ids["engagement_id"],
            "system_ids": [world.b.ids["system_id"]],
        },
    )
    assert r.status_code == 422
    r = world.a.fde.post(
        f"{base}/agenthub/eval-runs",
        json={
            "template_ref": ref,
            "evidence_file_ids": [world.b.ids["file_id"]],
        },
    )
    assert r.status_code == 422
    r = world.a.fde.patch(f"{base}/devtracker/tasks/{world.a.ids['task_id']}", json={"assignee_id": world.b.fde_id})
    assert r.status_code == 422
