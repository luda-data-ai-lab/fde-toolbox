from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.auth.deps import DB
from app.core.exports import attachment
from app.core.pagination import Page
from app.core.tenancy.deps import Ctx, ExportCtx, WriteCtx, path_entity, repo
from app.modules.coachq import service
from app.modules.coachq.models import (
    CoachActionItem,
    CoachCustomQuestion,
    CoachInsight,
    CoachSession,
    CoachSessionQuestion,
    CoachSubject,
)
from app.modules.coachq.schemas import (
    ActionItemIn,
    ActionItemOut,
    ActionItemPatch,
    ActionStatus,
    CustomQuestionIn,
    CustomQuestionOut,
    CustomQuestionPatch,
    InsightIn,
    InsightOut,
    InsightPatch,
    QuestionBankOut,
    SessionIn,
    SessionOut,
    SessionPatch,
    SessionQuestionIn,
    SessionQuestionOut,
    SessionQuestionPatch,
    SessionType,
    SubjectIn,
    SubjectOut,
    SubjectPatch,
    Worksheet,
)
from app.modules.coachq.service import Lang

router = APIRouter(prefix="/t/{tenant_id}/coachq", tags=["coachq"])

SubjectDep = Annotated[CoachSubject, Depends(path_entity(CoachSubject, "subject_id"))]
CustomQuestionDep = Annotated[CoachCustomQuestion, Depends(path_entity(CoachCustomQuestion, "custom_question_id"))]
SessionDep = Annotated[CoachSession, Depends(path_entity(CoachSession, "session_id"))]
QuestionDep = Annotated[CoachSessionQuestion, Depends(path_entity(CoachSessionQuestion, "session_question_id"))]
InsightDep = Annotated[CoachInsight, Depends(path_entity(CoachInsight, "insight_id"))]
ActionItemDep = Annotated[CoachActionItem, Depends(path_entity(CoachActionItem, "action_item_id"))]


def _no_content() -> Response:
    return Response(status_code=204)


@router.get("/question-bank", response_model=QuestionBankOut)
def question_bank(ctx: Ctx, db: DB, asset_id: str | None = None, version: int | None = None) -> QuestionBankOut:
    return service.question_bank(db, asset_id, version)


# subjects


@router.get("/subjects", response_model=Page[SubjectOut])
def list_subjects(
    ctx: Ctx, db: DB, limit: int = 200, cursor: str | None = None, engagement_id: str | None = None
) -> Page[SubjectOut]:
    r = repo(db, ctx, CoachSubject)
    stmt = r.query()
    if engagement_id:
        stmt = stmt.where(CoachSubject.engagement_id == engagement_id)
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[SubjectOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectIn, ctx: WriteCtx, db: DB) -> SubjectOut:
    return SubjectOut.model_validate(service.create_subject(ctx, db, body))


@router.get("/subjects/{subject_id}", response_model=SubjectOut)
def get_subject(obj: SubjectDep) -> SubjectOut:
    return SubjectOut.model_validate(obj)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(obj: SubjectDep, body: SubjectPatch, ctx: WriteCtx, db: DB) -> SubjectOut:
    return SubjectOut.model_validate(service.update_subject(ctx, db, obj, body))


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(obj: SubjectDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_subject(ctx, db, obj)
    return _no_content()


# custom questions


@router.get("/custom-questions", response_model=Page[CustomQuestionOut])
def list_custom_questions(
    ctx: Ctx, db: DB, limit: int = 500, cursor: str | None = None, engagement_id: str | None = None
) -> Page[CustomQuestionOut]:
    r = repo(db, ctx, CoachCustomQuestion)
    stmt = r.query()
    if engagement_id:
        stmt = stmt.where(
            (CoachCustomQuestion.engagement_id == engagement_id) | CoachCustomQuestion.engagement_id.is_(None)
        )
    rows, nxt = r.page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[CustomQuestionOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/custom-questions", response_model=CustomQuestionOut, status_code=201)
def create_custom_question(body: CustomQuestionIn, ctx: WriteCtx, db: DB) -> CustomQuestionOut:
    return CustomQuestionOut.model_validate(service.create_custom_question(ctx, db, body))


@router.get("/custom-questions/{custom_question_id}", response_model=CustomQuestionOut)
def get_custom_question(obj: CustomQuestionDep) -> CustomQuestionOut:
    return CustomQuestionOut.model_validate(obj)


@router.patch("/custom-questions/{custom_question_id}", response_model=CustomQuestionOut)
def update_custom_question(
    obj: CustomQuestionDep, body: CustomQuestionPatch, ctx: WriteCtx, db: DB
) -> CustomQuestionOut:
    return CustomQuestionOut.model_validate(service.update_custom_question(ctx, db, obj, body))


@router.delete("/custom-questions/{custom_question_id}", status_code=204)
def delete_custom_question(obj: CustomQuestionDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_custom_question(ctx, db, obj)
    return _no_content()


# sessions


@router.get("/sessions", response_model=Page[SessionOut])
def list_sessions(
    ctx: Ctx,
    db: DB,
    limit: int = 50,
    cursor: str | None = None,
    engagement_id: str | None = None,
    type: SessionType | None = None,
    subject_id: str | None = None,
    q: str | None = None,
) -> Page[SessionOut]:
    stmt = service.session_filter(ctx, db, engagement_id=engagement_id, type=type, subject_id=subject_id, q=q)
    rows, nxt = repo(db, ctx, CoachSession).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[SessionOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(body: SessionIn, ctx: WriteCtx, db: DB) -> SessionOut:
    return SessionOut.model_validate(service.create_session(ctx, db, body))


@router.get("/sessions/{session_id}", response_model=Worksheet)
def get_session(obj: SessionDep, ctx: Ctx, db: DB) -> Worksheet:
    return service.worksheet(ctx, db, obj)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(obj: SessionDep, body: SessionPatch, ctx: WriteCtx, db: DB) -> SessionOut:
    return SessionOut.model_validate(service.update_session(ctx, db, obj, body))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(obj: SessionDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_session(ctx, db, obj)
    return _no_content()


@router.get("/sessions/{session_id}/export.md")
def export_session(obj: SessionDep, ctx: ExportCtx, db: DB, lang: Lang = "ko") -> Response:
    return attachment(
        service.export_markdown(ctx, db, obj, lang), "text/markdown; charset=utf-8", f"coachq-session-{obj.id}.md"
    )


@router.post("/sessions/{session_id}/questions", response_model=SessionQuestionOut, status_code=201)
def add_question(obj: SessionDep, body: SessionQuestionIn, ctx: WriteCtx, db: DB) -> SessionQuestionOut:
    return SessionQuestionOut.model_validate(service.add_question(ctx, db, obj, body))


@router.patch("/session-questions/{session_question_id}", response_model=SessionQuestionOut)
def update_question(obj: QuestionDep, body: SessionQuestionPatch, ctx: WriteCtx, db: DB) -> SessionQuestionOut:
    return SessionQuestionOut.model_validate(service.update_question(ctx, db, obj, body))


@router.delete("/session-questions/{session_question_id}", status_code=204)
def delete_question(obj: QuestionDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_question(ctx, db, obj)
    return _no_content()


@router.post("/sessions/{session_id}/insights", response_model=InsightOut, status_code=201)
def create_insight(obj: SessionDep, body: InsightIn, ctx: WriteCtx, db: DB) -> InsightOut:
    return InsightOut.model_validate(service.create_insight(ctx, db, obj, body))


@router.patch("/insights/{insight_id}", response_model=InsightOut)
def update_insight(obj: InsightDep, body: InsightPatch, ctx: WriteCtx, db: DB) -> InsightOut:
    return InsightOut.model_validate(service.update_insight(ctx, db, obj, body))


@router.delete("/insights/{insight_id}", status_code=204)
def delete_insight(obj: InsightDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_insight(ctx, db, obj)
    return _no_content()


@router.post("/sessions/{session_id}/action-items", response_model=ActionItemOut, status_code=201)
def create_action_item(obj: SessionDep, body: ActionItemIn, ctx: WriteCtx, db: DB) -> ActionItemOut:
    return ActionItemOut.model_validate(service.create_action_item(ctx, db, obj, body))


# action items


@router.get("/action-items", response_model=Page[ActionItemOut])
def list_action_items(
    ctx: Ctx,
    db: DB,
    limit: int = 200,
    cursor: str | None = None,
    engagement_id: str | None = None,
    session_id: str | None = None,
    status: ActionStatus | None = None,
) -> Page[ActionItemOut]:
    stmt = service.action_item_filter(ctx, db, engagement_id=engagement_id, session_id=session_id, status=status)
    rows, nxt = repo(db, ctx, CoachActionItem).page(limit=limit, cursor=cursor, stmt=stmt)
    return Page(items=[ActionItemOut.model_validate(x) for x in rows], next_cursor=nxt)


@router.get("/action-items/export.csv")
def export_action_items(
    ctx: ExportCtx,
    db: DB,
    engagement_id: str | None = None,
    session_id: str | None = None,
    status: ActionStatus | None = None,
    lang: Lang = "ko",
) -> Response:
    text = service.export_action_items_csv(
        ctx, db, engagement_id=engagement_id, session_id=session_id, status=status, lang=lang
    )
    return attachment(text, "text/csv; charset=utf-8", "coachq-action-items.csv")


@router.get("/action-items/{action_item_id}", response_model=ActionItemOut)
def get_action_item(obj: ActionItemDep) -> ActionItemOut:
    return ActionItemOut.model_validate(obj)


@router.patch("/action-items/{action_item_id}", response_model=ActionItemOut)
def update_action_item(obj: ActionItemDep, body: ActionItemPatch, ctx: WriteCtx, db: DB) -> ActionItemOut:
    return ActionItemOut.model_validate(service.update_action_item(ctx, db, obj, body))


@router.delete("/action-items/{action_item_id}", status_code=204)
def delete_action_item(obj: ActionItemDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_action_item(ctx, db, obj)
    return _no_content()
