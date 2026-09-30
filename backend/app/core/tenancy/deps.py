from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.auth.deps import DB, CurrentPrincipal
from app.core.errors import forbidden, not_found
from app.core.tenancy.context import AUDIT_VIEW_ROLES, EXPORT_ROLES, TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Tenant
from app.db.base import TenantScopedModel
from app.db.session import TENANT_KEY

M = TypeVar("M", bound=TenantScopedModel)


def get_tenant_context(tenant_id: str, principal: CurrentPrincipal, db: DB) -> TenantContext:
    if tenant_id not in principal.allowed_tenant_ids or db.get(Tenant, tenant_id) is None:
        raise not_found()
    db.info[TENANT_KEY] = tenant_id
    return TenantContext(principal=principal, tenant_id=tenant_id)


Ctx = Annotated[TenantContext, Depends(get_tenant_context)]


def require_write(ctx: Ctx) -> TenantContext:
    if not ctx.can_write:
        raise forbidden()
    return ctx


WriteCtx = Annotated[TenantContext, Depends(require_write)]


def require_audit_view(ctx: Ctx) -> TenantContext:
    if ctx.role not in AUDIT_VIEW_ROLES:
        raise forbidden()
    return ctx


AuditCtx = Annotated[TenantContext, Depends(require_audit_view)]


def require_export(ctx: Ctx) -> TenantContext:
    if ctx.role not in EXPORT_ROLES:
        raise forbidden()
    return ctx


ExportCtx = Annotated[TenantContext, Depends(require_export)]


def path_entity(model: type[M], param: str) -> Callable[..., M]:
    """Dependency that loads a tenant-scoped row from a path param, 404 if not in the current tenant.

    Resolving the row in a dependency guarantees the 404 happens before body validation,
    so foreign ids never leak through 422 vs 404 differences.
    """

    def _load(request: Request, ctx: Ctx, db: DB) -> M:
        row_id = request.path_params.get(param)
        if not isinstance(row_id, str):
            raise not_found()
        return TenantScopedRepository(db, ctx, model).get_or_404(row_id)

    _load.__name__ = f"load_{model.__tablename__}_{param}"
    return _load


def repo(db: Session, ctx: TenantContext, model: type[M]) -> TenantScopedRepository[M]:
    return TenantScopedRepository(db, ctx, model)
