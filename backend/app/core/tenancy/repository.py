from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.core.pagination import paginate
from app.core.tenancy.context import TenantContext
from app.db.base import TenantScopedModel

M = TypeVar("M", bound=TenantScopedModel)


class TenantScopedRepository(Generic[M]):
    """All access to tenant data goes through here. tenant_id always comes from the context."""

    def __init__(self, db: Session, ctx: TenantContext, model: type[M]) -> None:
        self.db = db
        self.ctx = ctx
        self.model = model

    def query(self) -> Select[M]:
        return select(self.model).where(self.model.tenant_id == self.ctx.tenant_id)

    def get(self, row_id: str) -> M | None:
        return self.db.scalars(self.query().where(self.model.id == row_id)).first()

    def get_or_404(self, row_id: str) -> M:
        row = self.get(row_id)
        if row is None:
            raise not_found()
        return row

    def ensure_ref(self, row_id: str | None, field: str) -> None:
        """Validate a body-supplied reference belongs to the current tenant."""
        if row_id is not None and self.get(row_id) is None:
            raise AppError(422, "invalid_reference", detail={"field": field})

    def page(self, *, limit: int, cursor: str | None, stmt: Select[M] | None = None) -> tuple[list[M], str | None]:
        return paginate(self.db, stmt if stmt is not None else self.query(), self.model, limit, cursor)

    def all(self, stmt: Select[M] | None = None) -> list[M]:
        return list(self.db.scalars(stmt if stmt is not None else self.query()).all())

    def create(self, **values: Any) -> M:
        values.pop("tenant_id", None)
        values.pop("id", None)
        obj = self.model(**values)
        obj.tenant_id = self.ctx.tenant_id
        obj.created_by = self.ctx.user_id
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, obj: M, **values: Any) -> M:
        for key, value in values.items():
            if key in {"id", "tenant_id", "created_at", "created_by"}:
                continue
            setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: M) -> None:
        self.db.delete(obj)
        self.db.flush()
