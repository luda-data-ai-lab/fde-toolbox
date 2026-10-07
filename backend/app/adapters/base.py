"""Adapter contract. Every outbound network call lives in an adapter under app/adapters/."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from app.core.audit.service import record
from app.core.errors import AppError
from app.core.tenancy.context import TenantContext

JsonScalar = str | int | float | bool | None
FieldKind = Literal["text", "int", "secret"]


class AdapterDisabled(AppError):  # noqa: N818
    """The adapter is not allowed, not activated, or has no usable credentials; use the offline path."""

    def __init__(self, adapter_key: str, reason: str) -> None:
        super().__init__(409, "adapter_disabled", detail={"adapter": adapter_key, "reason": reason})
        self.adapter_key = adapter_key
        self.reason = reason


class AdapterCallError(AppError):
    def __init__(self, adapter_key: str, reason: str) -> None:
        super().__init__(502, "adapter_call_failed", detail={"adapter": adapter_key, "reason": reason})


@dataclass(frozen=True)
class EgressNotice:
    """What leaves the deployment, where it goes and which features send it (shown before approval)."""

    destination: str
    data_kinds: tuple[str, ...]
    features: tuple[str, ...]

    def as_dict(self) -> dict[str, str | list[str]]:
        return {"destination": self.destination, "data_kinds": list(self.data_kinds), "features": list(self.features)}


@dataclass(frozen=True)
class ConfigField:
    name: str
    kind: FieldKind
    required: bool = True
    default: JsonScalar = None


@dataclass(frozen=True)
class HealthResult:
    ok: bool
    message: str | None = None
    latency_ms: int = 0


@dataclass
class AdapterContext:
    """An activated adapter bound to one tenant. Credentials are decrypted only for the call's lifetime."""

    tenant: TenantContext
    db: Session
    activation_id: str
    adapter_key: str
    config: dict[str, JsonScalar]
    credentials: dict[str, str] = field(repr=False)

    def record_call(
        self,
        feature: str,
        *,
        request_bytes: int,
        response_bytes: int,
        ok: bool,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """Append and commit a call audit entry (sizes and outcome only, never the payload).

        Committed immediately so the trail survives a failing feature; call adapters before
        the feature's own writes.
        """
        detail: dict[str, JsonScalar] = {
            "adapter": self.adapter_key,
            "feature": feature,
            "request_bytes": request_bytes,
            "response_bytes": response_bytes,
            "result": "ok" if ok else "error",
            "duration_ms": duration_ms,
        }
        if error:
            detail["error"] = error
        record(
            self.db,
            action="adapter.call",
            actor_id=self.tenant.user_id,
            tenant_id=self.tenant.tenant_id,
            target_type="adapter_activation",
            target_id=self.activation_id,
            detail=detail,
            ip=self.tenant.ip,
        )
        self.db.commit()


class Adapter(Protocol):
    key: str
    display_name: str
    implemented: bool
    config_fields: tuple[ConfigField, ...]

    def data_egress_notice(self) -> EgressNotice: ...

    def validate_config(
        self, config: Mapping[str, JsonScalar], credentials: Mapping[str, str]
    ) -> tuple[dict[str, JsonScalar], dict[str, str]]:
        """Return normalised (config, credentials) or raise AppError(422, "invalid_adapter_config")."""
        ...

    def health_check(self, ctx: AdapterContext) -> HealthResult: ...


def invalid_config(field_name: str) -> AppError:
    return AppError(422, "invalid_adapter_config", detail={"field": field_name})
