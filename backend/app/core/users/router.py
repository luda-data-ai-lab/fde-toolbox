from fastapi import APIRouter
from sqlalchemy import select

from app.core.auth.deps import DB, AdminPrincipal
from app.core.errors import not_found
from app.core.pagination import Page, paginate
from app.core.users import service
from app.core.users.models import User
from app.core.users.schemas import UserAdminOut, UserIn, UserPatch

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=Page[UserAdminOut])
def list_users(principal: AdminPrincipal, db: DB, limit: int = 50, cursor: str | None = None) -> Page[UserAdminOut]:
    rows, nxt = paginate(db, select(User), User, limit, cursor)
    return Page(items=[service.to_admin_out(db, u) for u in rows], next_cursor=nxt)


@router.post("", response_model=UserAdminOut, status_code=201)
def create_user(body: UserIn, principal: AdminPrincipal, db: DB) -> UserAdminOut:
    return service.to_admin_out(db, service.create_user(principal, db, body))


@router.get("/{user_id}", response_model=UserAdminOut)
def get_user(user_id: str, principal: AdminPrincipal, db: DB) -> UserAdminOut:
    user = db.get(User, user_id)
    if user is None:
        raise not_found()
    return service.to_admin_out(db, user)


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user(user_id: str, body: UserPatch, principal: AdminPrincipal, db: DB) -> UserAdminOut:
    user = db.get(User, user_id)
    if user is None:
        raise not_found()
    return service.to_admin_out(db, service.update_user(principal, db, user, body))
