import json
from collections.abc import Iterator
from typing import Any

import pytest

from app.adapters.llm import LlmConfig
from app.adapters.registry import LLM
from app.config import get_settings
from app.modules.flowdesk.mermaid import to_mermaid
from app.modules.flowdesk.schemas import FlowGraph
from app.modules.flowdesk.service import LANE_HEIGHT, template_graph
from tests.conftest import World


def _base(world: World) -> str:
    return f"/api/v1/t/{world.a.tenant_id}/flowdesk"


def _graph(system_id: str | None = None) -> dict[str, Any]:
    return {
        "lanes": ["영업", "생산"],
        "nodes": [
            {"id": "s", "type": "start", "label": "시작", "lane": "영업", "position": {"x": 0, "y": 0}},
            {"id": "t", "type": "task", "label": '수주 "접수"', "lane": "영업"},
            {"id": "d", "type": "decision", "label": "재고?", "lane": "생산"},
            {"id": "m", "type": "system", "label": "", "system_id": system_id},
        ],
        "edges": [
            {"id": "e1", "source": "s", "target": "t"},
            {"id": "e2", "source": "t", "target": "d", "label": "예"},
            {"id": "e3", "source": "d", "target": "m"},
        ],
    }


def _actions(world: World) -> list[str]:
    logs = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/audit-logs", params={"limit": 200}).json()["items"]
    return [x["action"] for x in logs]


def _create(world: World, **extra: Any) -> dict[str, Any]:
    body = {"engagement_id": world.a.ids["engagement_id"], "title": "주문 처리", **extra}
    r = world.a.fde.post(f"{_base(world)}/flows", json=body)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def test_graph_validation() -> None:
    FlowGraph.model_validate(_graph())
    bad = [
        {"nodes": [{"id": "a"}, {"id": "a"}]},
        {"nodes": [{"id": "a"}], "edges": [{"id": "e", "source": "a", "target": "zz"}]},
        {"nodes": [{"id": "a", "lane": "없는 레인"}]},
        {"lanes": ["x", "x"]},
        {"nodes": [{"id": "a", "type": "bogus"}]},
    ]
    for g in bad:
        try:
            FlowGraph.model_validate(g)
        except ValueError:
            continue
        raise AssertionError(g)


def test_mermaid_export_shapes_and_escaping() -> None:
    graph = FlowGraph.model_validate(_graph("sys-1"))
    text = to_mermaid(graph, {"sys-1": "MES"})
    assert text.startswith("flowchart LR\n")
    assert 'subgraph lane0["영업"]' in text and 'subgraph lane1["생산"]' in text
    assert 'n0(["시작"])' in text
    assert 'n1["수주 #quot;접수#quot;"]' in text
    assert 'n2{"재고?"}' in text
    assert 'n3[("MES")]' in text
    assert 'n1 -->|"예"| n2' in text and "n0 --> n1" in text


def test_template_layout() -> None:
    payload = {
        "lanes": ["A", "B"],
        "nodes": [
            {"id": "s", "type": "start", "label": "시작", "lane": "A"},
            {"id": "x", "type": "weird", "label": "X", "lane": "B"},
        ],
        "edges": [{"from": "s", "to": "x"}],
    }
    g = template_graph(payload)
    assert [n.type for n in g.nodes] == ["start", "task"]
    assert g.nodes[1].position.y - g.nodes[0].position.y == LANE_HEIGHT
    assert g.nodes[1].position.x > g.nodes[0].position.x
    assert g.edges[0].source == "s" and g.edges[0].target == "x"


def test_flow_crud_and_system_refs(world: World) -> None:
    base = _base(world)
    fde = world.a.fde
    flow = _create(world, graph=_graph(world.a.ids["system_id"]), perspective="pm")
    assert flow["kind"] == "as_is" and flow["node_count"] == 4 and flow["graph"]["schema_version"] == 1
    assert flow["tenant_id"] == world.a.tenant_id

    foreign = _graph(world.b.ids["system_id"])
    r = fde.post(f"{base}/flows", json={"engagement_id": world.a.ids["engagement_id"], "title": "x", "graph": foreign})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_reference"
    r = fde.post(f"{base}/flows", json={"engagement_id": world.b.ids["engagement_id"], "title": "x"})
    assert r.status_code == 422
    r = fde.patch(f"{base}/flows/{flow['id']}", json={"graph": foreign})
    assert r.status_code == 422

    r = fde.patch(f"{base}/flows/{flow['id']}", json={"title": "주문 처리 v2", "graph": {"nodes": [{"id": "only"}]}})
    assert r.status_code == 200 and r.json()["title"] == "주문 처리 v2" and r.json()["node_count"] == 1

    listed = fde.get(f"{base}/flows", params={"engagement_id": world.a.ids["engagement_id"], "kind": "as_is"}).json()
    assert flow["id"] in [x["id"] for x in listed["items"]]
    assert "graph" not in listed["items"][0]

    for client in (world.a.client_admin, world.a.client_user):
        assert client.get(f"{base}/flows/{flow['id']}").status_code == 200
        assert client.patch(f"{base}/flows/{flow['id']}", json={"title": "no"}).status_code == 403
    assert fde.delete(f"{base}/flows/{flow['id']}").status_code == 204
    assert fde.get(f"{base}/flows/{flow['id']}").status_code == 404
    acts = _actions(world)
    assert {"flowdesk.flow_create", "flowdesk.flow_update", "flowdesk.flow_delete"} <= set(acts)


def test_template_start(world: World) -> None:
    payload = {
        "lanes": ["영업", "품질"],
        "nodes": [{"id": "s", "type": "start", "label": "시작", "lane": "영업"}, {"id": "q", "label": "검사"}],
        "edges": [{"from": "s", "to": "q"}],
    }
    asset = world.admin.post(
        "/api/v1/assets",
        json={
            "asset_type": "flow_template",
            "asset_key": "t-1",
            "title": "검사 흐름",
            "payload": payload,
            "status": "published",
        },
    ).json()
    templates = world.a.fde.get(f"{_base(world)}/templates").json()
    tpl = next(t for t in templates if t["asset_id"] == asset["asset_id"])
    assert tpl["graph"]["lanes"] == ["영업", "품질"]
    flow = _create(world, template_ref={"asset_id": asset["asset_id"], "version": 1})
    assert flow["template_ref"] == {"asset_id": asset["asset_id"], "version": 1}
    assert [n["id"] for n in flow["graph"]["nodes"]] == ["s", "q"]
    r = world.a.fde.post(
        f"{_base(world)}/flows",
        json={
            "engagement_id": world.a.ids["engagement_id"],
            "title": "x",
            "template_ref": {"asset_id": "nope", "version": 1},
        },
    )
    assert r.status_code == 422


def test_pairing(world: World) -> None:
    base = _base(world)
    fde = world.a.fde
    as_is = _create(world, graph=_graph())
    r = fde.post(f"{base}/flows/{as_is['id']}/pair", json={"copy_graph": True})
    assert r.status_code == 201
    to_be = r.json()
    assert to_be["kind"] == "to_be" and to_be["pair_id"] == as_is["id"] and to_be["title"] == "주문 처리 (To-Be)"
    assert to_be["graph"] == fde.get(f"{base}/flows/{as_is['id']}").json()["graph"]
    assert fde.get(f"{base}/flows/{as_is['id']}/pair").json()["id"] == to_be["id"]
    assert fde.post(f"{base}/flows/{as_is['id']}/pair", json={}).status_code == 409

    assert fde.delete(f"{base}/flows/{as_is['id']}/pair").json()["pair_id"] is None
    assert fde.get(f"{base}/flows/{to_be['id']}").json()["pair_id"] is None
    assert fde.get(f"{base}/flows/{as_is['id']}/pair").status_code == 404

    other_as_is = _create(world)
    assert fde.post(f"{base}/flows/{as_is['id']}/pair", json={"flow_id": other_as_is["id"]}).status_code == 422
    assert fde.post(f"{base}/flows/{as_is['id']}/pair", json={"flow_id": world.b.ids["flow_id"]}).status_code == 422
    r = fde.post(f"{base}/flows/{as_is['id']}/pair", json={"flow_id": to_be["id"]})
    assert r.status_code == 201 and r.json()["pair_id"] == as_is["id"]

    assert fde.delete(f"{base}/flows/{to_be['id']}").status_code == 204
    assert fde.get(f"{base}/flows/{as_is['id']}").json()["pair_id"] is None
    assert "flowdesk.flow_pair" in _actions(world) and "flowdesk.flow_unpair" in _actions(world)


def test_snapshots_and_restore(world: World) -> None:
    base = _base(world)
    fde = world.a.fde
    flow = _create(world, graph=_graph(world.a.ids["system_id"]))
    s1 = fde.post(f"{base}/flows/{flow['id']}/snapshots", json={"note": "초안"}).json()
    fde.patch(f"{base}/flows/{flow['id']}", json={"graph": {"nodes": [{"id": "x"}]}})
    s2 = fde.post(f"{base}/flows/{flow['id']}/snapshots", json={}).json()
    assert (s1["version"], s2["version"]) == (1, 2) and s1["node_count"] == 4 and s2["node_count"] == 1
    listed = fde.get(f"{base}/flows/{flow['id']}/snapshots").json()
    assert [s["version"] for s in listed] == [2, 1]
    assert fde.get(f"{base}/flows/{flow['id']}/snapshots/{s1['id']}").json()["graph"]["nodes"][0]["id"] == "s"
    assert world.a.client_user.post(f"{base}/flows/{flow['id']}/snapshots", json={}).status_code == 403

    other = _create(world)
    assert fde.get(f"{base}/flows/{other['id']}/snapshots/{s1['id']}").status_code == 404
    assert fde.post(f"{base}/flows/{other['id']}/snapshots/{s1['id']}/restore").status_code == 404

    assert fde.delete(f"/api/v1/t/{world.a.tenant_id}/systems/{world.a.ids['system_id']}").status_code in (204, 409)
    restored = fde.post(f"{base}/flows/{flow['id']}/snapshots/{s1['id']}/restore").json()
    assert restored["node_count"] == 4
    assert "flowdesk.snapshot_create" in _actions(world) and "flowdesk.snapshot_restore" in _actions(world)


def test_export_and_import_roundtrip(world: World) -> None:
    base = _base(world)
    fde = world.a.fde
    flow = _create(world, graph=_graph(world.a.ids["system_id"]), kind="to_be", perspective="executive")
    r = fde.get(f"{base}/flows/{flow['id']}/export.json")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    doc = json.loads(r.content)
    assert doc["kind"] == "flowdesk_flow" and doc["flow"]["kind"] == "to_be"
    mmd = fde.get(f"{base}/flows/{flow['id']}/export.mmd")
    assert mmd.status_code == 200 and f'[("ERP {world.a.code}")]' in mmd.text
    assert world.a.client_user.get(f"{base}/flows/{flow['id']}/export.json").status_code == 403
    assert world.a.client_admin.get(f"{base}/flows/{flow['id']}/export.mmd").status_code == 200

    imported = fde.post(f"{base}/flows/import", json={"engagement_id": world.a.ids["engagement_id"], "document": doc})
    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["id"] != flow["id"] and body["perspective"] == "executive" and body["graph"] == flow["graph"]

    b_import = world.b.fde.post(
        f"/api/v1/t/{world.b.tenant_id}/flowdesk/flows/import",
        json={"engagement_id": world.b.ids["engagement_id"], "document": doc},
    )
    assert b_import.status_code == 201
    assert [n["system_id"] for n in b_import.json()["graph"]["nodes"]] == [None, None, None, None]
    assert (
        fde.post(
            f"{base}/flows/import", json={"engagement_id": world.a.ids["engagement_id"], "document": {}}
        ).status_code
        == 422
    )
    assert "flowdesk.flow_export" in _actions(world) and "flowdesk.flow_import" in _actions(world)


# --- generation ----------------------------------------------------------------

GENERATED = {
    "lanes": ["영업", "생산"],
    "nodes": [
        {"id": "n1", "type": "start", "label": "시작", "lane": "영업"},
        {"id": "n2", "type": "task", "label": "수주 접수", "lane": "영업", "system": "erp {code}"},
        {"id": "n3", "type": "Decision", "label": "재고?", "lane": "생산"},
        {"id": "n4", "type": "gateway", "label": "긴급 생산", "lane": "품질"},
        {"id": "n4", "type": "task", "label": "중복"},
        {"id": "n5", "type": "end", "label": "종료", "lane": "생산"},
    ],
    "edges": [
        {"source": "n1", "target": "n2"},
        {"source": "n2", "target": "n3"},
        {"source": "n3", "target": "n5", "label": "있음"},
        {"source": "n3", "target": "n4", "label": "없음"},
        {"source": "n4", "target": "zz"},
    ],
}


def _generated(world: World) -> str:
    code = world.a.ids["system_id"]
    name = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/systems/{code}").json()["name"]
    return json.dumps(GENERATED, ensure_ascii=False).replace("erp {code}", name.lower())


def _gen_body(world: World, **extra: Any) -> dict[str, Any]:
    return {
        "engagement_id": world.a.ids["engagement_id"],
        "title": "생성 흐름",
        "perspective": "developer",
        "description": "주문을 받아 생산 후 출하한다.",
        "insight_ids": [world.a.ids["insight_id"]],
        **extra,
    }


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


def test_insight_options_are_engagement_and_tenant_scoped(world: World) -> None:
    r = world.a.fde.get(f"{_base(world)}/insights", params={"engagement_id": world.a.ids["engagement_id"]})
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == [world.a.ids["insight_id"]]
    other = world.a.fde.get(f"{_base(world)}/insights", params={"engagement_id": world.b.ids["engagement_id"]})
    assert other.json() == []


def test_prompt_contains_perspective_inputs_and_schema(world: World) -> None:
    r = world.a.fde.post(f"{_base(world)}/generate/prompt", json=_gen_body(world))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_available"] is False
    prompt = body["prompt"]
    assert "Developer:" in prompt and "생성 흐름" in prompt and "주문을 받아" in prompt
    assert f"Insight {world.a.code}" in prompt and f"ERP {world.a.code}" in prompt
    assert "JSON Schema" in prompt and "Korean" in prompt
    executive = world.a.fde.post(f"{_base(world)}/generate/prompt", json=_gen_body(world, perspective="executive"))
    assert "Executive:" in executive.json()["prompt"] and "Developer:" not in executive.json()["prompt"]


def test_prompt_rejects_missing_input_and_foreign_insights(world: World) -> None:
    empty = world.a.fde.post(f"{_base(world)}/generate/prompt", json=_gen_body(world, description="", insight_ids=[]))
    assert empty.status_code == 422
    foreign = _gen_body(world, insight_ids=[world.b.ids["insight_id"]])
    assert world.a.fde.post(f"{_base(world)}/generate/prompt", json=foreign).status_code == 422
    assert world.a.client_user.post(f"{_base(world)}/generate/prompt", json=_gen_body(world)).status_code == 403


def test_copy_mode_answer_becomes_normalised_flow(world: World) -> None:
    r = world.a.fde.post(f"{_base(world)}/generate", json=_gen_body(world, answer=f"```json\n{_generated(world)}\n```"))
    assert r.status_code == 201, r.text
    flow = r.json()
    graph = flow["graph"]
    assert flow["perspective"] == "developer" and flow["title"] == "생성 흐름"
    assert graph["lanes"] == ["영업", "생산", "품질"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert list(nodes) == ["n1", "n2", "n3", "n4", "n5"]
    assert nodes["n2"]["system_id"] == world.a.ids["system_id"]
    assert nodes["n3"]["type"] == "decision" and nodes["n4"]["type"] == "task"
    assert [(e["source"], e["target"], e["label"]) for e in graph["edges"]] == [
        ("n1", "n2", None),
        ("n2", "n3", None),
        ("n3", "n5", "있음"),
        ("n3", "n4", "없음"),
    ]
    xs = {k: v["position"]["x"] for k, v in nodes.items()}
    assert xs["n1"] < xs["n2"] < xs["n3"] < xs["n5"]
    assert len({(v["position"]["x"], v["position"]["y"]) for v in nodes.values()}) == 5
    assert "flowdesk.flow_generate" in _actions(world)


def test_copy_mode_invalid_answer(world: World) -> None:
    for answer in ("설명만 있음", '{"nodes": []}'):
        r = world.a.fde.post(f"{_base(world)}/generate", json=_gen_body(world, answer=answer))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "flow_result_invalid"


def test_llm_mode_disabled_then_generates(
    world: World, adapters_allowed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"{_base(world)}/generate"
    disabled = world.a.fde.post(url, json=_gen_body(world))
    assert disabled.status_code == 409 and disabled.json()["error"]["code"] == "adapter_disabled"
    aid = world.a.ids["activation_id"]
    approve = world.a.client_admin.post(
        f"/api/v1/t/{world.a.tenant_id}/adapters/activations/{aid}/approve", json={"acknowledged_egress": True}
    )
    assert approve.status_code == 200, approve.text
    assert world.a.fde.post(f"{url}/prompt", json=_gen_body(world)).json()["llm_available"] is True
    fake = FakeTransport([_generated(world)])
    monkeypatch.setattr(LLM, "transport", fake)
    r = world.a.fde.post(url, json=_gen_body(world))
    assert r.status_code == 201, r.text
    assert len(r.json()["graph"]["nodes"]) == 5
    assert "Developer:" in fake.prompts[0] and "JSON Schema" in fake.prompts[0]
