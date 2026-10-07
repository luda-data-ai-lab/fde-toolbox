from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import Adapter, AdapterContext, AdapterDisabled
from app.adapters.llm import LlmAdapter, LlmClient
from app.adapters.stubs import AgentRuntimeAdapter, GitAdapter
from app.config import get_settings
from app.core.adapters.models import AdapterActivation
from app.core.crypto import DecryptionError, decrypt_json
from app.core.tenancy.context import TenantContext


class AdapterRegistry:
    """Known adapters. With ADAPTERS_ALLOWED=false it exposes none of them."""

    def __init__(self, adapters: list[Adapter]) -> None:
        self._adapters = {a.key: a for a in adapters}

    def available(self) -> list[Adapter]:
        return list(self._adapters.values()) if get_settings().adapters_allowed else []

    def get(self, key: str) -> Adapter | None:
        return self._adapters.get(key) if get_settings().adapters_allowed else None


LLM = LlmAdapter()
REGISTRY = AdapterRegistry([LLM, AgentRuntimeAdapter(), GitAdapter()])


def active_activation(db: Session, tenant_id: str, key: str) -> AdapterActivation | None:
    return db.scalars(
        select(AdapterActivation).where(
            AdapterActivation.tenant_id == tenant_id,
            AdapterActivation.adapter_key == key,
            AdapterActivation.status == "active",
        )
    ).first()


def get_adapter(ctx: TenantContext, db: Session, key: str) -> tuple[Adapter, AdapterContext]:
    """Resolve an active adapter for the tenant or raise AdapterDisabled (callers fall back to copy mode)."""
    adapter = REGISTRY.get(key)
    if adapter is None:
        raise AdapterDisabled(key, "not_allowed")
    activation = active_activation(db, ctx.tenant_id, key)
    if activation is None:
        raise AdapterDisabled(key, "not_active")
    if activation.credentials_encrypted is None:
        raise AdapterDisabled(key, "credentials_missing")
    try:
        credentials = decrypt_json(activation.credentials_encrypted)
    except DecryptionError as exc:
        raise AdapterDisabled(key, "credentials_unreadable") from exc
    return adapter, AdapterContext(
        tenant=ctx,
        db=db,
        activation_id=activation.id,
        adapter_key=key,
        config=dict(activation.config),
        credentials=credentials,
    )


def get_llm(ctx: TenantContext, db: Session) -> LlmClient:
    _adapter, actx = get_adapter(ctx, db, LLM.key)
    return LLM.client(actx)
