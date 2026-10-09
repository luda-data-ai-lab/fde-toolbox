import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.llm import LlmConfig
from app.adapters.registry import LLM
from app.config import get_settings
from app.modules.ontomap import extract
from tests.conftest import World
from tests.modules.test_exmigrate import _upload


def _base(world: World) -> str:
    return f"/api/v1/t/{world.a.tenant_id}/ontomap"


def _cands(fde: TestClient, base: str, **params: str) -> list[dict[str, Any]]:
    r = fde.get(f"{base}/candidates", params={"limit": "200", **params})
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


def _one(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(c for c in items if c["name"] == name)


def _actions(world: World) -> list[str]:
    logs = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/audit-logs", params={"limit": 200}).json()["items"]
    return [x["action"] for x in logs]


@pytest.fixture
def adapters_allowed() -> Iterator[None]:
    settings = get_settings()
    prev, settings.adapters_allowed = settings.adapters_allowed, True
    yield
    settings.adapters_allowed = prev


class FakeTransport:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, config: LlmConfig, api_key: str) -> str:
        self.prompts.append(prompt)
        return self.replies.pop(0)


def test_pure_extractors() -> None:
    erd = {
        "tables": [
            {
                "name": "orders",
                "label": "주문",
                "columns": [
                    {"name": "order_no", "label": "주문번호", "type": "integer", "nullable": False},
                    {"name": "product_code", "label": "제품코드", "type": "text"},
                    {"name": "memo", "label": "비고"},
                ],
            },
            {"name": "products", "label": "", "columns": [{"name": "product_code", "label": "제품코드"}]},
        ],
        "relations": [
            {
                "from_table": "orders",
                "from_column": "product_code",
                "to_table": "products",
                "to_column": "product_code",
            },
            {"from_table": "orders", "from_column": "x", "to_table": "missing", "to_column": "x"},
        ],
    }
    items = extract.from_erd(erd)
    assert [(i.kind, i.name) for i in items] == [
        ("concept", "주문"),
        ("attribute", "주문.주문번호"),
        ("attribute", "주문.제품코드"),
        ("attribute", "주문.비고"),
        ("concept", "products"),
        ("attribute", "products.제품코드"),
        ("relation", "주문 → products"),
    ]
    assert items[1].payload == {
        "concept": "주문",
        "attribute": "주문번호",
        "table": "orders",
        "column": "order_no",
        "data_type": "integer",
        "required": True,
    }
    assert items[3].payload["data_type"] == "string"
    assert items[-1].payload["relation"] == "제품코드" and items[-1].payload["column"] == "product_code"
    assert extract.from_erd(erd) == items

    assert extract.interface_subject("수주 정보 전송") == "수주"
    assert extract.interface_subject("생산실적 I/F") == "생산실적"
    assert extract.interface_subject("전송") == "전송"
    [concept] = extract.from_interface("출하 데이터 연동", "IF-1", " 출하 지시 데이터 ")
    assert concept.name == "출하" and concept.payload == {
        "if_code": "IF-1",
        "interface": "출하 데이터 연동",
        "context": "출하 지시 데이터",
    }

    graph = {
        "nodes": [
            {"id": "d1", "type": "document", "label": "작업 지시서", "lane": "생산팀"},
            {"id": "d2", "type": "document", "label": "작업  지시서"},
            {"id": "t1", "type": "task", "label": "검사"},
            {"id": "d3", "type": "document", "label": ""},
        ]
    }
    assert [(i.name, i.payload) for i in extract.from_flow("생산", graph)] == [
        ("작업 지시서", {"node_id": "d1", "flow": "생산", "department": "생산팀"})
    ]


def test_erd_extraction_accept_and_merge(world: World) -> None:
    fde, base = world.a.fde, _base(world)
    analysis = _upload(world)
    url = f"/api/v1/t/{world.a.tenant_id}/exmigrate/analyses/{analysis['id']}"
    body = {"source_type": "exmigrate_erd", "source_id": analysis["id"]}
    early = fde.post(f"{base}/candidates/extract", json=body)
    assert early.status_code == 409 and early.json()["error"]["code"] == "erd_not_confirmed"
    assert fde.post(f"{url}/erd/confirm").status_code == 200
    erd = fde.get(f"{url}/erd").json()["erd"]

    r = fde.post(f"{base}/candidates/extract", json=body)
    assert r.status_code == 200, r.text
    first = r.json()
    n_cols = sum(len(t["columns"]) for t in erd["tables"])
    assert first["by_kind"]["concept"] == len(erd["tables"]) and first["by_kind"]["attribute"] == n_cols
    assert first["by_kind"].get("relation", 0) == len(
        {(rel["from_table"], rel["to_table"]) for rel in erd["relations"] if rel["from_table"] != rel["to_table"]}
    )
    again = fde.post(f"{base}/candidates/extract", json=body).json()
    assert again == {"created": 0, "existing": first["created"], "by_kind": {}}

    items = _cands(fde, base, source_type="exmigrate_erd", source_id=analysis["id"])
    assert {c["status"] for c in items} == {"open"}
    assert all(c["name"] not in ("제품", "Order List") for c in fde.get(f"{base}/concepts").json()["items"])
    concepts = _cands(fde, base, source_id=analysis["id"], kind="concept")
    assert {c["name"] for c in concepts} == {"제품", "Order List"}

    # attribute before its concept: owning concept cannot be resolved yet
    price = _one(items, "제품.단가")
    assert price["kind"] == "attribute" and price["payload"]["table"] == erd["tables"][0]["name"]
    missing = fde.post(f"{base}/candidates/{price['id']}/accept", json={})
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "concept_required"

    product = fde.post(
        f"{base}/candidates/{_one(concepts, '제품')['id']}/accept",
        json={"definition": "판매 제품", "system_id": world.a.ids["system_id"]},
    )
    assert product.status_code == 200, product.text
    pid = product.json()["resolved_into_id"]
    concept = fde.get(f"{base}/concepts/{pid}").json()
    assert concept["status"] == "confirmed" and concept["definition"] == "판매 제품"
    assert [(m["system_id"], m["table_name"], m["origin"]) for m in concept["mappings"]] == [
        (world.a.ids["system_id"], erd["tables"][0]["name"], "exmigrate")
    ]

    accepted = fde.post(f"{base}/candidates/{price['id']}/accept", json={}).json()
    assert accepted["status"] == "accepted"
    detail = fde.get(f"{base}/concepts/{pid}").json()
    attr = next(a for a in detail["attributes"] if a["id"] == accepted["resolved_into_id"])
    assert attr["name"] == "단가" and attr["data_type"] == "decimal"
    col = next(c["name"] for c in erd["tables"][0]["columns"] if c["label"] == "단가")
    assert any(m["target_id"] == attr["id"] and m["column_name"] == col for m in detail["mappings"])

    # relation needs both concepts; Order List is accepted as a draft
    [rel] = [c for c in items if c["kind"] == "relation"]
    blocked = fde.post(f"{base}/candidates/{rel['id']}/accept", json={})
    assert blocked.status_code == 422 and blocked.json()["error"]["detail"]["field"] == "source_concept_id"
    orders = fde.post(f"{base}/candidates/{_one(concepts, 'Order List')['id']}/accept", json={"status": "candidate"})
    assert fde.get(f"{base}/concepts/{orders.json()['resolved_into_id']}").json()["status"] == "draft"
    ok = fde.post(f"{base}/candidates/{rel['id']}/accept", json={})
    assert ok.status_code == 200, ok.text
    relation = next(x for x in fde.get(f"{base}/relations").json()["items"] if x["id"] == ok.json()["resolved_into_id"])
    assert relation["source_concept_id"] == orders.json()["resolved_into_id"] and relation["target_concept_id"] == pid

    # merging an attribute candidate into an existing attribute also records the column mapping
    name_cand = _one(_cands(fde, base, source_id=analysis["id"], status="open"), "제품.제품명")
    assert name_cand["kind"] == "attribute" and name_cand["payload"]["attribute"] == "제품명"
    foreign = fde.post(f"{base}/candidates/{name_cand['id']}/merge", json={"target_id": world.b.ids["attribute_id"]})
    assert foreign.status_code == 422 and foreign.json()["error"]["detail"]["field"] == "target_id"
    merged = fde.post(f"{base}/candidates/{name_cand['id']}/merge", json={"target_id": attr["id"]})
    assert merged.status_code == 200 and merged.json()["status"] == "merged"

    # ignore → reopen, idempotent re-extract keeps resolved/ignored candidates as they are
    memo = _one(_cands(fde, base, source_id=analysis["id"], status="open"), "Order List.비고")
    assert fde.post(f"{base}/candidates/{memo['id']}/ignore").json()["status"] == "ignored"
    assert fde.post(f"{base}/candidates/extract", json=body).json()["created"] == 0
    assert fde.post(f"{base}/candidates/{memo['id']}/reopen").json()["status"] == "open"

    actions = _actions(world)
    for a in ("ontomap.candidate_extract", "ontomap.candidate_accept", "ontomap.candidate_merge"):
        assert a in actions


def test_interface_and_flow_extraction_with_concept_suggestions(world: World) -> None:
    fde, base = world.a.fde, _base(world)
    tbase = f"/api/v1/t/{world.a.tenant_id}"
    iface = fde.post(
        f"{tbase}/interfaces",
        json={
            "if_code": "IF-ORD-9",
            "name": "수주 정보 전송",
            "description": "고객 수주 헤더와 품목",
            "source_system_id": world.a.ids["system_id"],
            "target_system_id": world.a.ids["system_id"],
        },
    ).json()
    r = fde.post(f"{base}/candidates/extract", json={"source_type": "interface"})
    assert r.status_code == 200, r.text
    assert r.json()["by_kind"] == {"concept": 2}
    order = _one(_cands(fde, base, source_type="interface", source_id=iface["id"]), "수주")
    assert order["payload"]["context"] == "고객 수주 헤더와 품목" and order["payload"]["if_code"] == "IF-ORD-9"

    existing = fde.post(f"{base}/concepts", json={"name": "수주 "}).json()
    order = _one(_cands(fde, base, source_type="interface", source_id=iface["id"]), "수주")
    assert order["similar"][0]["term_id"] == existing["id"] and order["similar"][0]["score"] == 100
    accepted = fde.post(
        f"{base}/candidates/{order['id']}/accept", json={"term": "고객 수주", "system_id": world.a.ids["system_id"]}
    ).json()
    mapping = fde.get(f"{base}/concepts/{accepted['resolved_into_id']}").json()["mappings"][0]
    assert mapping["interface_id"] == iface["id"] and mapping["origin"] == "interface"

    flow = fde.post(
        f"{tbase}/flowdesk/flows",
        json={
            "engagement_id": world.a.ids["engagement_id"],
            "title": "출하",
            "graph": {
                "lanes": ["물류"],
                "nodes": [{"id": "d", "type": "document", "label": "출하 지시서", "lane": "물류"}],
            },
        },
    ).json()
    one = fde.post(f"{base}/candidates/extract", json={"source_type": "flowdesk_flow", "source_id": flow["id"]})
    assert one.json() == {"created": 1, "existing": 0, "by_kind": {"concept": 1}}
    cand = _cands(fde, base, source_type="flowdesk_flow", source_id=flow["id"])[0]
    assert cand["name"] == "출하 지시서" and cand["payload"]["department"] == "물류"
    merged = fde.post(f"{base}/candidates/{cand['id']}/merge", json={"target_id": existing["id"]}).json()
    assert merged["status"] == "merged" and merged["resolved_into_id"] == existing["id"]

    for source_type, key in (
        ("interface", "interface_id"),
        ("flowdesk_flow", "flow_id"),
        ("exmigrate_erd", "analysis_id"),
    ):
        bad = fde.post(f"{base}/candidates/extract", json={"source_type": source_type, "source_id": world.b.ids[key]})
        assert bad.status_code == 422 and bad.json()["error"]["detail"]["field"] == "source_id"
    assert all(
        c["source_id"] != iface["id"]
        for c in _cands(world.b.fde, f"/api/v1/t/{world.b.tenant_id}/ontomap", source_type="interface")
    )
    assert world.a.client_user.post(f"{base}/candidates/extract", json={"source_type": "interface"}).status_code == 403
    assert fde.post(f"{base}/candidates/extract", json={"source_type": "manual"}).status_code == 422
    kinds = {c["kind"] for c in _cands(fde, base, kind="concept")}
    assert kinds == {"concept"}


def test_llm_suggestions_copy_mode(world: World) -> None:
    fde, base = world.a.fde, _base(world)
    sid = world.a.ids["session_id"]
    prompt = fde.post(f"{base}/candidates/suggest/prompt", json={"task": "terms", "session_id": sid})
    assert prompt.status_code == 200, prompt.text
    body = prompt.json()
    assert body["llm_available"] is False
    assert f"Interview {world.a.code}" in body["prompt"] and f"Insight {world.a.code}" in body["prompt"]
    assert f"Term {world.a.code}" in body["prompt"] and "JSON Schema" in body["prompt"]
    assert fde.post(f"{base}/candidates/suggest/prompt", json={"task": "terms"}).status_code == 422
    foreign = fde.post(
        f"{base}/candidates/suggest/prompt", json={"task": "terms", "session_id": world.b.ids["session_id"]}
    )
    assert foreign.status_code == 422 and foreign.json()["error"]["detail"]["field"] == "session_id"

    answer = json.dumps({"terms": [{"name": "배합비", "definition": "원료 배합 비율", "department": "생산팀"}]})
    run = {"task": "terms", "session_id": sid, "answer": f"```json\n{answer}\n```"}
    r = fde.post(f"{base}/candidates/suggest", json=run)
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 1, "existing": 0, "by_kind": {"term": 1}}
    assert fde.post(f"{base}/candidates/suggest", json=run).json()["created"] == 0
    cand = _one(_cands(fde, base, source_type="llm"), "배합비")
    assert cand["status"] == "open" and cand["source_id"] == sid and cand["payload"]["definition"] == "원료 배합 비율"
    assert all(t["term"] != "배합비" for t in fde.get(f"{base}/terms").json()["items"])
    bad = fde.post(f"{base}/candidates/suggest", json={**run, "answer": "not json"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "suggest_result_invalid"

    rels = fde.post(f"{base}/candidates/suggest/prompt", json={"task": "relations"})
    assert rels.status_code == 409 and rels.json()["error"]["code"] == "not_enough_concepts"
    fde.post(f"{base}/concepts", json={"name": "배합"})
    assert (
        f"Concept {world.a.code}"
        in fde.post(f"{base}/candidates/suggest/prompt", json={"task": "relations"}).json()["prompt"]
    )
    rel_answer = {
        "relations": [
            {"source": "배합", "name": "사용한다", "target": f"Concept {world.a.code}", "cardinality": "N:M"},
            {"source": "배합", "name": "없음", "target": "Unknown"},
        ]
    }
    out = fde.post(f"{base}/candidates/suggest", json={"task": "relations", "answer": json.dumps(rel_answer)})
    assert out.json()["by_kind"] == {"relation": 1}
    rel = next(c for c in _cands(fde, base, source_type="llm", kind="relation"))
    assert rel["payload"]["cardinality"] == "N:M" and rel["payload"]["relation"] == "사용한다"
    ok = fde.post(f"{base}/candidates/{rel['id']}/accept", json={}).json()
    assert ok["status"] == "accepted"

    defs = {
        "definitions": [
            {"name": f"term {world.a.code}", "definition": "테스트 용어"},
            {"name": "배합", "definition": "원료를 섞는 작업"},
        ]
    }
    d = fde.post(f"{base}/candidates/suggest", json={"task": "definitions", "answer": json.dumps(defs)}).json()
    assert d["by_kind"] == {"term": 1, "concept": 1}
    term_def = _one(_cands(fde, base, source_type="llm", kind="term"), f"Term {world.a.code}")
    assert term_def["similar"][0]["term_id"] == world.a.ids["term_id"]
    fde.post(f"{base}/candidates/{term_def['id']}/merge", json={"target_id": world.a.ids["term_id"]})
    term = fde.get(f"{base}/terms/{world.a.ids['term_id']}").json()
    assert term["definition"] == "테스트 용어" and {a["alias"] for a in term["aliases"]} == {f"T{world.a.code}"}
    assert "ontomap.candidate_suggest" in _actions(world)


def test_llm_suggestions_adapter_mode(world: World, adapters_allowed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fde, base = world.a.fde, _base(world)
    body = {"task": "terms", "session_id": world.a.ids["session_id"]}
    disabled = fde.post(f"{base}/candidates/suggest", json=body)
    assert disabled.status_code == 409 and disabled.json()["error"]["code"] == "adapter_disabled"
    aid = world.a.ids["activation_id"]
    approve = world.a.client_admin.post(
        f"/api/v1/t/{world.a.tenant_id}/adapters/activations/{aid}/approve", json={"acknowledged_egress": True}
    )
    assert approve.status_code == 200, approve.text
    assert fde.post(f"{base}/candidates/suggest/prompt", json=body).json()["llm_available"] is True
    fake = FakeTransport([json.dumps({"terms": [{"name": "도료 로트"}]})])
    monkeypatch.setattr(LLM, "transport", fake)
    r = fde.post(f"{base}/candidates/suggest", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1 and "JSON Schema" in fake.prompts[0]
    assert _one(_cands(fde, base, source_type="llm"), "도료 로트")["status"] == "open"
