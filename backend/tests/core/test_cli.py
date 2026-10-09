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
from app.modules.devtracker.models import DevIssue
from app.modules.discoveryq.models import DiscoveryInsight
from app.modules.exmigrate.models import XlErdDraft
from app.modules.flowdesk.models import Flow
from app.modules.interfaces.models import Interface, InterfaceUpload
from app.modules.ontomap.models import OntoCandidate, OntoConcept, OntoMapping, OntoTerm, OntoTermAlias
from app.modules.specforge.models import SpecDocument


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
        interfaces = db.scalars(select(Interface).where(Interface.tenant_id == tenant.id)).all()
        assert len(interfaces) == 15
        assert db.scalars(select(InterfaceUpload)).one().status == "applied"
        terms = db.scalars(select(OntoTerm).where(OntoTerm.tenant_id == tenant.id)).all()
        assert len(terms) == 20
        assert {"배합비", "점도 규격", "도막 검사"} <= {t.term for t in terms}
        assert all(t.status == "confirmed" for t in terms)
        aliases = db.scalars(select(OntoTermAlias).where(OntoTermAlias.tenant_id == tenant.id)).all()
        assert all(a.department for a in aliases)
        assert len({a.department for a in aliases}) >= 5
    with pytest.raises(SystemExit):
        cli.main(["seed-demo"])


def test_password_required_non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FDE_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit, match="password required"):
        cli.main(["init-admin", "--email", "a@b.c"])


def test_seed_sample(db: Session) -> None:
    cli.main(["init-admin", "--email", "root@luda.local", "--password", "root-pass-123"])
    cli.main(["seed-sample", "--password", "sample-pass-123"])
    tenant = db.scalars(select(Tenant).where(Tenant.code == "HANBIT")).one()
    with guard_bypass(db):
        assert len(db.scalars(select(System).where(System.tenant_id == tenant.id)).all()) == 6
        assert len(db.scalars(select(Interface).where(Interface.tenant_id == tenant.id)).all()) == 12
        assert len(db.scalars(select(OntoTerm).where(OntoTerm.tenant_id == tenant.id)).all()) == 15
        assert db.scalars(select(XlErdDraft).where(XlErdDraft.tenant_id == tenant.id)).one().confirmed
        assert {f.kind for f in db.scalars(select(Flow).where(Flow.tenant_id == tenant.id))} == {"as_is", "to_be"}
        assert len(db.scalars(select(OntoConcept).where(OntoConcept.tenant_id == tenant.id)).all()) == 5
        assert db.scalars(select(OntoMapping).where(OntoMapping.tenant_id == tenant.id)).all()
        assert db.scalars(select(OntoCandidate).where(OntoCandidate.status == "open")).all()
        assert db.scalars(select(DiscoveryInsight).where(DiscoveryInsight.tenant_id == tenant.id)).all()
        docs = db.scalars(select(SpecDocument).where(SpecDocument.tenant_id == tenant.id)).all()
        assert sorted(d.status for d in docs) == ["confirmed", "draft"]
        assert db.scalars(select(DevIssue).where(DevIssue.tenant_id == tenant.id)).all()
    with pytest.raises(SystemExit):
        cli.main(["seed-sample"])
