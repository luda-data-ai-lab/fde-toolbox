"""Phase 2 acceptance: insight → flow → Spec.md → DevTracker project in one engagement, LLM adapter off and on."""

import json
from collections.abc import Iterator

import pytest

from app.adapters.llm import LlmConfig
from app.adapters.registry import LLM
from app.config import get_settings
from tests.conftest import World

ANSWER = {
    "lanes": ["영업", "생산"],
    "nodes": [
        {"id": "n1", "type": "start", "label": "주문 시작", "lane": "영업"},
        {"id": "n2", "type": "task", "label": "주문 등록", "lane": "영업"},
        {"id": "n3", "type": "end", "label": "생산 지시", "lane": "생산"},
    ],
    "edges": [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}],
}


class FakeTransport:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, config: LlmConfig, api_key: str) -> str:
        self.prompts.append(prompt)
        return self.replies.pop(0)


@pytest.fixture
def adapters_allowed() -> Iterator[None]:
    settings = get_settings()
    prev, settings.adapters_allowed = settings.adapters_allowed, True
    yield
    settings.adapters_allowed = prev


def _chain(world: World, *, llm: FakeTransport | None) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}"
    fde = world.a.fde
    eng = world.a.ids["engagement_id"]
    session = fde.post(f"{base}/discoveryq/sessions", json={"engagement_id": eng, "title": "인수 인터뷰"}).json()
    insight = fde.post(
        f"{base}/discoveryq/sessions/{session['id']}/insights", json={"text": "수주를 두 번 입력한다"}
    ).json()

    gen = {"engagement_id": eng, "title": "인수 흐름", "perspective": "business", "insight_ids": [insight["id"]]}
    prompt = fde.post(f"{base}/flowdesk/generate/prompt", json=gen).json()
    assert prompt["llm_available"] is (llm is not None)
    assert "수주를 두 번 입력한다" in prompt["prompt"]
    if llm is None:
        gen["answer"] = json.dumps(ANSWER, ensure_ascii=False)
    r = fde.post(f"{base}/flowdesk/generate", json=gen)
    assert r.status_code == 201, r.text
    flow = r.json()

    r = fde.post(
        f"{base}/specforge/documents",
        json={
            "engagement_id": eng,
            "doc_type": "spec",
            "title": "인수 명세",
            "sources": {"discovery_session_ids": [session["id"]], "flow_ids": [flow["id"]]},
        },
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert "인수 흐름" in doc["content_md"] and "수주를 두 번 입력한다" in doc["content_md"]
    url = f"{base}/specforge/documents/{doc['id']}"
    enrich = fde.post(f"{url}/enrich-prompt", json={}).json()
    assert enrich["llm_available"] is (llm is not None)
    content = fde.post(f"{url}/enrich", json={}).json()["content_md"] if llm else doc["content_md"] + "\n보강\n"
    assert fde.patch(url, json={"content_md": content}).status_code == 200
    assert fde.post(f"{url}/versions", json={"note": "인수"}).status_code == 201

    project = {"engagement_id": eng, "name": "인수 프로젝트", "spec_document_ids": [doc["id"]]}
    draft = fde.post(f"{base}/devtracker/projects", json=project)
    assert (draft.status_code, draft.json()["error"]["code"]) == (422, "invalid_reference")
    assert fde.patch(url, json={"status": "confirmed"}).json()["status"] == "confirmed"
    assert world.a.client_user.post(f"{base}/devtracker/projects", json=project).status_code == 403
    assert world.b.fde.post(f"/api/v1/t/{world.b.tenant_id}/devtracker/projects", json=project).status_code == 422
    r = fde.post(f"{base}/devtracker/projects", json=project)
    assert r.status_code == 201, r.text
    assert r.json()["spec_document_ids"] == [doc["id"]]
    assert world.b.fde.get(f"{base}/devtracker/projects/{r.json()['id']}").status_code in (403, 404)


def test_chain_with_adapter_off_uses_prompt_copy(world: World) -> None:
    _chain(world, llm=None)


def test_chain_with_adapter_on_uses_llm(world: World, adapters_allowed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    aid = world.a.ids["activation_id"]
    r = world.a.client_admin.post(
        f"/api/v1/t/{world.a.tenant_id}/adapters/activations/{aid}/approve", json={"acknowledged_egress": True}
    )
    assert r.status_code == 200, r.text
    fake = FakeTransport([json.dumps(ANSWER, ensure_ascii=False), "# 인수 명세\n\nLLM 보강"])
    monkeypatch.setattr(LLM, "transport", fake)
    _chain(world, llm=fake)
    assert len(fake.prompts) == 2 and not fake.replies
