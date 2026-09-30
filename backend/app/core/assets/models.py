from typing import Any

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AssetModel

ASSET_TYPES = (
    "question_bank",
    "flow_template",
    "if_template",
    "upper_ontology",
    "glossary_template",
    "spec_template",
    "rule_pack",
    "agent_template",
)
ASSET_STATUSES = ("draft", "published", "deprecated")


class AssetItem(AssetModel):
    __tablename__ = "asset_items"
    __table_args__ = (UniqueConstraint("asset_id", "version", name="uq_asset_items_asset_version"),)

    asset_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    asset_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
