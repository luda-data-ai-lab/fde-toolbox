from tests.conftest import World


def test_phase0_acceptance_template_versions_and_instance_visibility(world: World) -> None:
    """Template v1/v2 registered, tenant A instance on v2, invisible to tenant B users."""
    aid = world.template["asset_id"]
    a_items = world.a.client_user.get(f"/api/v1/t/{world.a.tenant_id}/agenthub/instances").json()["items"]
    assert [i["template_ref"] for i in a_items] == [{"asset_id": aid, "version": 2}]
    for client in (world.b.fde, world.b.client_admin, world.b.client_user):
        b_items = client.get(f"/api/v1/t/{world.b.tenant_id}/agenthub/instances").json()["items"]
        assert world.a.ids["instance_id"] not in {i["id"] for i in b_items}
        assert client.get(f"/api/v1/t/{world.a.tenant_id}/agenthub/instances").status_code == 404


def test_eval_cases_and_runs(world: World) -> None:
    aid = world.template["asset_id"]
    cases = world.a.fde.get(f"/api/v1/assets/{aid}/versions/2/eval-cases").json()
    assert len(cases) == 2
    assert world.a.fde.get(f"/api/v1/assets/{aid}/versions/9/eval-cases").status_code == 404
    cid = cases[1]["id"]
    assert (
        world.admin.patch(f"/api/v1/assets/eval-cases/{cid}", json={"criteria": "exact"}).json()["criteria"] == "exact"
    )
    assert world.a.fde.patch(f"/api/v1/assets/eval-cases/{cid}", json={"criteria": "x"}).status_code == 403
    base = f"/api/v1/t/{world.a.tenant_id}/agenthub"
    run = world.a.fde.post(
        f"{base}/eval-runs",
        json={
            "template_ref": {"asset_id": aid, "version": 2},
            "results": [{"case_id": cases[0]["id"], "passed": True}, {"case_id": cid, "passed": False, "note": "typo"}],
        },
    ).json()
    assert run["pass_rate"] == 0.5
    bad = world.a.fde.post(
        f"{base}/eval-runs",
        json={"template_ref": {"asset_id": aid, "version": 1}, "results": [{"case_id": cid, "passed": True}]},
    )
    assert bad.status_code == 422
    runs = world.a.fde.get(f"{base}/eval-runs", params={"asset_id": aid}).json()["items"]
    assert len(runs) == 2
    assert world.a.fde.delete(f"{base}/eval-runs/{run['id']}").status_code == 204
    assert world.admin.delete(f"/api/v1/assets/eval-cases/{cid}").status_code == 204


def test_instance_lifecycle(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}/agenthub/instances"
    iid = world.a.ids["instance_id"]
    fde = world.a.fde
    r = fde.patch(
        f"{base}/{iid}", json={"status": "pilot", "overrides": {"extra": "Use formal tone"}, "owner_id": world.a.fde_id}
    )
    assert r.json()["status"] == "pilot" and r.json()["overrides"] == {"extra": "Use formal tone"}
    assert fde.get(base, params={"status": "pilot"}).json()["items"][0]["id"] == iid
    assert fde.patch(f"{base}/{iid}", json={"status": "retired"}).status_code == 422
    assert fde.patch(f"{base}/{iid}", json={"template_ref": {"asset_id": "nope", "version": 1}}).status_code == 422
    assert fde.patch(f"{base}/{iid}", json={"owner_id": world.b.fde_id}).status_code == 422
    assert world.a.client_admin.patch(f"{base}/{iid}", json={"status": "stopped"}).status_code == 403
    assert fde.delete(f"{base}/{iid}").status_code == 204
