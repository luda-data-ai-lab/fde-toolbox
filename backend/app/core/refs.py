"""Generic, tenant-safe validation of ID references across modules.

Modules must not import each other's models, so cross-module references are
checked by table name through the SQLAlchemy registry.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tenancy.context import TenantContext
from app.db.base import Base, TenantScopedModel


def _model_for(table: str) -> type[TenantScopedModel]:
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if issubclass(cls, TenantScopedModel) and cls.__tablename__ == table:
            return cls
    raise KeyError(table)


def ensure_tenant_refs(db: Session, ctx: TenantContext, table: str, ids: list[str], field: str) -> None:
    unique = set(ids)
    if not unique:
        return
    model = _model_for(table)
    found = set(db.scalars(select(model.id).where(model.tenant_id == ctx.tenant_id, model.id.in_(unique))).all())
    if found != unique:
        raise AppError(422, "invalid_reference", detail={"field": field})


def ensure_tenant_ref(db: Session, ctx: TenantContext, table: str, row_id: str | None, field: str) -> None:
    if row_id is not None:
        ensure_tenant_refs(db, ctx, table, [row_id], field)
