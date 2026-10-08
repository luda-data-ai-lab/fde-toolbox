import io
import json
import zipfile
from collections.abc import Iterator

import pytest
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.base import AdapterDisabled
from app.adapters.llm import LlmConfig
from app.adapters.registry import LLM, get_llm
from app.config import get_settings
from app.core.adapters.models import AdapterActivation
from app.core.audit.models import AuditLog
from app.core.crypto import DecryptionError, decrypt_json, encrypt_json
from app.core.prompting import ResultParseError, parse_json_result
from app.core.tenancy.context import Principal, TenantContext
from app.core.users.models import User
from app.db.session import TENANT_KEY
from tests.conftest import World, login, make_user


class Flow(BaseModel):
    steps: list[str]


class FakeTransport:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []
        self.keys: list[str] = []

    def complete(self, prompt: str, *, config: LlmConfig, api_key: str) -> str:
        self.prompts.append(prompt)
        self.keys.append(api_key)
        return self.replies.pop(0)


@pytest.fixture
def allowed() -> Iterator[None]:
    settings = get_settings()
    prev, settings.adapters_allowed = settings.adapters_allowed, True
    yield
    settings.adapters_allowed = prev


def _base(world: World) -> str:
    return f"/api/v1/t/{world.a.tenant_id}/adapters"


def _activate(world: World) -> str:
    aid = world.a.ids["activation_id"]
    r = world.a.client_admin.post(f"{_base(world)}/activations/{aid}/approve", json={"acknowledged_egress": True})
    assert r.status_code == 200, r.text
    return aid


def _ctx(db: Session, world: World) -> TenantContext:
    db.info[TENANT_KEY] = world.a.tenant_id
    user = db.scalars(select(User).where(User.id == world.a.fde_id)).one()
    return TenantContext(Principal(user, None, frozenset({world.a.tenant_id})), world.a.tenant_id)


def test_disabled_by_default(world: World, db: Session) -> None:
    assert get_settings().adapters_allowed is False
    assert world.a.fde.get("/api/v1/auth/me").json()["adapters_allowed"] is False
    assert world.a.fde.get(_base(world)).json() == []
    r = world.a.fde.post(f"{_base(world)}/activations", json={"adapter_key": "llm", "credentials": {"api_key": "k"}})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "adapters_not_allowed"
    with pytest.raises(AdapterDisabled) as exc:
        get_llm(_ctx(db, world), db)
    assert exc.value.reason == "not_allowed"


def test_request_stores_encrypted_credentials_and_notice(world: World, db: Session, allowed: None) -> None:
    adapters = {a["key"]: a for a in world.a.client_user.get(_base(world)).json()}
    assert set(adapters) == {"llm", "agent_runtime", "git"}
    llm = adapters["llm"]
    assert llm["egress_notice"]["destination"] == "api.anthropic.com"
    assert "flowdesk_generate" in llm["egress_notice"]["features"]
    assert llm["activation"]["status"] == "requested"
    assert llm["activation"]["has_credentials"] is True
    assert llm["activation"]["config"] == {"model": "test-model", "max_tokens": 4096, "timeout_seconds": 60}
    assert "k-TA" not in json.dumps(llm)
    _ctx(db, world)
    row = db.get(AdapterActivation, world.a.ids["activation_id"])
    assert row is not None and row.credentials_encrypted is not None
    assert "k-TA" not in row.credentials_encrypted
    assert decrypt_json(row.credentials_encrypted) == {"api_key": "k-TA"}
    assert adapters["git"]["implemented"] is False
    assert adapters["git"]["activation"] is None


def test_request_validation_and_roles(world: World, allowed: None) -> None:
    url = f"{_base(world)}/activations"
    body = {"adapter_key": "llm", "config": {"model": "m"}, "credentials": {"api_key": "k"}}
    for client in (world.a.client_admin, world.a.client_user):
        assert client.post(url, json=body).status_code == 403
    r = world.a.fde.post(url, json={**body, "credentials": {}})
    assert (r.status_code, r.json()["error"]["detail"]) == (422, {"field": "api_key"})
    r = world.a.fde.post(url, json={**body, "config": {"model": "m", "max_tokens": 0}})
    assert (r.status_code, r.json()["error"]["detail"]) == (422, {"field": "max_tokens"})
    r = world.a.fde.post(url, json={**body, "adapter_key": "git"})
    assert (r.status_code, r.json()["error"]["code"]) == (422, "adapter_not_implemented")
    assert world.a.fde.post(url, json={**body, "adapter_key": "nope"}).status_code == 404


def test_approval_flow_and_audit(world: World, db: Session, allowed: None) -> None:
    aid = world.a.ids["activation_id"]
    approve = f"{_base(world)}/activations/{aid}/approve"
    assert world.a.fde.post(approve, json={"acknowledged_egress": True}).status_code == 403
    assert world.a.client_user.post(approve, json={"acknowledged_egress": True}).status_code == 403
    r = world.admin.post(approve, json={"acknowledged_egress": True, "reason": "no customer admin"})
    assert (r.status_code, r.json()["error"]["code"]) == (403, "client_admin_approval_required")
    assert world.a.client_admin.post(approve, json={"acknowledged_egress": False}).status_code == 422
    _activate(world)
    out = world.a.fde.get(f"{_base(world)}/activations/{aid}").json()
    assert out["status"] == "active" and out["approved_at"] is not None
    assert world.a.client_admin.post(approve, json={"acknowledged_egress": True}).status_code == 409
    r = world.a.fde.post(
        f"{_base(world)}/activations",
        json={"adapter_key": "llm", "config": {"model": "m"}, "credentials": {"api_key": "k"}},
    )
    assert r.json()["error"]["code"] == "adapter_already_active"
    logs = db.scalars(select(AuditLog).where(AuditLog.tenant_id == world.a.tenant_id)).all()
    actions = [log.action for log in logs]
    assert {"adapter.request", "adapter.approve"} <= set(actions)
    assert all("k-TA" not in json.dumps(log.detail) for log in logs)
    b = world.b.fde.get(f"/api/v1/t/{world.b.tenant_id}/adapters/activations/{world.b.ids['activation_id']}").json()
    assert b["status"] == "requested"


def test_luda_admin_approves_with_reason_without_client_admin(world: World, db: Session, allowed: None) -> None:
    db.execute(update(User).where(User.home_tenant_id == world.a.tenant_id).values(is_active=False))
    db.commit()
    approve = f"{_base(world)}/activations/{world.a.ids['activation_id']}/approve"
    r = world.admin.post(approve, json={"acknowledged_egress": True})
    assert (r.status_code, r.json()["error"]["code"]) == (422, "approval_reason_required")
    r = world.admin.post(approve, json={"acknowledged_egress": True, "reason": "standalone install"})
    assert r.status_code == 200, r.text
    assert r.json()["approval_reason"] == "standalone install"


def test_reject_and_deactivate_clear_credentials(world: World, db: Session, allowed: None) -> None:
    aid = world.a.ids["activation_id"]
    act = f"{_base(world)}/activations/{aid}"
    assert world.a.client_user.post(f"{act}/deactivate", json={}).status_code == 403
    r = world.a.client_admin.post(f"{act}/reject", json={"reason": "not now"})
    assert r.json()["status"] == "disabled" and r.json()["has_credentials"] is False
    assert world.a.client_admin.post(f"{act}/reject", json={}).status_code == 409
    world.a.fde.post(
        f"{_base(world)}/activations",
        json={"adapter_key": "llm", "config": {"model": "m"}, "credentials": {"api_key": "k2"}},
    )
    _activate(world)
    r = world.a.client_admin.post(f"{act}/deactivate", json={})
    assert r.json()["status"] == "disabled"
    assert world.a.fde.post(f"{act}/deactivate", json={}).status_code == 409
    with pytest.raises(AdapterDisabled) as exc:
        get_llm(_ctx(db, world), db)
    assert exc.value.reason == "not_active"
    actions = db.scalars(select(AuditLog.action).where(AuditLog.target_id == aid)).all()
    assert actions.count("adapter.request") == 2
    assert {"adapter.reject", "adapter.deactivate"} <= set(actions)


def test_llm_generate_json_retries_once_and_audits_calls(
    world: World, db: Session, allowed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(AdapterDisabled):
        get_llm(_ctx(db, world), db)
    aid = _activate(world)
    fake = FakeTransport(["not json", '```json\n{"steps": ["a", "b"]}\n```'])
    monkeypatch.setattr(LLM, "transport", fake)
    result = get_llm(_ctx(db, world), db).generate_json("draw the flow", Flow, feature="flowdesk_generate")
    assert result.steps == ["a", "b"]
    assert fake.keys == ["k-TA", "k-TA"]
    assert "JSON Schema" in fake.prompts[0] and "rejected" in fake.prompts[1]
    calls = db.scalars(
        select(AuditLog).where(AuditLog.action == "adapter.call", AuditLog.target_id == aid).order_by(AuditLog.at)
    ).all()
    assert len(calls) == 2
    assert calls[0].detail["feature"] == "flowdesk_generate"
    assert calls[0].detail["request_bytes"] == len(fake.prompts[0].encode())
    assert calls[0].detail["result"] == "ok"
    assert all("draw the flow" not in json.dumps(c.detail) for c in calls)

    monkeypatch.setattr(LLM, "transport", FakeTransport(["{}", '{"steps": 1}']))
    with pytest.raises(Exception) as exc:
        get_llm(_ctx(db, world), db).generate_json("x", Flow, feature="flowdesk_generate")
    assert getattr(exc.value, "code", None) == "llm_invalid_response"


def test_health_check_route(world: World, allowed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    aid = world.a.ids["activation_id"]
    url = f"{_base(world)}/activations/{aid}/health-check"
    r = world.a.fde.post(url)
    assert (r.status_code, r.json()["error"]["detail"]["reason"]) == (409, "not_active")
    _activate(world)
    monkeypatch.setattr(LLM, "transport", FakeTransport(["OK"]))
    assert world.a.client_admin.post(url).status_code == 403
    r = world.a.fde.post(url)
    assert r.status_code == 200 and r.json()["ok"] is True


def test_tenant_export_drops_credentials(world: World, db: Session, allowed: None) -> None:
    _activate(world)
    bundle = world.a.fde.get(f"/api/v1/t/{world.a.tenant_id}/export").content
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(bundle)).read("manifest.json"))
    rows = manifest["tables"]["adapter_activations"]
    assert rows[0]["status"] == "active" and rows[0]["credentials_encrypted"] is None
    r = world.admin.post(
        "/api/v1/admin/tenants/import",
        files={"file": ("a.zip", bundle, "application/zip")},
        data={"code": "TA-COPY"},
    )
    assert r.status_code == 201, r.text
    make_user(db, "copy@luda.test", "fde", tenant_ids=[r.json()["id"]])
    copied = login("copy@luda.test").get(f"/api/v1/t/{r.json()['id']}/adapters").json()
    llm = next(a for a in copied if a["key"] == "llm")
    assert llm["activation"]["status"] == "disabled" and llm["activation"]["has_credentials"] is False


def test_crypto_roundtrip_and_tamper() -> None:
    token = encrypt_json({"api_key": "secret"})
    assert "secret" not in token
    assert decrypt_json(token) == {"api_key": "secret"}
    with pytest.raises(DecryptionError):
        decrypt_json(token[:-4] + "AAAA")


def test_result_parser() -> None:
    assert parse_json_result('Here:\n{"steps": ["x"]} done', Flow).steps == ["x"]
    with pytest.raises(ResultParseError) as exc:
        parse_json_result("no json here", Flow)
    assert exc.value.reason == "no_json"
    with pytest.raises(ResultParseError) as exc:
        parse_json_result('{"steps": [1, {"a": 2}]}', Flow)
    assert exc.value.reason == "schema_mismatch" and exc.value.errors
