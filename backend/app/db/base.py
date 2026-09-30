import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class TenantScopedMixin:
    """Customer data. Every row belongs to exactly one tenant."""

    @declared_attr
    def tenant_id(cls) -> Mapped[str]:
        return mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)


class AssetMixin:
    """LUDA asset data. Never carries a tenant_id; versioned by (asset_id, version)."""

    @declared_attr
    def asset_id(cls) -> Mapped[str]:
        return mapped_column(String(36), nullable=False, index=True)

    @declared_attr
    def version(cls) -> Mapped[int]:
        return mapped_column(Integer, nullable=False)


GLOBAL_TABLES: frozenset[str] = frozenset({"tenants", "users", "user_tenant_assignments", "audit_logs"})


class TenantScopedModel(TenantScopedMixin, Base):
    __abstract__ = True


class AssetModel(AssetMixin, Base):
    __abstract__ = True
