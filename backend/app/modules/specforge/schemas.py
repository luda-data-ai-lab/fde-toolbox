from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import AssetRef, ORMModel

DocType = Literal["spec", "devin"]
DocStatus = Literal["draft", "confirmed"]
MAX_MD = 500_000


class SpecSources(BaseModel):
    """Inputs assembled into the draft; every id must belong to the document's tenant and engagement."""

    discovery_session_ids: list[str] = Field(default_factory=list, max_length=100)
    flow_ids: list[str] = Field(default_factory=list, max_length=100)
    interfaces: bool = False
    glossary: bool = False
    requirements: str | None = Field(default=None, max_length=20_000)


class DocumentIn(BaseModel):
    engagement_id: str
    doc_type: DocType
    title: str = Field(min_length=1, max_length=200)
    template_ref: AssetRef | None = None
    rule_pack_refs: list[AssetRef] = Field(default_factory=list, max_length=20)
    sources: SpecSources = Field(default_factory=SpecSources)


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: DocStatus | None = None
    content_md: str | None = Field(default=None, max_length=MAX_MD)
    template_ref: AssetRef | None = None
    rule_pack_refs: list[AssetRef] | None = Field(default=None, max_length=20)
    sources: SpecSources | None = None


class DocumentSummary(ORMModel):
    engagement_id: str
    doc_type: DocType
    title: str
    status: DocStatus
    template_ref: dict[str, Any] | None
    rule_pack_refs: list[dict[str, Any]]
    source_refs: dict[str, Any]
    version_count: int = 0


class DocumentOut(DocumentSummary):
    content_md: str


class VersionIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class VersionSummary(ORMModel):
    document_id: str
    version: int
    note: str | None


class VersionOut(VersionSummary):
    content_md: str


class DiffOut(BaseModel):
    from_label: str
    to_label: str
    diff: str


class TemplateSection(BaseModel):
    key: str
    title: str
    rule: str | None = None


class TemplateOut(BaseModel):
    asset_id: str
    version: int
    asset_key: str
    title: str
    doc: DocType
    sections: list[TemplateSection]


class RulePackOut(BaseModel):
    asset_id: str
    version: int
    asset_key: str
    title: str
    rules: list[str]


class EnrichIn(BaseModel):
    instructions: str | None = Field(default=None, max_length=4000)


class EnrichPromptOut(BaseModel):
    prompt: str
    llm_available: bool


class EnrichOut(BaseModel):
    content_md: str
