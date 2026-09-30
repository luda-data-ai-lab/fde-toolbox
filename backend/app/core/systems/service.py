from sqlalchemy.orm import Session

from app.core.audit.service import audited
from app.core.systems.models import System
from app.core.systems.schemas import SystemIn, SystemPatch
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository


@audited("system.create", "system")
def create_system(ctx: TenantContext, db: Session, body: SystemIn) -> System:
    return TenantScopedRepository(db, ctx, System).create(**body.model_dump())


@audited("system.update", "system")
def update_system(ctx: TenantContext, db: Session, obj: System, body: SystemPatch) -> System:
    return TenantScopedRepository(db, ctx, System).update(obj, **body.model_dump(exclude_unset=True))


@audited("system.delete", "system")
def delete_system(ctx: TenantContext, db: Session, obj: System) -> str:
    TenantScopedRepository(db, ctx, System).delete(obj)
    return obj.id
