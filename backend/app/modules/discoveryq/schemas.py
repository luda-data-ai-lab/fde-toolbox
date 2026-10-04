from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import ORMModel

SessionType = Literal["interview", "coaching"]
SessionStatus = Literal["planned", "in_progress", "done"]
ActionStatus = Literal["open", "in_progress", "done", "cancelled"]
Tags = list[str]


class QuestionRef(BaseModel):
    asset_id: str
    version: int
    question_id: str = Field(min_length=1, max_length=100)


class BankQuestion(BaseModel):
    id: str
    text: str
    tags: list[str] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class BankCategory(BaseModel):
    key: str
    name: str
    questions: list[BankQuestion] = Field(default_factory=list)


class QuestionBankPayload(BaseModel):
    session_types: dict[str, list[str]] = Field(default_factory=dict)
    audiences: list[str] = Field(default_factory=list)
    categories: list[BankCategory] = Field(default_factory=list)


class QuestionBank(QuestionBankPayload):
    asset_id: str
    version: int
    title: str


class BankSummary(BaseModel):
    asset_id: str
    version: int
    title: str


class QuestionBankOut(BaseModel):
    bank: QuestionBank | None
    banks: list[BankSummary]


class SubjectIn(BaseModel):
    engagement_id: str
    name: str = Field(min_length=1, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=100)
    system_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class SubjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=100)
    system_ids: list[str] | None = None
    notes: str | None = None


class SubjectOut(ORMModel):
    tenant_id: str
    engagement_id: str
    name: str
    department: str | None
    job_title: str | None
    system_ids: list[str]
    notes: str | None


class CustomQuestionIn(BaseModel):
    engagement_id: str | None = None
    category: str | None = Field(default=None, max_length=50)
    text: str | None = Field(default=None, min_length=1)
    tags: Tags = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    follow_ups: list[str] | None = None
    source_ref: QuestionRef | None = None

    @model_validator(mode="after")
    def _text_or_source(self) -> "CustomQuestionIn":
        if self.text is None and self.source_ref is None:
            raise ValueError("text or source_ref is required")
        return self


class CustomQuestionPatch(BaseModel):
    category: str | None = Field(default=None, max_length=50)
    text: str | None = Field(default=None, min_length=1)
    tags: Tags | None = None
    audience: list[str] | None = None
    follow_ups: list[str] | None = None


class CustomQuestionOut(ORMModel):
    tenant_id: str
    engagement_id: str | None
    category: str | None
    text: str
    tags: list[str]
    audience: list[str]
    follow_ups: list[str]
    source_ref: QuestionRef | None


class SessionIn(BaseModel):
    engagement_id: str
    type: SessionType = "interview"
    subject_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    session_date: date | None = None
    status: SessionStatus = "planned"
    summary: str | None = None


class SessionPatch(BaseModel):
    type: SessionType | None = None
    subject_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    session_date: date | None = None
    status: SessionStatus | None = None
    summary: str | None = None


class SessionOut(ORMModel):
    tenant_id: str
    engagement_id: str
    type: str
    subject_id: str | None
    title: str
    session_date: date | None
    status: str
    summary: str | None


class SessionQuestionIn(BaseModel):
    """Exactly one of question_ref, custom_question_id or custom_text."""

    question_ref: QuestionRef | None = None
    custom_question_id: str | None = None
    custom_text: str | None = Field(default=None, min_length=1)
    answer: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "SessionQuestionIn":
        given = [x for x in (self.question_ref, self.custom_question_id, self.custom_text) if x is not None]
        if len(given) != 1:
            raise ValueError("exactly one of question_ref, custom_question_id, custom_text is required")
        return self


class SessionQuestionPatch(BaseModel):
    answer: str | None = None
    position: int | None = Field(default=None, ge=0)


class SessionQuestionOut(ORMModel):
    tenant_id: str
    session_id: str
    question_ref: QuestionRef | None
    custom_question_id: str | None
    custom_text: str | None
    text: str
    category: str | None
    follow_ups: list[str]
    answer: str | None
    position: int


class InsightIn(BaseModel):
    session_question_id: str | None = None
    text: str = Field(min_length=1)
    tags: Tags = Field(default_factory=list)


class InsightPatch(BaseModel):
    session_question_id: str | None = None
    text: str | None = Field(default=None, min_length=1)
    tags: Tags | None = None


class InsightOut(ORMModel):
    tenant_id: str
    session_id: str
    session_question_id: str | None
    text: str
    tags: list[str]


class ActionItemIn(BaseModel):
    insight_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    assignee: str | None = Field(default=None, max_length=100)
    due: date | None = None
    status: ActionStatus = "open"


class ActionItemPatch(BaseModel):
    insight_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    assignee: str | None = Field(default=None, max_length=100)
    due: date | None = None
    status: ActionStatus | None = None


class ActionItemOut(ORMModel):
    tenant_id: str
    session_id: str
    insight_id: str | None
    title: str
    assignee: str | None
    due: date | None
    status: str


class Worksheet(BaseModel):
    session: SessionOut
    subject: SubjectOut | None
    questions: list[SessionQuestionOut]
    insights: list[InsightOut]
    action_items: list[ActionItemOut]
