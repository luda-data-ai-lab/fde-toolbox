from dataclasses import dataclass, field

from app.core.users.models import User

WRITE_ROLES = frozenset({"luda_admin", "fde"})
AUDIT_VIEW_ROLES = frozenset({"luda_admin", "fde", "client_admin"})
EXPORT_ROLES = frozenset({"luda_admin", "fde", "client_admin"})


@dataclass(frozen=True)
class Principal:
    user: User
    ip: str | None
    allowed_tenant_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def user_id(self) -> str:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def is_admin(self) -> bool:
        return self.user.role == "luda_admin"


@dataclass(frozen=True)
class TenantContext:
    principal: Principal
    tenant_id: str

    @property
    def user_id(self) -> str:
        return self.principal.user_id

    @property
    def role(self) -> str:
        return self.principal.role

    @property
    def ip(self) -> str | None:
        return self.principal.ip

    @property
    def can_write(self) -> bool:
        return self.role in WRITE_ROLES
