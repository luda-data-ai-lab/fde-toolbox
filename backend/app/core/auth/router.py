from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.config import get_settings
from app.core.audit.service import record
from app.core.auth.deps import DB, CurrentPrincipal, allowed_tenant_ids, client_ip
from app.core.auth.security import create_token, verify_password
from app.core.errors import AppError
from app.core.tenants.models import Tenant
from app.core.users.models import User
from app.core.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class TenantBrief(BaseModel):
    id: str
    name: str
    code: str
    status: str


class MeOut(BaseModel):
    user: UserOut
    tenants: list[TenantBrief]
    adapters_allowed: bool


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response, db: DB) -> MeOut:
    user = db.scalars(select(User).where(User.email == body.email.strip().lower())).first()
    if user is None or not user.is_active or not verify_password(user.password_hash, body.password):
        record(db, action="auth.login_failed", actor_id=None, detail={"email": body.email[:254]}, ip=client_ip(request))
        db.commit()
        raise AppError(401, "invalid_credentials")
    record(db, action="auth.login", actor_id=user.id, target_type="user", target_id=user.id, ip=client_ip(request))
    db.commit()
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        create_token(user.id),
        httponly=True,
        samesite="strict",
        secure=s.cookie_secure,
        max_age=s.session_ttl_minutes * 60,
        path="/",
    )
    return _me(db, user, allowed_tenant_ids(db, user))


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=MeOut)
def me(principal: CurrentPrincipal, db: DB) -> MeOut:
    return _me(db, principal.user, principal.allowed_tenant_ids)


def _me(db: DB, user: User, tenant_ids: frozenset[str]) -> MeOut:
    tenants = (
        db.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids)).order_by(Tenant.name)).all() if tenant_ids else []
    )
    return MeOut(
        user=UserOut.model_validate(user),
        tenants=[TenantBrief(id=t.id, name=t.name, code=t.code, status=t.status) for t in tenants],
        adapters_allowed=get_settings().adapters_allowed,
    )
