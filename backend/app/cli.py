"""Operator commands: ``python -m app.cli <command>``."""

import argparse
import getpass
import json
import os
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, select, text
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.config import get_settings
from app.core.assets.models import AssetItem
from app.core.assets.schemas import AssetPackage
from app.core.assets.service import import_package, latest
from app.core.schemas import AssetRef
from app.core.systems.schemas import SystemIn
from app.core.systems.service import create_system
from app.core.tenancy.context import Principal, TenantContext
from app.core.tenants.models import Tenant
from app.core.tenants.schemas import EngagementIn, TenantIn
from app.core.tenants.service import create_engagement, create_tenant
from app.core.users.models import User
from app.core.users.schemas import UserIn
from app.core.users.service import create_user, create_user_record
from app.db.session import new_session, tenant_scope
from app.modules.agenthub.schemas import InstanceIn
from app.modules.agenthub.service import create_instance
from app.modules.devtracker.schemas import ProjectIn, TaskIn
from app.modules.devtracker.service import create_project, create_task

BACKEND = Path(__file__).resolve().parents[1]
SEED_ASSETS = BACKEND / "seeds" / "assets"
DEMO_CODE = "DEMO"
DEMO_AGENT_TEMPLATE = "daily-production-report"


def _out(msg: str) -> None:
    sys.stdout.write(msg + "\n")


def migrate() -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")


def create_database(url: str) -> bool:
    """Create the SQL Server database named in ``url`` when missing; other backends need no step."""
    target = make_url(url)
    if target.get_backend_name() != "mssql" or not target.database:
        return False
    engine = create_engine(target.set(database="master"), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            if conn.scalar(text("SELECT DB_ID(:name)"), {"name": target.database}) is not None:
                return False
            conn.exec_driver_sql(f"CREATE DATABASE {conn.dialect.identifier_preparer.quote(target.database)}")
    finally:
        engine.dispose()
    return True


def _password(given: str | None, env: str, prompt: str) -> str:
    value = given or os.environ.get(env)
    if value:
        return value
    if not sys.stdin.isatty():
        raise SystemExit(f"password required: pass --password or set {env}")
    first = getpass.getpass(prompt)
    if first != getpass.getpass("Repeat: "):
        raise SystemExit("passwords do not match")
    return first


def _admin(db: Session) -> Principal:
    user = db.scalars(select(User).where(User.role == "luda_admin", User.is_active).order_by(User.created_at)).first()
    if user is None:
        raise SystemExit("no LUDA admin exists; run init-admin first")
    return Principal(user=user, ip=None)


def init_admin(email: str, name: str, password: str) -> None:
    with new_session() as db:
        if db.scalars(select(User).where(User.role == "luda_admin")).first():
            raise SystemExit("a LUDA admin already exists")
        create_user_record(db, UserIn(email=email, name=name, role="luda_admin", password=password), None)
        db.commit()
    _out(f"created LUDA admin {email}")


def seed_assets(db: Session) -> tuple[int, int]:
    principal = _admin(db)
    created = skipped = 0
    for path in sorted(SEED_ASSETS.glob("*.json")):
        package = AssetPackage.model_validate(json.loads(path.read_text(encoding="utf-8")))
        result = import_package(principal, db, package)
        created += result.created
        skipped += result.skipped
    return created, skipped


def seed_demo(db: Session, password: str | None) -> dict[str, str]:
    seed_assets(db)
    principal = _admin(db)
    if db.scalars(select(Tenant).where(Tenant.code == DEMO_CODE)).first():
        raise SystemExit("demo tenant already exists")
    tenant = create_tenant(principal, db, TenantIn(name="데모 제조사", code=DEMO_CODE, notes="도료 제조 데모"))
    pw = password or secrets.token_urlsafe(12)
    fde = create_user(
        principal, db, UserIn(email="fde@demo.local", name="데모 FDE", role="fde", password=pw, tenant_ids=[tenant.id])
    )
    create_user(
        principal,
        db,
        UserIn(
            email="client@demo.local",
            name="데모 고객 관리자",
            role="client_admin",
            password=pw,
            home_tenant_id=tenant.id,
        ),
    )
    ctx = TenantContext(
        principal=Principal(user=fde, ip=None, allowed_tenant_ids=frozenset({tenant.id})), tenant_id=tenant.id
    )
    with tenant_scope(db, tenant.id):
        eng = create_engagement(
            ctx,
            db,
            EngagementIn(
                name="생산·품질 데이터 통합",
                status="in_progress",
                lead_fde_id=fde.id,
                description="MES·ERP·LIMS 데이터를 연결해 생산 일보와 품질 추적을 자동화한다.",
            ),
        )
        systems = [
            create_system(ctx, db, body)
            for body in (
                SystemIn(
                    name="생산관리시스템",
                    short_name="MES",
                    type="MES",
                    owner_dept="생산팀",
                    hosting="on_premise",
                    db_type="MSSQL",
                ),
                SystemIn(
                    name="전사자원관리",
                    short_name="ERP",
                    type="ERP",
                    owner_dept="경영지원팀",
                    hosting="on_premise",
                    db_type="Oracle",
                ),
                SystemIn(
                    name="실험실정보관리",
                    short_name="LIMS",
                    type="LIMS",
                    owner_dept="품질팀",
                    hosting="on_premise",
                    db_type="MSSQL",
                ),
                SystemIn(
                    name="창고관리시스템",
                    short_name="WMS",
                    type="WMS",
                    owner_dept="물류팀",
                    hosting="cloud",
                    db_type="PostgreSQL",
                ),
                SystemIn(
                    name="설비감시제어",
                    short_name="SCADA",
                    type="SCADA",
                    owner_dept="설비팀",
                    hosting="on_premise",
                    db_type="Historian",
                ),
                SystemIn(name="그룹웨어", short_name="GW", type="GROUPWARE", owner_dept="정보전략팀", hosting="cloud"),
            )
        ]
        project = create_project(
            ctx, db, ProjectIn(engagement_id=eng.id, name="생산 일보 자동화", status="active", stack="Python, FastAPI")
        )
        for task in (
            TaskIn(title="MES 실적 테이블 조사", status="done", assignee_id=fde.id),
            TaskIn(title="LIMS 검사 결과 연동", status="in_progress", assignee_id=fde.id),
            TaskIn(title="일보 요약 프롬프트 초안", status="todo", assignee_id=fde.id),
        ):
            create_task(ctx, db, project, task)
        tmpl = latest(db, _asset_id(db, DEMO_AGENT_TEMPLATE))
        create_instance(
            ctx,
            db,
            InstanceIn(
                name="데모 생산 일보 요약",
                template_ref=AssetRef(asset_id=tmpl.asset_id, version=tmpl.version),
                engagement_id=eng.id,
                system_ids=[systems[0].id, systems[2].id],
                status="pilot",
                owner_id=fde.id,
                dev_project_id=project.id,
            ),
        )
    return {"tenant_id": tenant.id, "password": pw}


def _asset_id(db: Session, key: str) -> str:
    asset_id = db.scalars(select(AssetItem.asset_id).where(AssetItem.asset_key == key)).first()
    if asset_id is None:
        raise SystemExit(f"seed asset {key!r} missing")
    return asset_id


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply database migrations")
    sub.add_parser("create-db", help="create the SQL Server database from DATABASE_URL if missing")
    p = sub.add_parser("init-admin", help="create the first LUDA admin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="LUDA Admin")
    p.add_argument("--password", help="or set FDE_ADMIN_PASSWORD; prompts when interactive")
    sub.add_parser("seed-assets", help="import bundled LUDA assets (idempotent)")
    p = sub.add_parser("seed-demo", help="create the demo tenant, users and sample data")
    p.add_argument("--password", help="password for demo users (random if omitted)")
    args = parser.parse_args(argv)

    if args.cmd == "create-db":
        _out("database created" if create_database(get_settings().database_url) else "database ready")
    elif args.cmd == "migrate":
        migrate()
        _out("database at head")
    elif args.cmd == "init-admin":
        init_admin(args.email, args.name, _password(args.password, "FDE_ADMIN_PASSWORD", "Password: "))
    elif args.cmd == "seed-assets":
        with new_session() as db:
            created, skipped = seed_assets(db)
        _out(f"assets: {created} created, {skipped} already present")
    elif args.cmd == "seed-demo":
        with new_session() as db:
            info = seed_demo(db, args.password)
        _out(f"demo tenant {info['tenant_id']} created")
        _out(f"users fde@demo.local / client@demo.local, password: {info['password']}")


if __name__ == "__main__":
    main()
