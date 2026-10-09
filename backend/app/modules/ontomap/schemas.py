from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schemas import ORMModel

TermStatus = Literal["candidate", "confirmed", "deprecated"]
CandidateStatus = Literal["open", "accepted", "merged", "ignored"]
CandidateSource = Literal["discovery_session", "manual"]


def _clean(value: str) -> str:
    return " ".join(value.split())


class AliasIn(BaseModel):
    alias: str = Field(min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=100)

    @field_validator("alias")
    @classmethod
    def _alias(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("empty")
        return v

    @field_validator("department")
    @classmethod
    def _department(cls, v: str | None) -> str | None:
        return _clean(v) or None if v is not None else None


class AliasOut(BaseModel):
    alias: str
    department: str | None = None


class TermFields(BaseModel):
    definition: str | None = Field(default=None, max_length=5000)
    abbreviation: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class TermIn(TermFields):
    term: str = Field(min_length=1, max_length=200)
    status: TermStatus = "confirmed"
    concept_id: str | None = None
    aliases: list[AliasIn] = Field(default_factory=list, max_length=100)

    @field_validator("term")
    @classmethod
    def _term(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("empty")
        return v


class TermPatch(TermFields):
    term: str | None = Field(default=None, min_length=1, max_length=200)
    status: TermStatus | None = None
    concept_id: str | None = None
    aliases: list[AliasIn] | None = Field(default=None, max_length=100)

    @field_validator("term")
    @classmethod
    def _term(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = _clean(v)
        if not v:
            raise ValueError("empty")
        return v


class TermOut(ORMModel):
    tenant_id: str
    term: str
    definition: str | None
    abbreviation: str | None
    status: TermStatus
    concept_id: str | None
    source_type: str | None
    source_id: str | None
    notes: str | None
    aliases: list[AliasOut] = Field(default_factory=list)


class SimilarTerm(BaseModel):
    term_id: str
    term: str
    matched: str
    score: int


class CandidateIn(BaseModel):
    kind: Literal["term"] = "term"
    name: str = Field(min_length=1, max_length=200)
    source_type: CandidateSource = "manual"
    source_id: str | None = None
    session_question_id: str | None = None
    context: str | None = Field(default=None, max_length=2000)
    definition: str | None = Field(default=None, max_length=5000)
    department: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("empty")
        return v


class CandidateOut(ORMModel):
    tenant_id: str
    kind: str
    name: str
    payload: dict[str, Any]
    source_type: str
    source_id: str | None
    status: CandidateStatus
    resolved_into_id: str | None
    similar: list[SimilarTerm] = Field(default_factory=list)


class AcceptIn(TermFields):
    term: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["candidate", "confirmed"] = "confirmed"
    aliases: list[AliasIn] = Field(default_factory=list, max_length=100)


class MergeIn(BaseModel):
    term_id: str
    department: str | None = Field(default=None, max_length=100)


class ImportRowValues(BaseModel):
    term: str | None = None
    definition: str | None = None
    abbreviation: str | None = None
    aliases: list[AliasOut] = Field(default_factory=list)
    status: TermStatus | None = None
    notes: str | None = None


class ImportRowError(BaseModel):
    field: str
    code: str


class ImportRow(BaseModel):
    row: int
    values: ImportRowValues
    action: Literal["create", "update", "skip"]
    errors: list[ImportRowError] = Field(default_factory=list)


class ImportSummary(BaseModel):
    total: int
    valid: int
    invalid: int
    create: int
    update: int


class ImportResult(BaseModel):
    filename: str
    applied: bool
    summary: ImportSummary
    rows: list[ImportRow]


ConceptStatus = Literal["draft", "confirmed", "deprecated"]
DataType = Literal["string", "integer", "decimal", "boolean", "date", "datetime", "code"]
Cardinality = Literal["1:1", "1:N", "N:M"]


def _name(v: str) -> str:
    v = _clean(v)
    if not v:
        raise ValueError("empty")
    return v


class UpperRef(BaseModel):
    """Concept of a specific upper-ontology asset version."""

    asset_id: str
    version: int
    concept_key: str = Field(min_length=1, max_length=100)


class ConceptFields(BaseModel):
    definition: str | None = Field(default=None, max_length=5000)
    owner_dept: str | None = Field(default=None, max_length=100)


class ConceptIn(ConceptFields):
    name: str = Field(min_length=1, max_length=200)
    status: ConceptStatus = "draft"
    parent_ref: UpperRef | None = None
    parent_concept_id: str | None = None

    _n = field_validator("name")(_name)

    @model_validator(mode="after")
    def _one_parent(self) -> Self:
        if self.parent_ref is not None and self.parent_concept_id is not None:
            raise ValueError("parent_ref and parent_concept_id are exclusive")
        return self


class ConceptPatch(ConceptFields):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: ConceptStatus | None = None
    parent_ref: UpperRef | None = None
    parent_concept_id: str | None = None
    id_attribute_id: str | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return None if v is None else _name(v)

    @model_validator(mode="after")
    def _one_parent(self) -> Self:
        if self.parent_ref is not None and self.parent_concept_id is not None:
            raise ValueError("parent_ref and parent_concept_id are exclusive")
        return self


class ConceptOut(ORMModel):
    tenant_id: str
    name: str
    definition: str | None
    parent_ref: UpperRef | None
    parent_concept_id: str | None
    id_attribute_id: str | None
    owner_dept: str | None
    status: ConceptStatus


class AttributeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    data_type: DataType = "string"
    unit: str | None = Field(default=None, max_length=50)
    required: bool = False
    constraints: dict[str, Any] = Field(default_factory=dict)

    _n = field_validator("name")(_name)


class AttributePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    data_type: DataType | None = None
    unit: str | None = Field(default=None, max_length=50)
    required: bool | None = None
    constraints: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return None if v is None else _name(v)


class AttributeOut(ORMModel):
    tenant_id: str
    concept_id: str
    name: str
    data_type: DataType
    unit: str | None
    required: bool
    constraints: dict[str, Any]


class RelationIn(BaseModel):
    source_concept_id: str
    name: str = Field(min_length=1, max_length=200)
    target_concept_id: str
    cardinality: Cardinality = "1:N"
    inverse_name: str | None = Field(default=None, max_length=200)

    _n = field_validator("name")(_name)


class RelationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_concept_id: str | None = None
    cardinality: Cardinality | None = None
    inverse_name: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return None if v is None else _name(v)


class RelationOut(ORMModel):
    tenant_id: str
    source_concept_id: str
    name: str
    target_concept_id: str
    cardinality: Cardinality
    inverse_name: str | None


class UpperConcept(BaseModel):
    key: str
    name: str
    definition: str | None = None
    parent_key: str | None = None
    iri_local: str | None = None
    properties: list[str] = Field(default_factory=list)


class UpperRelation(BaseModel):
    source: str
    name: str
    target: str


class UpperOntologyOut(BaseModel):
    asset_id: str
    version: int
    asset_key: str
    title: str
    namespace: str | None
    concepts: list[UpperConcept]
    relations: list[UpperRelation]


class Ancestor(BaseModel):
    kind: Literal["concept", "upper"]
    id: str
    name: str
    ontology: str | None = None


class InheritedProperty(BaseModel):
    name: str
    data_type: str | None = None
    origin: str


class InheritedRelation(BaseModel):
    name: str
    target: str
    origin: str


class ValidationIssue(BaseModel):
    code: Literal["orphan_concept", "duplicate_concept", "term_without_definition", "dangling_upper_ref"]
    target_type: Literal["onto_concept", "onto_term"]
    target_id: str
    name: str


class ConceptDetail(ConceptOut):
    attributes: list[AttributeOut]
    relations: list[RelationOut]
    ancestors: list[Ancestor]
    inherited_properties: list[InheritedProperty]
    inherited_relations: list[InheritedRelation]
    terms: list[TermOut]
    warnings: list[ValidationIssue]


class ValidationReport(BaseModel):
    issues: list[ValidationIssue]
