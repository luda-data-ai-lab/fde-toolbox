from fastapi.testclient import TestClient

from tests.conftest import World
from tests.modules.test_exmigrate import _upload


def _base(world: World) -> str:
    return f"/api/v1/t/{world.a.tenant_id}/ontomap"


def _concept(fde: TestClient, base: str, name: str, **extra: object) -> dict:
    res = fde.post(f"{base}/concepts", json={"name": name, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def test_mapping_crud_coverage_and_validation(world: World) -> None:
    base, fde, ids = _base(world), world.a.fde, world.a.ids
    lot = _concept(fde, base, "생산 로트", status="confirmed", definition="배합 단위")
    other = _concept(fde, base, "제품")
    attr = fde.post(f"{base}/concepts/{lot['id']}/attributes", json={"name": "로트번호"}).json()
    assert fde.post(f"{base}/concepts/{lot['id']}/attributes", json={"name": "점도"}).status_code == 201
    rel = fde.post(
        f"{base}/relations", json={"source_concept_id": lot["id"], "name": "produces", "target_concept_id": other["id"]}
    ).json()

    issues = fde.get(f"{base}/validation").json()["issues"]
    assert {
        "code": "unmapped_concept",
        "target_type": "onto_concept",
        "target_id": lot["id"],
        "name": "생산 로트",
    } in issues

    # Required location per kind
    assert (
        fde.post(f"{base}/mappings", json={"target_kind": "concept", "target_id": lot["id"]}).json()["error"]["code"]
        == "mapping_incomplete"
    )
    no_col = fde.post(f"{base}/mappings", json={"target_kind": "attribute", "target_id": attr["id"], "table_name": "t"})
    assert no_col.status_code == 422 and no_col.json()["error"]["detail"]["field"] == "column_name"
    no_if = fde.post(f"{base}/mappings", json={"target_kind": "relation", "target_id": rel["id"]})
    assert no_if.status_code == 422
    exm = fde.post(
        f"{base}/mappings",
        json={"target_kind": "concept", "target_id": lot["id"], "system_id": ids["system_id"], "origin": "exmigrate"},
    )
    assert exm.status_code == 422 and exm.json()["error"]["detail"]["field"] == "table_name"
    wrong_kind = fde.post(
        f"{base}/mappings", json={"target_kind": "attribute", "target_id": lot["id"], "column_name": "x"}
    )
    assert wrong_kind.status_code == 422 and wrong_kind.json()["error"]["code"] == "invalid_reference"

    m_concept = fde.post(
        f"{base}/mappings",
        json={
            "target_kind": "concept",
            "target_id": lot["id"],
            "system_id": ids["system_id"],
            "table_name": " mes_lot ",
            "origin": "exmigrate",
        },
    )
    assert m_concept.status_code == 201, m_concept.text
    assert m_concept.json()["table_name"] == "mes_lot" and m_concept.json()["concept_id"] == lot["id"]
    m_attr = fde.post(
        f"{base}/mappings",
        json={"target_kind": "attribute", "target_id": attr["id"], "table_name": "mes_lot", "column_name": "lot_no"},
    ).json()
    assert m_attr["concept_id"] == lot["id"]
    m_rel = fde.post(
        f"{base}/mappings",
        json={
            "target_kind": "relation",
            "target_id": rel["id"],
            "interface_id": ids["interface_id"],
            "origin": "interface",
        },
    ).json()
    assert m_rel["concept_id"] == lot["id"]

    detail = fde.get(f"{base}/concepts/{lot['id']}").json()
    assert {m["id"] for m in detail["mappings"]} == {m_concept.json()["id"], m_attr["id"], m_rel["id"]}
    assert not [w for w in detail["warnings"] if w["code"] == "unmapped_concept"]

    cov = {r["concept_id"]: r for r in fde.get(f"{base}/coverage").json()}
    assert cov[lot["id"]]["mapping_count"] == 3
    assert cov[lot["id"]]["systems"] == [f"ERP {world.a.code}"]
    assert cov[lot["id"]]["attributes_total"] == 2 and cov[lot["id"]]["unmapped_attributes"] == ["점도"]
    assert cov[other["id"]]["mapping_count"] == 0

    listed = fde.get(f"{base}/mappings", params={"concept_id": lot["id"]}).json()["items"]
    assert len(listed) == 3
    assert len(fde.get(f"{base}/mappings", params={"system_id": ids["system_id"]}).json()["items"]) >= 1

    # Patch keeps the per-kind requirement
    cleared = fde.patch(f"{base}/mappings/{m_concept.json()['id']}", json={"system_id": None})
    assert cleared.status_code == 422
    patched = fde.patch(f"{base}/mappings/{m_attr['id']}", json={"column_name": "lot_number", "notes": "PK"})
    assert patched.status_code == 200 and patched.json()["column_name"] == "lot_number"

    # Deleting targets removes their mappings
    assert fde.delete(f"{base}/attributes/{attr['id']}").status_code == 204
    assert fde.delete(f"{base}/concepts/{other['id']}").status_code == 204
    left = fde.get(f"{base}/mappings", params={"concept_id": lot["id"]}).json()["items"]
    assert [m["id"] for m in left] == [m_concept.json()["id"]]
    assert fde.delete(f"{base}/mappings/{m_concept.json()['id']}").status_code == 204
    assert fde.delete(f"{base}/concepts/{lot['id']}").status_code == 204


def test_mapping_rejects_foreign_refs(world: World) -> None:
    base, fde, a, b = _base(world), world.a.fde, world.a.ids, world.b.ids
    for body in (
        {"target_kind": "concept", "target_id": b["concept_id"], "system_id": a["system_id"]},
        {"target_kind": "concept", "target_id": a["concept_id"], "system_id": b["system_id"]},
        {"target_kind": "relation", "target_id": a["relation_id"], "interface_id": b["interface_id"]},
        {"target_kind": "attribute", "target_id": b["attribute_id"], "column_name": "c"},
    ):
        res = fde.post(f"{base}/mappings", json=body)
        assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_reference", body


def test_mapping_permissions_and_sources(world: World) -> None:
    base = _base(world)
    body = {"target_kind": "concept", "target_id": world.a.ids["concept_id"], "system_id": world.a.ids["system_id"]}
    assert world.a.client_user.post(f"{base}/mappings", json=body).status_code == 403
    src = world.a.client_user.get(f"{base}/mapping-sources").json()
    assert {s["id"] for s in src["systems"]} == {world.a.ids["system_id"]}
    assert world.a.ids["interface_id"] in {i["id"] for i in src["interfaces"]}
    assert world.b.ids["interface_id"] not in {i["id"] for i in src["interfaces"]}
    assert src["erd_tables"] and all(t["filename"] != f"xl-{world.b.code}.xlsx" for t in src["erd_tables"])


def test_mapping_sources_list_confirmed_erd_tables(world: World) -> None:
    fde = world.a.fde
    analysis = _upload(world)
    url = f"/api/v1/t/{world.a.tenant_id}/exmigrate/analyses/{analysis['id']}"
    erd = fde.get(f"{url}/erd").json()["erd"]
    erd["tables"][1]["columns"][0]["primary_key"] = True
    assert fde.put(f"{url}/erd", json=erd).status_code == 200
    src = f"{_base(world)}/mapping-sources"
    assert analysis["id"] not in {t["analysis_id"] for t in fde.get(src).json()["erd_tables"]}
    assert fde.post(f"{url}/erd/confirm").status_code == 200
    tables = [t for t in fde.get(src).json()["erd_tables"] if t["analysis_id"] == analysis["id"]]
    assert [t["table"] for t in tables] == [t["name"] for t in erd["tables"]]
    assert tables[0]["columns"] == [c["name"] for c in erd["tables"][0]["columns"]]
    other = world.b.fde.get(f"/api/v1/t/{world.b.tenant_id}/ontomap/mapping-sources").json()["erd_tables"]
    assert analysis["id"] not in {t["analysis_id"] for t in other}
