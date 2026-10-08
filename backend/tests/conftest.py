import json
import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_TMP = Path(tempfile.mkdtemp(prefix="fde-test-"))
os.environ.setdefault("SECRET_KEY", "test-secret-key-please-change-0123456789")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-please-change")
os.environ["APP_ENV"] = "test"
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP / 'test.db'}"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.db.models  # noqa: E402, F401
from app.config import get_settings  # noqa: E402
from app.core.users.schemas import UserIn  # noqa: E402
from app.core.users.service import create_user_record  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import configure_engine, new_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.interfaces.excel import build_workbook  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "password-1234"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = configure_engine(get_settings().database_url)
    with eng.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete()) if eng.dialect.has_table(conn, table.name) else None
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_db(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    s = new_session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def app_client(engine: Engine) -> TestClient:
    return TestClient(create_app())


def make_user(
    db: Session, email: str, role: str, home_tenant_id: str | None = None, tenant_ids: list[str] | None = None
) -> str:
    user = create_user_record(
        db,
        UserIn(
            email=email,
            name=email.split("@")[0],
            role=role,
            password=PASSWORD,  # type: ignore[arg-type]
            home_tenant_id=home_tenant_id,
            tenant_ids=tenant_ids or [],
        ),
        None,
    )
    db.commit()
    return user.id


def login(email: str) -> TestClient:
    client = TestClient(create_app())
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def admin(db: Session) -> TestClient:
    make_user(db, "admin@luda.test", "luda_admin")
    return login("admin@luda.test")


@dataclass
class TenantWorld:
    tenant_id: str
    code: str
    fde: TestClient
    client_admin: TestClient
    client_user: TestClient
    fde_id: str
    ids: dict[str, str] = field(default_factory=dict)


@dataclass
class World:
    admin: TestClient
    a: TenantWorld
    b: TenantWorld
    template: dict[str, Any]


def _ok(r: Any, status: int = 201) -> dict[str, Any]:
    assert r.status_code == status, r.text
    body: dict[str, Any] = r.json()
    return body


def build_tenant(admin: TestClient, db: Session, code: str, template: dict[str, Any]) -> TenantWorld:
    t = _ok(admin.post("/api/v1/admin/tenants", json={"name": f"Tenant {code}", "code": code}))
    tid = t["id"]
    fde_id = make_user(db, f"fde-{code}@luda.test".lower(), "fde", tenant_ids=[tid])
    make_user(db, f"cadmin-{code}@client.test".lower(), "client_admin", home_tenant_id=tid)
    make_user(db, f"cuser-{code}@client.test".lower(), "client_user", home_tenant_id=tid)
    fde = login(f"fde-{code}@luda.test".lower())
    base = f"/api/v1/t/{tid}"
    ids: dict[str, str] = {}
    ids["engagement_id"] = _ok(fde.post(f"{base}/engagements", json={"name": f"Eng {code}"}))["id"]
    ids["system_id"] = _ok(fde.post(f"{base}/systems", json={"name": f"ERP {code}", "type": "ERP"}))["id"]
    ids["file_id"] = _ok(
        fde.post(f"{base}/files", files={"file": (f"note-{code}.txt", f"secret of {code}".encode(), "text/plain")})
    )["id"]
    ids["project_id"] = _ok(
        fde.post(f"{base}/devtracker/projects", json={"engagement_id": ids["engagement_id"], "name": f"Proj {code}"})
    )["id"]
    ids["task_id"] = _ok(
        fde.post(f"{base}/devtracker/projects/{ids['project_id']}/tasks", json={"title": f"Task {code}"})
    )["id"]
    ids["prompt_id"] = _ok(
        fde.post(f"{base}/devtracker/tasks/{ids['task_id']}/prompts", json={"tool": "devin", "prompt": f"p {code}"})
    )["id"]
    ids["interface_id"] = _ok(
        fde.post(
            f"{base}/interfaces",
            json={
                "if_code": f"IF-{code}-001",
                "name": f"I/F {code}",
                "source_system_id": ids["system_id"],
                "target_system_id": ids["system_id"],
            },
        )
    )["id"]
    workbook = build_workbook([[f"IF-{code}-002", "실적", f"ERP {code}", f"MES {code}"]], [])
    ids["upload_id"] = _ok(fde.post(f"{base}/interfaces/uploads", files={"file": ("if.xlsx", workbook, XLSX)}))["id"]
    discovery = f"{base}/discoveryq"
    ids["subject_id"] = _ok(
        fde.post(
            f"{discovery}/subjects",
            json={"engagement_id": ids["engagement_id"], "name": f"Kim {code}", "system_ids": [ids["system_id"]]},
        )
    )["id"]
    ids["custom_question_id"] = _ok(
        fde.post(f"{discovery}/custom-questions", json={"text": f"Custom question {code}", "category": "status"})
    )["id"]
    ids["session_id"] = _ok(
        fde.post(
            f"{discovery}/sessions",
            json={"engagement_id": ids["engagement_id"], "subject_id": ids["subject_id"], "title": f"Interview {code}"},
        )
    )["id"]
    ids["session_question_id"] = _ok(
        fde.post(
            f"{discovery}/sessions/{ids['session_id']}/questions",
            json={"custom_question_id": ids["custom_question_id"]},
        )
    )["id"]
    ids["insight_id"] = _ok(
        fde.post(
            f"{discovery}/sessions/{ids['session_id']}/insights",
            json={"text": f"Insight {code}", "session_question_id": ids["session_question_id"]},
        )
    )["id"]
    ids["action_item_id"] = _ok(
        fde.post(
            f"{discovery}/sessions/{ids['session_id']}/action-items",
            json={"title": f"Action {code}", "insight_id": ids["insight_id"]},
        )
    )["id"]
    onto = f"{base}/ontomap"
    ids["term_id"] = _ok(
        fde.post(f"{onto}/terms", json={"term": f"Term {code}", "aliases": [{"alias": f"T{code}", "department": "QA"}]})
    )["id"]
    ids["candidate_id"] = _ok(
        fde.post(
            f"{onto}/candidates",
            json={"name": f"Cand {code}", "source_type": "discovery_session", "source_id": ids["session_id"]},
        )
    )["id"]
    ref = {"asset_id": template["asset_id"], "version": 2}
    ids["run_id"] = _ok(
        fde.post(
            f"{base}/agenthub/eval-runs",
            json={
                "template_ref": ref,
                "results": [{"case_id": template["case_ids"][0], "passed": True}],
                "evidence_file_ids": [ids["file_id"]],
            },
        )
    )["id"]
    ids["instance_id"] = _ok(
        fde.post(
            f"{base}/agenthub/instances",
            json={
                "name": f"Agent {code}",
                "template_ref": ref,
                "engagement_id": ids["engagement_id"],
                "system_ids": [ids["system_id"]],
                "dev_project_id": ids["project_id"],
            },
        )
    )["id"]
    flows = f"{base}/flowdesk/flows"
    ids["flow_id"] = _ok(
        fde.post(
            flows,
            json={
                "engagement_id": ids["engagement_id"],
                "title": f"Flow {code}",
                "graph": {
                    "lanes": ["Sales"],
                    "nodes": [
                        {"id": "a", "type": "system", "label": "ERP", "lane": "Sales", "system_id": ids["system_id"]}
                    ],
                },
            },
        )
    )["id"]
    _ok(fde.post(f"{flows}/{ids['flow_id']}/pair", json={}))
    ids["snapshot_id"] = _ok(fde.post(f"{flows}/{ids['flow_id']}/snapshots", json={"note": f"v1 {code}"}))["id"]
    docs = f"{base}/specforge/documents"
    ids["document_id"] = _ok(
        fde.post(
            docs,
            json={
                "engagement_id": ids["engagement_id"],
                "doc_type": "spec",
                "title": f"Spec {code}",
                "sources": {
                    "discovery_session_ids": [ids["session_id"]],
                    "flow_ids": [ids["flow_id"]],
                    "glossary": True,
                },
            },
        )
    )["id"]
    ids["version_id"] = _ok(fde.post(f"{docs}/{ids['document_id']}/versions", json={"note": f"v1 {code}"}))["id"]
    settings = get_settings()
    allowed, settings.adapters_allowed = settings.adapters_allowed, True
    try:
        ids["activation_id"] = _ok(
            fde.post(
                f"{base}/adapters/activations",
                json={"adapter_key": "llm", "config": {"model": "test-model"}, "credentials": {"api_key": f"k-{code}"}},
            )
        )["id"]
    finally:
        settings.adapters_allowed = allowed
    return TenantWorld(
        tenant_id=tid,
        code=code,
        fde=fde,
        client_admin=login(f"cadmin-{code}@client.test".lower()),
        client_user=login(f"cuser-{code}@client.test".lower()),
        fde_id=fde_id,
        ids=ids,
    )


SEED_DIR = Path(__file__).resolve().parents[1] / "seeds" / "assets"
SPEC_SEEDS = ("doc-templates.json", "rule-pack-default.json")


def build_template(admin: TestClient) -> dict[str, Any]:
    v1 = _ok(
        admin.post(
            "/api/v1/assets",
            json={
                "asset_type": "agent_template",
                "asset_key": "daily-report",
                "title": "Daily report agent",
                "payload": {"system_prompt": "Summarise the daily production report."},
                "status": "published",
            },
        )
    )
    aid = v1["asset_id"]
    _ok(
        admin.post(
            f"/api/v1/assets/{aid}/versions",
            json={
                "payload": {"system_prompt": "Summarise the daily production report in Korean."},
                "status": "published",
                "change_note": "Korean output",
            },
        )
    )
    case_ids = [
        _ok(
            admin.post(
                f"/api/v1/assets/{aid}/versions/2/eval-cases",
                json={"name": f"case {i}", "input": "in", "expected": "out"},
            )
        )["id"]
        for i in range(2)
    ]
    return {"asset_id": aid, "case_ids": case_ids}


@pytest.fixture
def world(admin: TestClient, db: Session) -> World:
    template = build_template(admin)
    for name in SPEC_SEEDS:
        _ok(admin.post("/api/v1/assets/import", json=json.loads((SEED_DIR / name).read_text(encoding="utf-8"))), 200)
    return World(
        admin=admin,
        a=build_tenant(admin, db, "TA", template),
        b=build_tenant(admin, db, "TB", template),
        template=template,
    )
