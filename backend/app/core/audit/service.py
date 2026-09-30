from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session

from app.core.audit.models import AuditLog
from app.core.tenancy.context import Principal, TenantContext
from app.db.base import Base

P = ParamSpec("P")
R = TypeVar("R")
C = TypeVar("C", TenantContext, Principal)

PURGE_KEY = "audit_purge_allowed"


class AuditLogImmutableError(RuntimeError):
    pass


def record(
    db: Session,
    *,
    action: str,
    actor_id: str | None,
    tenant_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    log = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
        ip=ip,
        created_by=actor_id,
    )
    db.add(log)
    return log


def _target_id(result: object) -> str | None:
    if isinstance(result, str):
        return result
    if isinstance(result, Base):
        return result.id
    return None


def audited(
    action: str, target_type: str
) -> Callable[[Callable[Concatenate[C, Session, P], R]], Callable[Concatenate[C, Session, P], R]]:
    """Service-layer decorator: run the write, append an audit log and commit in one transaction."""

    def decorator(
        fn: Callable[Concatenate[C, Session, P], R],
    ) -> Callable[Concatenate[C, Session, P], R]:
        @wraps(fn)
        def wrapper(ctx: C, db: Session, *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                result = fn(ctx, db, *args, **kwargs)
                tenant_id = ctx.tenant_id if isinstance(ctx, TenantContext) else None
                record(
                    db,
                    action=action,
                    actor_id=ctx.user_id,
                    tenant_id=tenant_id,
                    target_type=target_type,
                    target_id=_target_id(result),
                    ip=ctx.ip,
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            return result

        return cast(Callable[Concatenate[C, Session, P], R], wrapper)

    return decorator


@event.listens_for(Session, "before_flush")
def _block_audit_mutation(session: Session, _ctx: Any, _instances: Any) -> None:
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, AuditLog) and not session.info.get(PURGE_KEY):
            raise AuditLogImmutableError("audit logs are append-only")


@event.listens_for(Session, "do_orm_execute")
def _block_bulk_audit_mutation(state: ORMExecuteState) -> None:
    if (
        (state.is_update or state.is_delete)
        and not state.session.info.get(PURGE_KEY)
        and any(m.class_ is AuditLog for m in state.all_mappers)
    ):
        raise AuditLogImmutableError("audit logs are append-only")
