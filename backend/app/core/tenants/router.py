from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.core.auth.deps import DB, AdminPrincipal
from app.core.errors import not_found
from app.core.pagination import Page, paginate
from app.core.tenancy.deps import Ctx, WriteCtx, path_entity, repo
from app.core.tenants import service
from app.core.tenants.models import Engagement, Tenant
from app.core.tenants.schemas import (
    EngagementIn,
    EngagementOut,
    EngagementPatch,
    TenantIn,
    TenantOut,
    TenantPatch,
)

admin_router = APIRouter(prefix="/admin/tenants", tags=["admin"])
router = APIRouter(prefix="/t/{tenant_id}/engagements", tags=["engagements"])


def _tenant(tenant_id: str, db: DB) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise not_found()
    return tenant


@admin_router.get("", response_model=Page[TenantOut])
def list_tenants(principal: AdminPrincipal, db: DB, limit: int = 50, cursor: str | None = None) -> Page[TenantOut]:
    rows, nxt = paginate(db, select(Tenant), Tenant, limit, cursor)
    return Page(items=[TenantOut.model_validate(r) for r in rows], next_cursor=nxt)


@admin_router.post("", response_model=TenantOut, status_code=201)
def create_tenant(body: TenantIn, principal: AdminPrincipal, db: DB) -> TenantOut:
    return TenantOut.model_validate(service.create_tenant(principal, db, body))


@admin_router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: str, principal: AdminPrincipal, db: DB) -> TenantOut:
    return TenantOut.model_validate(_tenant(tenant_id, db))


@admin_router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: str, body: TenantPatch, principal: AdminPrincipal, db: DB) -> TenantOut:
    return TenantOut.model_validate(service.update_tenant(principal, db, _tenant(tenant_id, db), body))


@admin_router.delete("/{tenant_id}", status_code=204)
def delete_tenant(tenant_id: str, principal: AdminPrincipal, db: DB) -> Response:
    service.delete_tenant(principal, db, _tenant(tenant_id, db))
    return Response(status_code=204)


EngagementDep = Annotated[Engagement, Depends(path_entity(Engagement, "engagement_id"))]


@router.get("", response_model=Page[EngagementOut])
def list_engagements(ctx: Ctx, db: DB, limit: int = 50, cursor: str | None = None) -> Page[EngagementOut]:
    rows, nxt = repo(db, ctx, Engagement).page(limit=limit, cursor=cursor)
    return Page(items=[EngagementOut.model_validate(r) for r in rows], next_cursor=nxt)


@router.post("", response_model=EngagementOut, status_code=201)
def create_engagement(body: EngagementIn, ctx: WriteCtx, db: DB) -> EngagementOut:
    return EngagementOut.model_validate(service.create_engagement(ctx, db, body))


@router.get("/{engagement_id}", response_model=EngagementOut)
def get_engagement(obj: EngagementDep) -> EngagementOut:
    return EngagementOut.model_validate(obj)


@router.patch("/{engagement_id}", response_model=EngagementOut)
def update_engagement(obj: EngagementDep, body: EngagementPatch, ctx: WriteCtx, db: DB) -> EngagementOut:
    return EngagementOut.model_validate(service.update_engagement(ctx, db, obj, body))


@router.delete("/{engagement_id}", status_code=204)
def delete_engagement(obj: EngagementDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_engagement(ctx, db, obj)
    return Response(status_code=204)
