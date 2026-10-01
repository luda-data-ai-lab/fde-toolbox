from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import ORMModel

TermStatus = Literal["candidate", "confirmed", "deprecated"]
CandidateStatus = Literal["open", "accepted", "merged", "ignored"]
CandidateSource = Literal["coach_session", "manual"]


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
