import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.core.assets.models import AssetItem
from app.core.systems.models import System
from app.core.tenants.models import Tenant
from app.core.users.models import User
from app.db.session import guard_bypass
from app.modules.agenthub.models import AgentEvalCase, AgentInstance


def test_init_admin_and_seeds(db: Session, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["seed-assets"])
    cli.main(["init-admin", "--email", "Root@Luda.Local", "--password", "root-pass-123"])
    assert db.scalars(select(User.email).where(User.role == "luda_admin")).all() == ["root@luda.local"]
    with pytest.raises(SystemExit):
        cli.main(["init-admin", "--email", "other@luda.local", "--password", "root-pass-123"])

    cli.main(["seed-assets"])
    cli.main(["seed-assets"])
    assert "0 created" in capsys.readouterr().out.splitlines()[-1]
    types = set(db.scalars(select(AssetItem.asset_type)).all())
    assert types == {
        "question_bank",
        "flow_template",
        "if_template",
        "upper_ontology",
        "glossary_template",
        "spec_template",
        "rule_pack",
        "agent_template",
    }
    qb = db.scalars(select(AssetItem).where(AssetItem.asset_type == "question_bank")).one()
    assert len(qb.payload["categories"]) == 8
    assert all(len(c["questions"]) >= 8 for c in qb.payload["categories"])
    onto = db.scalars(select(AssetItem).where(AssetItem.asset_type == "upper_ontology")).one()
    assert len(onto.payload["concepts"]) == 20
    assert len(db.scalars(select(AgentEvalCase)).all()) == 3

    cli.main(["seed-demo", "--password", "demo-pass-123"])
    tenant = db.scalars(select(Tenant).where(Tenant.code == "DEMO")).one()
    assert tenant.name == "데모 제조사"
    with guard_bypass(db):
        assert db.scalars(select(System).where(System.tenant_id == tenant.id)).all().__len__() == 6
        assert db.scalars(select(AgentInstance)).one().tenant_id == tenant.id
    with pytest.raises(SystemExit):
        cli.main(["seed-demo"])


def test_password_required_non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FDE_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit, match="password required"):
        cli.main(["init-admin", "--email", "a@b.c"])
