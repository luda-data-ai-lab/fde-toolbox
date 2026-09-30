from tests.conftest import World


def test_versions_and_diff(world: World) -> None:
    aid = world.template["asset_id"]
    c = world.a.fde
    versions = c.get(f"/api/v1/assets/{aid}").json()
    assert [v["version"] for v in versions] == [1, 2]
    d = c.get(f"/api/v1/assets/{aid}/diff", params={"from_version": 1, "to_version": 2}).json()
    assert "+Summarise the daily production report in Korean." in d["prompt_diff"]
    assert d["payload_diff"].startswith("--- v1")
    listing = c.get("/api/v1/assets", params={"asset_type": "agent_template"}).json()
    assert listing[0]["latest_version"] == 2 and listing[0]["versions"] == 2
    assert c.get("/api/v1/assets/missing").status_code == 404


def test_only_admin_edits_assets(world: World) -> None:
    aid = world.template["asset_id"]
    body = {"payload": {}, "change_note": "x"}
    assert world.a.fde.post(f"/api/v1/assets/{aid}/versions", json=body).status_code == 403
    assert (
        world.a.fde.post("/api/v1/assets", json={"asset_type": "rule_pack", "asset_key": "r", "title": "t"}).status_code
        == 403
    )


def test_published_payload_is_frozen(world: World) -> None:
    aid = world.template["asset_id"]
    r = world.admin.patch(f"/api/v1/assets/{aid}/versions/2", json={"payload": {"x": 1}})
    assert r.status_code == 400
    r = world.admin.patch(f"/api/v1/assets/{aid}/versions/2", json={"status": "deprecated"})
    assert r.json()["status"] == "deprecated"


def test_package_roundtrip(world: World) -> None:
    aid = world.template["asset_id"]
    pkg = world.admin.get("/api/v1/assets/export", params={"asset_ids": [aid]}).json()
    assert pkg["schema_version"] == 1 and len(pkg["assets"]) == 2
    assert {r["table"] for r in pkg["related"]} == {"agent_eval_cases"}
    assert all("tenant_id" not in a for a in pkg["assets"])
    assert world.admin.post("/api/v1/assets/import", json=pkg).json() == {"created": 0, "skipped": 4}
    pkg["assets"][0]["asset_id"] = "11111111-1111-1111-1111-111111111111"
    assert world.admin.post("/api/v1/assets/import", json=pkg).json()["created"] == 1
    pkg["schema_version"] = 99
    assert world.admin.post("/api/v1/assets/import", json=pkg).status_code == 400
