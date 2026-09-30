from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.assets.models import AssetItem
from app.core.auth.deps import DB, CurrentPrincipal
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement, Tenant
from app.core.users.models import User
from app.db.session import tenant_scope
from app.modules.agenthub.service import home_summary as agenthub_summary
from app.modules.devtracker.service import home_summary as devtracker_summary

router = APIRouter(prefix="/home", tags=["home"])


class TenantHome(BaseModel):
    tenant_id: str
    name: str
    code: str
    engagements: list[dict[str, Any]]
    devtracker: dict[str, Any]
    agenthub: dict[str, Any]


class HomeOut(BaseModel):
    role: str
    totals: dict[str, int]
    tenants: list[TenantHome]


@router.get("", response_model=HomeOut)
def home(principal: CurrentPrincipal, db: DB) -> HomeOut:
    tenants = list(db.scalars(select(Tenant).where(Tenant.id.in_(principal.allowed_tenant_ids)).order_by(Tenant.name)))
    items: list[TenantHome] = []
    for tenant in tenants:
        ctx = TenantContext(principal=principal, tenant_id=tenant.id)
        with tenant_scope(db, tenant.id):
            engagements = TenantScopedRepository(db, ctx, Engagement).all()
            items.append(
                TenantHome(
                    tenant_id=tenant.id,
                    name=tenant.name,
                    code=tenant.code,
                    engagements=[{"id": e.id, "name": e.name, "status": e.status} for e in engagements],
                    devtracker=devtracker_summary(ctx, db),
                    agenthub=agenthub_summary(ctx, db),
                )
            )
    totals = {"tenants": len(tenants)}
    if principal.is_admin:
        totals["users"] = db.scalar(select(func.count()).select_from(User)) or 0
        totals["assets"] = db.scalar(select(func.count(func.distinct(AssetItem.asset_id)))) or 0
    return HomeOut(role=principal.role, totals=totals, tenants=items)
