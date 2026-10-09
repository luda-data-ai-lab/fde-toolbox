import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.assets.models import AssetItem
from tests.conftest import SEED_DIR, World


@pytest.fixture(autouse=True)
def _upper_seed(admin: TestClient) -> None:
    seed = json.loads((SEED_DIR / "upper-ontology-manufacturing.json").read_text(encoding="utf-8"))
    assert admin.post("/api/v1/assets/import", json=seed).status_code == 200


def _base(world: World) -> str:
    return f"/api/v1/t/{world.a.tenant_id}/ontomap"


def _upper(world: World) -> dict:
    uppers = world.a.fde.get(f"{_base(world)}/upper-ontologies").json()
    return next(u for u in uppers if u["asset_key"] == "manufacturing-common")


def _ref(upper: dict, key: str) -> dict:
    return {"asset_id": upper["asset_id"], "version": upper["version"], "concept_key": key}


def test_upper_ontology_listed(world: World) -> None:
    upper = _upper(world)
    keys = {c["key"] for c in upper["concepts"]}
    assert {"lot", "product", "work_order"} <= keys
    lot = next(c for c in upper["concepts"] if c["key"] == "lot")
    assert lot["name"] == "로트" and "로트번호" in lot["properties"]
    assert {"source": "lot", "name": "inspected_by", "target": "inspection"} in upper["relations"]


def test_concept_crud_inheritance_and_relations(world: World) -> None:
    base = _base(world)
    fde = world.a.fde
    upper = _upper(world)
    bad = fde.post(f"{base}/concepts", json={"name": "X", "parent_ref": _ref(upper, "nope")})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_reference"
    both = fde.post(f"{base}/concepts", json={"name": "X", "parent_ref": _ref(upper, "lot"), "parent_concept_id": "x"})
    assert both.status_code == 422

    lot = fde.post(
        f"{base}/concepts",
        json={
            "name": " 생산 로트 ",
            "definition": "배합 단위",
            "parent_ref": _ref(upper, "lot"),
            "status": "confirmed",
        },
    )
    assert lot.status_code == 201, lot.text
    lot_d = lot.json()
    assert lot_d["name"] == "생산 로트" and lot_d["ancestors"][0]["kind"] == "upper"
    assert lot_d["ancestors"][0]["id"] == "lot" and "로트번호" in [p["name"] for p in lot_d["inherited_properties"]]
    assert any(r["name"] == "inspected_by" and r["target"] == "품질검사" for r in lot_d["inherited_relations"])
    assert [w["code"] for w in lot_d["warnings"]] == ["unmapped_concept"]

    attr = fde.post(
        f"{base}/concepts/{lot_d['id']}/attributes", json={"name": "LOT 번호", "data_type": "code", "required": True}
    ).json()
    child = fde.post(f"{base}/concepts", json={"name": "반제품 로트", "parent_concept_id": lot_d["id"]}).json()
    assert [a["name"] for a in child["ancestors"]] == ["생산 로트", "로트"]
    origins = {p["name"]: p["origin"] for p in child["inherited_properties"]}
    assert origins["LOT 번호"] == "생산 로트" and origins["로트번호"].endswith("/ 로트")

    patched = fde.patch(f"{base}/concepts/{lot_d['id']}", json={"id_attribute_id": attr["id"]}).json()
    assert patched["id_attribute_id"] == attr["id"]
    foreign_attr = fde.post(f"{base}/concepts/{child['id']}/attributes", json={"name": "등급"}).json()
    assert fde.patch(f"{base}/concepts/{lot_d['id']}", json={"id_attribute_id": foreign_attr["id"]}).status_code == 422

    cycle = fde.patch(f"{base}/concepts/{lot_d['id']}", json={"parent_concept_id": child["id"]})
    assert cycle.status_code == 422 and cycle.json()["error"]["code"] == "inheritance_cycle"
    assert fde.patch(f"{base}/concepts/{lot_d['id']}", json={"parent_concept_id": lot_d["id"]}).status_code == 422

    rel = fde.post(
        f"{base}/relations",
        json={
            "source_concept_id": child["id"],
            "name": "투입된다",
            "target_concept_id": lot_d["id"],
            "cardinality": "N:M",
            "inverse_name": "투입받는다",
        },
    )
    assert rel.status_code == 201, rel.text
    assert fde.get(f"{base}/relations", params={"concept_id": lot_d["id"]}).json()["items"][0]["id"] == rel.json()["id"]
    assert fde.patch(f"{base}/relations/{rel.json()['id']}", json={"cardinality": "1:1"}).json()["cardinality"] == "1:1"
    assert any(r["name"] == "투입된다" for r in fde.get(f"{base}/concepts/{lot_d['id']}").json()["relations"])

    term = fde.post(f"{base}/terms", json={"term": "LOT", "definition": "로트", "concept_id": lot_d["id"]}).json()
    assert [t["id"] for t in fde.get(f"{base}/concepts/{lot_d['id']}").json()["terms"]] == [term["id"]]

    assert fde.delete(f"{base}/attributes/{attr['id']}").status_code == 204
    assert fde.get(f"{base}/concepts/{lot_d['id']}").json()["id_attribute_id"] is None
    assert fde.delete(f"{base}/concepts/{lot_d['id']}").status_code == 204
    orphan = fde.get(f"{base}/concepts/{child['id']}").json()
    assert orphan["parent_concept_id"] is None and orphan["relations"] == []
    assert fde.get(f"{base}/terms/{term['id']}").json()["concept_id"] is None


def test_validator_warns_without_blocking(world: World) -> None:
    base = _base(world)
    fde = world.a.fde
    a = fde.post(f"{base}/concepts", json={"name": "설비"}).json()
    b = fde.post(f"{base}/concepts", json={"name": " 설 비"}).json()
    assert b["name"] == "설 비" and "orphan_concept" in [w["code"] for w in a["warnings"]]
    term = fde.post(f"{base}/terms", json={"term": "가동률"}).json()
    issues = fde.get(f"{base}/validation").json()["issues"]
    codes = {(i["code"], i["target_id"]) for i in issues}
    assert ("duplicate_concept", a["id"]) in codes and ("duplicate_concept", b["id"]) in codes
    assert ("orphan_concept", b["id"]) in codes and ("term_without_definition", term["id"]) in codes


def test_permissions_isolation_and_upper_untouched(world: World, db: Session) -> None:
    base = _base(world)
    before = [(r.id, r.payload) for r in db.scalars(select(AssetItem).where(AssetItem.asset_type == "upper_ontology"))]
    upper = _upper(world)
    mine = world.a.fde.post(f"{base}/concepts", json={"name": "로트", "parent_ref": _ref(upper, "lot")}).json()
    assert world.a.client_user.get(f"{base}/concepts/{mine['id']}").status_code == 200
    assert world.a.client_user.post(f"{base}/concepts", json={"name": "Y"}).status_code == 403
    assert world.a.client_user.patch(f"{base}/concepts/{mine['id']}", json={"name": "Y"}).status_code == 403
    foreign = world.b.ids["concept_id"]
    assert world.a.fde.post(f"{base}/concepts", json={"name": "Z", "parent_concept_id": foreign}).status_code == 422
    rel = {"source_concept_id": mine["id"], "name": "r", "target_concept_id": foreign}
    assert world.a.fde.post(f"{base}/relations", json=rel).status_code == 422
    assert world.a.fde.post(f"{base}/terms", json={"term": "Q", "concept_id": foreign}).status_code == 422
    db.expire_all()
    after = [(r.id, r.payload) for r in db.scalars(select(AssetItem).where(AssetItem.asset_type == "upper_ontology"))]
    assert after == before
