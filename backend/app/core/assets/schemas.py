from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import ORMModel

AssetType = Literal[
    "question_bank",
    "flow_template",
    "if_template",
    "upper_ontology",
    "glossary_template",
    "spec_template",
    "rule_pack",
    "agent_template",
]
AssetStatus = Literal["draft", "published", "deprecated"]

PACKAGE_SCHEMA_VERSION = 1


class AssetIn(BaseModel):
    asset_type: AssetType
    asset_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    title: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    status: AssetStatus = "draft"
    change_note: str | None = None


class AssetVersionIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    payload: dict[str, Any]
    status: AssetStatus = "draft"
    change_note: str = Field(min_length=1)


class AssetVersionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    payload: dict[str, Any] | None = None
    status: AssetStatus | None = None
    change_note: str | None = None


class AssetOut(ORMModel):
    asset_id: str
    version: int
    asset_type: str
    asset_key: str
    title: str
    payload: dict[str, Any]
    status: str
    change_note: str | None


class AssetSummary(BaseModel):
    asset_id: str
    asset_type: str
    asset_key: str
    title: str
    latest_version: int
    latest_status: str
    versions: int


class AssetDiff(BaseModel):
    asset_id: str
    from_version: int
    to_version: int
    payload_diff: str
    prompt_diff: str | None


class PackageRow(BaseModel):
    table: str
    row: dict[str, Any]


class AssetPackage(BaseModel):
    schema_version: int = PACKAGE_SCHEMA_VERSION
    kind: Literal["asset_package"] = "asset_package"
    assets: list[dict[str, Any]]
    related: list[PackageRow] = Field(default_factory=list)


class ImportResult(BaseModel):
    created: int
    skipped: int
