from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel

SYSTEM_TYPES = ("MES", "ERP", "LIMS", "WMS", "SCADA", "GROUPWARE", "OTHER")
HOSTING_TYPES = ("on_premise", "cloud")


class System(TenantScopedModel):
    __tablename__ = "systems"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="OTHER")
    owner_dept: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hosting: Mapped[str | None] = mapped_column(String(20), nullable=True)
    db_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
