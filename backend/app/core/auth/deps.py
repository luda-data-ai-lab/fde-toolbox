from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.auth.security import decode_token
from app.core.errors import AppError, forbidden
from app.core.tenancy.context import Principal
from app.core.tenants.models import Tenant
from app.core.users.models import User, UserTenantAssignment
from app.db.session import get_db

DB = Annotated[Session, Depends(get_db)]


def allowed_tenant_ids(db: Session, user: User) -> frozenset[str]:
    if user.role == "luda_admin":
        return frozenset(db.scalars(select(Tenant.id)).all())
    ids: set[str] = set()
    if user.role == "fde":
        ids.update(db.scalars(select(UserTenantAssignment.tenant_id).where(UserTenantAssignment.user_id == user.id)))
    elif user.home_tenant_id:
        ids.add(user.home_tenant_id)
    return frozenset(ids)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_principal(request: Request, db: DB) -> Principal:
    token = request.cookies.get(get_settings().session_cookie_name)
    user_id = decode_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise AppError(401, "unauthorized")
    return Principal(user=user, ip=client_ip(request), allowed_tenant_ids=allowed_tenant_ids(db, user))


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.is_admin:
        raise forbidden()
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]
