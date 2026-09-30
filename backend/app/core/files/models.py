from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantScopedModel


class StoredFile(TenantScopedModel):
    __tablename__ = "files"

    owner_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
