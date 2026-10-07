"""Adapter activation workflow: FDE requests → customer admin approves (LUDA admin with a reason when
the customer has no admin) → active; any manager can deactivate. Every step is audit-logged."""

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import Adapter, HealthResult
from app.adapters.registry import REGISTRY, get_adapter
from app.core.adapters.models import AdapterActivation
from app.core.adapters.schemas import (
    ActivationOut,
    ActivationRequestIn,
    AdapterOut,
    ApproveIn,
    EgressNoticeOut,
    ReasonIn,
)
from app.core.audit.service import record
from app.core.crypto import encrypt_json
from app.core.errors import AppError, forbidden, not_found
from app.core.tenancy.context import TenantContext
from app.core.users.models import User
from app.db.base import utcnow

REQUEST_ROLES = frozenset({"luda_admin", "fde"})
APPROVE_ROLES = frozenset({"luda_admin", "client_admin"})
MANAGE_ROLES = frozenset({"luda_admin", "fde", "client_admin"})


def _require(ctx: TenantContext, roles: frozenset[str]) -> None:
    if ctx.role not in roles:
        raise forbidden()


def _adapter(key: str) -> Adapter:
    if not REGISTRY.available():
        raise AppError(403, "adapters_not_allowed")
    adapter = REGISTRY.get(key)
    if adapter is None:
        raise not_found()
    return adapter


def activation_out(row: AdapterActivation) -> ActivationOut:
    has_credentials = row.credentials_encrypted is not None
    return ActivationOut(
        id=row.id,
        tenant_id=row.tenant_id,
        adapter_key=row.adapter_key,
        status="disabled" if row.status == "active" and not has_credentials else row.status,
        config=row.config,
        has_credentials=has_credentials,
        egress_notice=EgressNoticeOut.model_validate(row.egress_notice) if row.egress_notice else None,
        request_note=row.request_note,
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        approval_reason=row.approval_reason,
        deactivated_by=row.deactivated_by,
        deactivated_at=row.deactivated_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_adapters(ctx: TenantContext, db: Session) -> list[AdapterOut]:
    adapters = REGISTRY.available()
    if not adapters:
        return []
    rows = {
        r.adapter_key: r
        for r in db.scalars(select(AdapterActivation).where(AdapterActivation.tenant_id == ctx.tenant_id))
    }
    return [
        AdapterOut.model_validate(
            {
                "key": a.key,
                "display_name": a.display_name,
                "implemented": a.implemented,
                "egress_notice": a.data_egress_notice().as_dict(),
                "config_fields": [asdict(f) for f in a.config_fields],
                "activation": activation_out(rows[a.key]) if a.key in rows else None,
            }
        )
        for a in adapters
    ]


def _audit(ctx: TenantContext, db: Session, action: str, row: AdapterActivation, reason: str | None = None) -> None:
    detail: dict[str, str] = {"adapter": row.adapter_key}
    if reason:
        detail["reason"] = reason
    record(
        db,
        action=action,
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="adapter_activation",
        target_id=row.id,
        detail=detail,
        ip=ctx.ip,
    )


def request_activation(ctx: TenantContext, db: Session, body: ActivationRequestIn) -> AdapterActivation:
    _require(ctx, REQUEST_ROLES)
    adapter = _adapter(body.adapter_key)
    config, credentials = adapter.validate_config(body.config, body.credentials)
    row = db.scalars(
        select(AdapterActivation).where(
            AdapterActivation.tenant_id == ctx.tenant_id, AdapterActivation.adapter_key == adapter.key
        )
    ).first()
    if row is not None and row.status == "active" and row.credentials_encrypted is not None:
        raise AppError(409, "adapter_already_active")
    if row is None:
        row = AdapterActivation(tenant_id=ctx.tenant_id, adapter_key=adapter.key, created_by=ctx.user_id)
        db.add(row)
    row.status = "requested"
    row.config = config
    row.credentials_encrypted = encrypt_json(credentials)
    row.egress_notice = adapter.data_egress_notice().as_dict()
    row.request_note = body.note
    row.requested_by = ctx.user_id
    row.requested_at = utcnow()
    row.approved_by = row.approved_at = row.approval_reason = None
    row.deactivated_by = row.deactivated_at = None
    db.flush()
    _audit(ctx, db, "adapter.request", row, body.note)
    db.commit()
    return row


def _tenant_has_client_admin(db: Session, tenant_id: str) -> bool:
    return (
        db.scalars(
            select(User.id).where(User.home_tenant_id == tenant_id, User.role == "client_admin", User.is_active)
        ).first()
        is not None
    )


def _pending(row: AdapterActivation) -> None:
    if row.status != "requested":
        raise AppError(409, "activation_not_pending")


def approve(ctx: TenantContext, db: Session, row: AdapterActivation, body: ApproveIn) -> AdapterActivation:
    _require(ctx, APPROVE_ROLES)
    adapter = _adapter(row.adapter_key)
    _pending(row)
    reason = (body.reason or "").strip() or None
    if ctx.role == "luda_admin":
        if _tenant_has_client_admin(db, ctx.tenant_id):
            raise AppError(403, "client_admin_approval_required")
        if reason is None:
            raise AppError(422, "approval_reason_required")
    row.status = "active"
    row.egress_notice = adapter.data_egress_notice().as_dict()
    row.approved_by = ctx.user_id
    row.approved_at = utcnow()
    row.approval_reason = reason
    db.flush()
    _audit(ctx, db, "adapter.approve", row, reason)
    db.commit()
    return row


def _disable(row: AdapterActivation, ctx: TenantContext) -> None:
    row.status = "disabled"
    row.credentials_encrypted = None
    row.deactivated_by = ctx.user_id
    row.deactivated_at = utcnow()


def reject(ctx: TenantContext, db: Session, row: AdapterActivation, body: ReasonIn) -> AdapterActivation:
    _require(ctx, APPROVE_ROLES)
    _pending(row)
    _disable(row, ctx)
    db.flush()
    _audit(ctx, db, "adapter.reject", row, body.reason)
    db.commit()
    return row


def deactivate(ctx: TenantContext, db: Session, row: AdapterActivation, body: ReasonIn) -> AdapterActivation:
    _require(ctx, MANAGE_ROLES)
    if row.status == "disabled":
        raise AppError(409, "activation_not_active")
    _disable(row, ctx)
    db.flush()
    _audit(ctx, db, "adapter.deactivate", row, body.reason)
    db.commit()
    return row


def health_check(ctx: TenantContext, db: Session, row: AdapterActivation) -> HealthResult:
    _require(ctx, REQUEST_ROLES)
    adapter, actx = get_adapter(ctx, db, row.adapter_key)
    return adapter.health_check(actx)
