from sqlalchemy import Engine, delete, func, select
from sqlalchemy.dialects import mssql, postgresql
from sqlalchemy.schema import CreateTable

from app.cli import create_database
from app.core.tenants.models import Tenant
from app.db.base import Base
from app.db.mssql import emulate_on_delete
from app.modules.ontomap.models import OntoTermAlias
from tests.conftest import World


def _ddl(table: object, dialect: object) -> str:
    return str(CreateTable(table).compile(dialect=dialect))  # type: ignore[arg-type]


def test_mssql_ddl_is_unicode_without_on_delete() -> None:
    alias = _ddl(OntoTermAlias.__table__, mssql.dialect())
    assert "alias NVARCHAR(200) NOT NULL" in alias
    assert "REFERENCES onto_terms (id)" in alias and "ON DELETE" not in alias
    assert "notes NVARCHAR(max)" in _ddl(Tenant.__table__, mssql.dialect())
    assert "ON DELETE CASCADE" in _ddl(OntoTermAlias.__table__, postgresql.dialect())


def test_create_database_only_targets_mssql() -> None:
    assert create_database("sqlite:///./unused.db") is False
    assert create_database("postgresql+psycopg://u:p@localhost/db") is False


def test_on_delete_emulation_purges_one_tenant(world: World, engine: Engine) -> None:
    tid, other = world.b.tenant_id, world.a.tenant_id
    tenants = Base.metadata.tables["tenants"]
    with engine.begin() as conn:
        emulate_on_delete(conn, tenants, select(tenants.c.id).where(tenants.c.id == tid))
        conn.execute(delete(tenants).where(tenants.c.id == tid))
    with engine.connect() as conn:
        remaining = {}
        for table in Base.metadata.sorted_tables:
            if "tenant_id" in table.c:
                count = select(func.count()).select_from(table)
                assert conn.scalar(count.where(table.c.tenant_id == tid)) == 0, table.name
                remaining[table.name] = conn.scalar(count.where(table.c.tenant_id == other))
        users = Base.metadata.tables["users"]
        assert conn.scalar(select(func.count()).select_from(users).where(users.c.home_tenant_id == tid)) == 0
    assert remaining["interfaces"] and remaining["discovery_session_questions"] and remaining["onto_term_aliases"]
