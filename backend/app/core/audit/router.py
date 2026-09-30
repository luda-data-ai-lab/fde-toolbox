import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.audit.models import AuditLog
from app.core.audit.service import record
from app.core.auth.deps import DB, AdminPrincipal
from app.core.pagination import Page, paginate
from app.core.tenancy.deps import AuditCtx

router = APIRouter(prefix="/t/{tenant_id}/audit-logs", tags=["audit"])
admin_router = APIRouter(prefix="/admin/audit-logs", tags=["admin"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict[str, object]
    ip: str | None
    at: datetime
    created_at: datetime


@router.get("", response_model=Page[AuditLogOut])
def list_logs(
    ctx: AuditCtx, db: DB, limit: int = 50, cursor: str | None = None, action: str | None = None
) -> Page[AuditLogOut]:
    stmt = select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows, nxt = paginate(db, stmt, AuditLog, limit, cursor)
    return Page(items=[AuditLogOut.model_validate(r) for r in rows], next_cursor=nxt)


@router.get("/export.csv")
def export_logs(ctx: AuditCtx, db: DB) -> Response:
    rows = db.scalars(
        select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id).order_by(AuditLog.at, AuditLog.id)
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["at", "actor_id", "action", "target_type", "target_id", "ip", "detail"])
    for r in rows:
        writer.writerow(
            [
                r.at.isoformat(),
                r.actor_id,
                r.action,
                r.target_type,
                r.target_id,
                r.ip,
                json.dumps(r.detail, ensure_ascii=False),
            ]
        )
    record(db, action="audit.export", actor_id=ctx.user_id, tenant_id=ctx.tenant_id, target_type="audit_log", ip=ctx.ip)
    db.commit()
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


@admin_router.get("", response_model=Page[AuditLogOut])
def list_global_logs(
    principal: AdminPrincipal, db: DB, limit: int = 50, cursor: str | None = None
) -> Page[AuditLogOut]:
    rows, nxt = paginate(db, select(AuditLog).where(AuditLog.tenant_id.is_(None)), AuditLog, limit, cursor)
    return Page(items=[AuditLogOut.model_validate(r) for r in rows], next_cursor=nxt)
