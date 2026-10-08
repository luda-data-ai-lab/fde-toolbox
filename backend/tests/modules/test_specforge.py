import io
import zipfile

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.llm import LlmConfig
from app.adapters.registry import LLM
from app.config import get_settings
from app.core.audit.models import AuditLog
from tests.conftest import World


def _base(world: World) -> str:
    return f"/api/v1/t/{world.a.tenant_id}/specforge"


def _assets(world: World) -> tuple[dict[str, object], dict[str, object]]:
    base = _base(world)
    templates = {t["doc"]: t for t in world.a.fde.get(f"{base}/templates").json()}
    packs = world.a.fde.get(f"{base}/rule-packs").json()
    return templates, packs[0]


def _create(world: World, **body: object) -> dict[str, object]:
    payload = {"engagement_id": world.a.ids["engagement_id"], "doc_type": "spec", "title": "Spec"} | body
    r = world.a.fde.post(f"{_base(world)}/documents", json=payload)
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_templates_and_rule_packs_listed(world: World) -> None:
    templates, pack = _assets(world)
    assert set(templates) == {"spec", "devin"}
    assert [s["key"] for s in templates["devin"]["sections"]][:2] == ["goal", "rules"]
    assert len(pack["rules"]) == 5


def test_spec_assembly_includes_selected_sources(world: World) -> None:
    ids = world.a.ids
    doc = _create(
        world,
        sources={
            "discovery_session_ids": [ids["session_id"]],
            "flow_ids": [ids["flow_id"]],
            "interfaces": True,
            "glossary": True,
            "requirements": "주문 처리 시간을 절반으로 줄인다.",
        },
    )
    md = str(doc["content_md"])
    assert md.startswith("# Spec\n")
    assert "주문 처리 시간을 절반으로 줄인다." in md
    assert "| Term TA |" in md and "TTA (QA)" in md
    assert "**Flow TA**" in md and "관련 시스템:" in md
    assert "| IF-TA-001 |" in md
    assert "**Interview TA**" in md and "- Insight TA" in md
    assert "## 3. 역할과 권한\n\n> TODO: 역할별 기능 허용 표를 작성한다." in md
    assert "TB" not in md
    assert doc["status"] == "draft" and doc["template_ref"] is not None


def test_devin_assembly_inserts_rules_and_glossary_directive(world: World) -> None:
    templates, pack = _assets(world)
    ref = {"asset_id": pack["asset_id"], "version": pack["version"]}
    doc = _create(
        world,
        doc_type="devin",
        title="Devin",
        rule_pack_refs=[ref],
        sources={"glossary": True, "discovery_session_ids": [world.a.ids["session_id"]]},
    )
    md = str(doc["content_md"])
    rules = md.split("## 2.")[1]
    assert "명세에 없는 기능이나 외부 호출을 추가하지 않는다." in rules
    assert "용어 사전의 표준 용어를 따른다" in md and "| Term TA |" in md
    assert "| Action TA |" in md
    assert doc["template_ref"] == {"asset_id": templates["devin"]["asset_id"], "version": 1}
    # Devin template is rejected for a Spec document.
    spec_ref = {"asset_id": templates["devin"]["asset_id"], "version": 1}
    r = world.a.fde.post(
        f"{_base(world)}/documents",
        json={
            "engagement_id": world.a.ids["engagement_id"],
            "doc_type": "spec",
            "title": "x",
            "template_ref": spec_ref,
        },
    )
    assert r.status_code == 422


def test_foreign_or_other_engagement_sources_rejected(world: World) -> None:
    base = _base(world)
    eng = world.a.ids["engagement_id"]
    for sources in (
        {"flow_ids": [world.b.ids["flow_id"]]},
        {"discovery_session_ids": [world.b.ids["session_id"]]},
    ):
        r = world.a.fde.post(
            f"{base}/documents", json={"engagement_id": eng, "doc_type": "spec", "title": "x", "sources": sources}
        )
        assert r.status_code == 422, sources
    other = world.a.fde.post(f"/api/v1/t/{world.a.tenant_id}/engagements", json={"name": "Other"}).json()["id"]
    r = world.a.fde.post(
        f"{base}/documents",
        json={
            "engagement_id": other,
            "doc_type": "spec",
            "title": "x",
            "sources": {"flow_ids": [world.a.ids["flow_id"]]},
        },
    )
    assert (r.status_code, r.json()["error"]["detail"]["field"]) == (422, "sources.flow_ids")


def test_versions_diff_restore_and_confirm(world: World, db: Session) -> None:
    base = f"{_base(world)}/documents"
    doc = _create(world)
    url = f"{base}/{doc['id']}"
    v1 = world.a.fde.post(f"{url}/versions", json={"note": "draft"}).json()
    assert v1["version"] == 1
    edited = str(doc["content_md"]).replace("> TODO: 보안", "- 외부 통신 없음\n> TODO: 보안")
    assert world.a.fde.patch(url, json={"content_md": edited}).status_code == 200
    d = world.a.fde.get(f"{url}/diff", params={"from_version": 1}).json()
    assert (d["from_label"], d["to_label"]) == ("v1", "working") and "+- 외부 통신 없음" in d["diff"]
    v2 = world.a.fde.post(f"{url}/versions", json={}).json()
    assert v2["version"] == 2
    d = world.a.fde.get(f"{url}/diff", params={"from_version": 1, "to_version": 2}).json()
    assert d["to_label"] == "v2" and "+- 외부 통신 없음" in d["diff"]
    assert world.a.fde.get(f"{url}/diff", params={"from_version": 9}).status_code == 404
    listed = world.a.fde.get(f"{url}/versions").json()
    assert [v["version"] for v in listed] == [2, 1]
    assert world.a.fde.get(f"{url}/versions/{v1['id']}").json()["content_md"] == doc["content_md"]
    restored = world.a.fde.post(f"{url}/versions/{v1['id']}/restore").json()
    assert restored["content_md"] == doc["content_md"] and restored["version_count"] == 2
    # Version ids are scoped to their document.
    other = _create(world, title="Other")
    assert world.a.fde.get(f"{base}/{other['id']}/versions/{v1['id']}").status_code == 404
    confirmed = world.a.fde.patch(url, json={"status": "confirmed"}).json()
    assert confirmed["status"] == "confirmed"
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.target_id == doc["id"])).all())
    assert {"specforge.document_create", "specforge.document_update", "specforge.version_restore"} <= actions


def test_reassemble_picks_up_new_sources(world: World) -> None:
    doc = _create(world)
    url = f"{_base(world)}/documents/{doc['id']}"
    assert "| Term TA |" not in str(doc["content_md"])
    world.a.fde.patch(url, json={"sources": {"glossary": True}})
    md = world.a.fde.post(f"{url}/assemble").json()["content_md"]
    assert "| Term TA |" in md


def test_exports_markdown_and_zip(world: World) -> None:
    base = f"{_base(world)}/documents"
    spec = _create(world)
    devin = _create(world, doc_type="devin", title="Devin")
    r = world.a.fde.get(f"{base}/{spec['id']}/export.md")
    assert r.status_code == 200 and "Spec.md" in r.headers["content-disposition"]
    assert r.text == spec["content_md"]
    r = world.a.fde.get(f"{base}/export.zip", params={"engagement_id": world.a.ids["engagement_id"]})
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert sorted(names) == ["Devin.md", "Spec-2.md", "Spec.md"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert devin["content_md"] in [zf.read(n).decode() for n in zf.namelist()]
        assert all("TB" not in zf.read(n).decode() for n in zf.namelist())


def test_permissions(world: World) -> None:
    base = f"{_base(world)}/documents"
    doc_id = world.a.ids["document_id"]
    for client in (world.a.client_admin, world.a.client_user):
        assert client.get(f"{base}/{doc_id}").status_code == 200
        assert client.get(f"{base}/{doc_id}/versions").status_code == 200
        assert client.patch(f"{base}/{doc_id}", json={"title": "x"}).status_code == 403
        assert client.post(f"{base}/{doc_id}/versions", json={}).status_code == 403
        assert client.post(f"{base}/{doc_id}/enrich-prompt", json={}).status_code == 403
    assert world.a.client_user.get(f"{base}/{doc_id}/export.md").status_code == 403
    assert world.a.client_admin.get(f"{base}/{doc_id}/export.md").status_code == 200


def test_enrich_prompt_copy_mode_offline(world: World) -> None:
    url = f"{_base(world)}/documents/{world.a.ids['document_id']}"
    r = world.a.fde.post(f"{url}/enrich-prompt", json={"instructions": "보안 섹션을 채워라"})
    body = r.json()
    assert body["llm_available"] is False
    assert (
        "--- DRAFT ---" in body["prompt"] and "# Spec TA" in body["prompt"] and "보안 섹션을 채워라" in body["prompt"]
    )
    r = world.a.fde.post(f"{url}/enrich", json={})
    assert r.status_code == 409


class FakeTransport:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, config: LlmConfig, api_key: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def test_enrich_with_active_llm_returns_unsaved_draft(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "adapters_allowed", True)
    aid = world.a.ids["activation_id"]
    r = world.a.client_admin.post(
        f"/api/v1/t/{world.a.tenant_id}/adapters/activations/{aid}/approve", json={"acknowledged_egress": True}
    )
    assert r.status_code == 200, r.text
    fake = FakeTransport("# Spec TA\n\n## 1. 개요\n\n다듬은 내용")
    monkeypatch.setattr(LLM, "transport", fake)
    url = f"{_base(world)}/documents/{world.a.ids['document_id']}"
    assert world.a.fde.post(f"{url}/enrich-prompt", json={}).json()["llm_available"] is True
    r = world.a.fde.post(f"{url}/enrich", json={})
    assert r.status_code == 200, r.text
    assert r.json()["content_md"].endswith("다듬은 내용\n")
    assert "# Spec TA" in fake.prompts[0]
    assert world.a.fde.get(url).json()["content_md"] != r.json()["content_md"]
