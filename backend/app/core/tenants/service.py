import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit.service import PURGE_KEY, audited, record
from app.core.errors import AppError
from app.core.tenancy.context import Principal, TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement, Tenant
from app.core.tenants.schemas import EngagementIn, EngagementPatch, TenantIn, TenantPatch
from app.core.users.models import User


def _ensure_code_free(db: Session, code: str) -> None:
    if db.scalars(select(Tenant).where(Tenant.code == code)).first():
        raise AppError(409, "tenant_code_taken")


@audited("tenant.create", "tenant")
def create_tenant(ctx: Principal, db: Session, body: TenantIn) -> Tenant:
    _ensure_code_free(db, body.code)
    tenant = Tenant(**body.model_dump(), created_by=ctx.user_id)
    db.add(tenant)
    db.flush()
    return tenant


@audited("tenant.update", "tenant")
def update_tenant(ctx: Principal, db: Session, tenant: Tenant, body: TenantPatch) -> Tenant:
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        tenant.name = data["name"]
    if data.get("status") is not None:
        tenant.status = data["status"]
    if data.get("deployment_mode") is not None:
        tenant.deployment_mode = data["deployment_mode"]
    if "notes" in data:
        tenant.notes = data["notes"]
    db.flush()
    return tenant


def delete_tenant(principal: Principal, db: Session, tenant: Tenant) -> None:
    """Permanently remove a tenant with all its data, audit logs and attachments."""
    tenant_id, code = tenant.id, tenant.code
    db.info[PURGE_KEY] = True
    try:
        for user in db.scalars(select(User).where(User.home_tenant_id == tenant_id)):
            user.home_tenant_id = None
        db.delete(tenant)
        db.flush()
        record(
            db,
            action="tenant.delete",
            actor_id=principal.user_id,
            target_type="tenant",
            target_id=tenant_id,
            detail={"code": code},
            ip=principal.ip,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.info.pop(PURGE_KEY, None)
    shutil.rmtree(get_settings().data_dir / "files" / tenant_id, ignore_errors=True)


@audited("engagement.create", "engagement")
def create_engagement(ctx: TenantContext, db: Session, body: EngagementIn) -> Engagement:
    return TenantScopedRepository(db, ctx, Engagement).create(**body.model_dump())


@audited("engagement.update", "engagement")
def update_engagement(ctx: TenantContext, db: Session, obj: Engagement, body: EngagementPatch) -> Engagement:
    return TenantScopedRepository(db, ctx, Engagement).update(obj, **body.model_dump(exclude_unset=True))


@audited("engagement.delete", "engagement")
def delete_engagement(ctx: TenantContext, db: Session, obj: Engagement) -> str:
    TenantScopedRepository(db, ctx, Engagement).delete(obj)
    return obj.id
