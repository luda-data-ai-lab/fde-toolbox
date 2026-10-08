import json
from typing import Any

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
