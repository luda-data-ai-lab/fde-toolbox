from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from app.config import get_settings
from app.db.base import TenantScopedMixin

TENANT_KEY = "tenant_id"
BYPASS_KEY = "tenant_guard_bypass"


class TenantGuardError(RuntimeError):
    pass


def _make_engine(url: str) -> Engine:
    kwargs: dict[str, Any] = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn: Any, _rec: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = _make_engine(get_settings().database_url)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def configure_engine(url: str) -> Engine:
    """Replace the global engine (tests, CLI)."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = _make_engine(url)
    _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def new_session() -> Session:
    get_engine()
    assert _factory is not None
    return _factory()


def get_db() -> Iterator[Session]:
    db = new_session()
    try:
        yield db
    finally:
        db.close()


def _touches_tenant_data(state: ORMExecuteState) -> bool:
    return any(issubclass(m.class_, TenantScopedMixin) for m in state.all_mappers)


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete) or not _touches_tenant_data(state):
        return
    info = state.session.info
    if info.get(BYPASS_KEY):
        return
    tenant_id = info.get(TENANT_KEY)
    if tenant_id is None:
        raise TenantGuardError("query on tenant-scoped table without tenant context")
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantScopedMixin,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _check_tenant_on_write(session: Session, _ctx: Any, _instances: Any) -> None:
    if session.info.get(BYPASS_KEY):
        return
    tenant_id = session.info.get(TENANT_KEY)
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, TenantScopedMixin) and (tenant_id is None or obj.tenant_id != tenant_id):
            raise TenantGuardError("write to tenant-scoped row outside current tenant")


@contextmanager
def tenant_scope(db: Session, tenant_id: str) -> Iterator[Session]:
    prev = db.info.get(TENANT_KEY)
    db.info[TENANT_KEY] = tenant_id
    try:
        yield db
    finally:
        if prev is None:
            db.info.pop(TENANT_KEY, None)
        else:
            db.info[TENANT_KEY] = prev


@contextmanager
def guard_bypass(db: Session) -> Iterator[Session]:
    """Explicit system-level access across tenants (admin export/delete, CLI seeds)."""
    prev = db.info.get(BYPASS_KEY, False)
    db.info[BYPASS_KEY] = True
    try:
        yield db
    finally:
        db.info[BYPASS_KEY] = prev
