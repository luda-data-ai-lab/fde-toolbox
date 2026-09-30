from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.audit.service import audited
from app.core.auth.security import hash_password
from app.core.errors import AppError, bad_request
from app.core.tenancy.context import Principal
from app.core.tenants.models import Tenant
from app.core.users.models import User, UserTenantAssignment
from app.core.users.schemas import UserAdminOut, UserIn, UserOut, UserPatch


def tenant_ids_of(db: Session, user_id: str) -> list[str]:
    return list(db.scalars(select(UserTenantAssignment.tenant_id).where(UserTenantAssignment.user_id == user_id)))


def user_has_tenant(db: Session, user_id: str, tenant_id: str) -> bool:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return False
    if user.role == "luda_admin":
        return True
    if user.role == "fde":
        return tenant_id in tenant_ids_of(db, user_id)
    return user.home_tenant_id == tenant_id


def to_admin_out(db: Session, user: User) -> UserAdminOut:
    base = UserOut.model_validate(user).model_dump()
    return UserAdminOut(**base, tenant_ids=tenant_ids_of(db, user.id))


def _validate_tenancy(db: Session, role: str, home_tenant_id: str | None, tenant_ids: list[str]) -> None:
    for tid in [*tenant_ids, *([home_tenant_id] if home_tenant_id else [])]:
        if db.get(Tenant, tid) is None:
            raise AppError(422, "invalid_reference", detail={"field": "tenant_ids"})
    if role in ("client_admin", "client_user") and not home_tenant_id:
        raise bad_request("home_tenant_required")


def _set_assignments(db: Session, user_id: str, tenant_ids: list[str], actor_id: str) -> None:
    db.execute(delete(UserTenantAssignment).where(UserTenantAssignment.user_id == user_id))
    for tid in dict.fromkeys(tenant_ids):
        db.add(UserTenantAssignment(user_id=user_id, tenant_id=tid, created_by=actor_id))


def create_user_record(db: Session, body: UserIn, actor_id: str | None) -> User:
    email = body.email.strip().lower()
    if db.scalars(select(User).where(User.email == email)).first():
        raise AppError(409, "email_taken")
    _validate_tenancy(db, body.role, body.home_tenant_id, body.tenant_ids)
    user = User(
        email=email,
        name=body.name,
        role=body.role,
        password_hash=hash_password(body.password),
        home_tenant_id=body.home_tenant_id,
        created_by=actor_id,
    )
    db.add(user)
    db.flush()
    if body.role == "fde":
        _set_assignments(db, user.id, body.tenant_ids, actor_id or user.id)
    return user


@audited("user.create", "user")
def create_user(ctx: Principal, db: Session, body: UserIn) -> User:
    return create_user_record(db, body, ctx.user_id)


@audited("user.update", "user")
def update_user(ctx: Principal, db: Session, user: User, body: UserPatch) -> User:
    data = body.model_dump(exclude_unset=True)
    role = data.get("role", user.role)
    home = data.get("home_tenant_id", user.home_tenant_id)
    tenant_ids = data.get("tenant_ids")
    _validate_tenancy(db, role, home, tenant_ids or [])
    if "name" in data and data["name"] is not None:
        user.name = data["name"]
    if "role" in data and data["role"] is not None:
        user.role = data["role"]
    if "home_tenant_id" in data:
        user.home_tenant_id = data["home_tenant_id"]
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = data["is_active"]
    if data.get("password"):
        user.password_hash = hash_password(data["password"])
    if tenant_ids is not None:
        _set_assignments(db, user.id, tenant_ids if role == "fde" else [], ctx.user_id)
    elif role != "fde":
        _set_assignments(db, user.id, [], ctx.user_id)
    db.flush()
    return user
