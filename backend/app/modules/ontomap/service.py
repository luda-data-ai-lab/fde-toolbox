import re
from collections import defaultdict
from typing import Any

from fastapi import UploadFile
from rapidfuzz import fuzz
from sqlalchemy import Select, delete, exists, func, or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.exports import csv_text
from app.core.files.service import read_upload
from app.core.refs import ensure_tenant_ref
from app.core.schemas import dump_patch
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.modules.ontomap import excel
from app.modules.ontomap.models import OntoCandidate, OntoTerm, OntoTermAlias
from app.modules.ontomap.schemas import (
    AcceptIn,
    AliasIn,
    AliasOut,
    CandidateIn,
    CandidateOut,
    ImportResult,
    ImportRow,
    ImportRowError,
    ImportRowValues,
    ImportSummary,
    MergeIn,
    SimilarTerm,
    TermIn,
    TermOut,
    TermPatch,
)

WORKBOOK_EXTENSIONS = {"xlsx", "xlsm"}
MAX_SIMILAR = 5
_NON_WORD = re.compile(r"[\W_]+")


def normalize(name: str) -> str:
    return _NON_WORD.sub("", name).lower()


def _terms(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoTerm]:
    return TenantScopedRepository(db, ctx, OntoTerm)


def _aliases(db: Session, ctx: TenantContext) -> TenantScopedRepository[OntoTermAlias]:
    return TenantScopedRepository(db, ctx, OntoTermAlias)


def _alias_map(db: Session, ctx: TenantContext, term_ids: list[str] | None = None) -> dict[str, list[OntoTermAlias]]:
    repo = _aliases(db, ctx)
    stmt = repo.query().order_by(OntoTermAlias.created_at, OntoTermAlias.id)
    if term_ids is not None:
        if not term_ids:
            return {}
        stmt = stmt.where(OntoTermAlias.term_id.in_(term_ids))
    out: dict[str, list[OntoTermAlias]] = defaultdict(list)
    for a in repo.all(stmt):
        out[a.term_id].append(a)
    return out


def terms_out(db: Session, ctx: TenantContext, terms: list[OntoTerm]) -> list[TermOut]:
    aliases = _alias_map(db, ctx, [t.id for t in terms])
    return [
        TermOut.model_validate(t).model_copy(
            update={"aliases": [AliasOut(alias=a.alias, department=a.department) for a in aliases.get(t.id, [])]}
        )
        for t in terms
    ]


def term_filter(
    ctx: TenantContext, db: Session, *, status: str | None, q: str | None, department: str | None
) -> Select[OntoTerm]:
    stmt = _terms(db, ctx).query()
    if status:
        stmt = stmt.where(OntoTerm.status == status)
    if q:
        like = f"%{q.strip().lower()}%"
        alias_match = exists().where(
            OntoTermAlias.term_id == OntoTerm.id,
            OntoTermAlias.tenant_id == ctx.tenant_id,
            func.lower(OntoTermAlias.alias).like(like),
        )
        stmt = stmt.where(
            or_(
                func.lower(OntoTerm.term).like(like),
                func.lower(OntoTerm.abbreviation).like(like),
                func.lower(OntoTerm.definition).like(like),
                alias_match,
            )
        )
    if department:
        stmt = stmt.where(
            exists().where(
                OntoTermAlias.term_id == OntoTerm.id,
                OntoTermAlias.tenant_id == ctx.tenant_id,
                OntoTermAlias.department == department,
            )
        )
    return stmt


def find_term(db: Session, ctx: TenantContext, name: str) -> OntoTerm | None:
    repo = _terms(db, ctx)
    return repo.db.scalars(repo.query().where(func.lower(OntoTerm.term) == name.lower())).first()


def _ensure_unique(db: Session, ctx: TenantContext, name: str, exclude_id: str | None = None) -> None:
    existing = find_term(db, ctx, name)
    if existing is not None and existing.id != exclude_id:
        raise AppError(409, "term_taken", detail={"field": "term", "term_id": existing.id})


def _dedupe(aliases: list[AliasIn], term: str) -> list[AliasIn]:
    seen: set[tuple[str, str | None]] = {(normalize(term), None)}
    out: list[AliasIn] = []
    for a in aliases:
        key = (normalize(a.alias), a.department)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def _replace_aliases(db: Session, ctx: TenantContext, term: OntoTerm, aliases: list[AliasIn]) -> None:
    db.execute(delete(OntoTermAlias).where(OntoTermAlias.tenant_id == ctx.tenant_id, OntoTermAlias.term_id == term.id))
    repo = _aliases(db, ctx)
    for a in _dedupe(aliases, term.term):
        repo.create(term_id=term.id, alias=a.alias, department=a.department)


def _add_aliases(db: Session, ctx: TenantContext, term: OntoTerm, aliases: list[AliasIn]) -> int:
    current = _alias_map(db, ctx, [term.id]).get(term.id, [])
    seen = {(normalize(term.term), None)} | {(normalize(a.alias), a.department) for a in current}
    repo = _aliases(db, ctx)
    added = 0
    for a in aliases:
        key = (normalize(a.alias), a.department)
        if key in seen:
            continue
        seen.add(key)
        repo.create(term_id=term.id, alias=a.alias, department=a.department)
        added += 1
    return added


def _create_term(
    db: Session,
    ctx: TenantContext,
    body: TermIn,
    source_type: str | None = "manual",
    source_id: str | None = None,
) -> OntoTerm:
    _ensure_unique(db, ctx, body.term)
    term = _terms(db, ctx).create(**body.model_dump(exclude={"aliases"}), source_type=source_type, source_id=source_id)
    _replace_aliases(db, ctx, term, body.aliases)
    return term


@audited("ontomap.term_create", "onto_term")
def create_term(ctx: TenantContext, db: Session, body: TermIn) -> OntoTerm:
    return _create_term(db, ctx, body)


@audited("ontomap.term_update", "onto_term")
def update_term(ctx: TenantContext, db: Session, term: OntoTerm, body: TermPatch) -> OntoTerm:
    values = dump_patch(body)
    aliases = values.pop("aliases", None)
    if values.get("term") is None:
        values.pop("term", None)
    else:
        _ensure_unique(db, ctx, values["term"], exclude_id=term.id)
    if "status" in values and values["status"] is None:
        values.pop("status")
    _terms(db, ctx).update(term, **values)
    if aliases is not None:
        _replace_aliases(db, ctx, term, body.aliases or [])
    return term


@audited("ontomap.term_delete", "onto_term")
def delete_term(ctx: TenantContext, db: Session, term: OntoTerm) -> str:
    term_id = term.id
    db.execute(delete(OntoTermAlias).where(OntoTermAlias.tenant_id == ctx.tenant_id, OntoTermAlias.term_id == term_id))
    _terms(db, ctx).delete(term)
    return term_id


def similar_terms(db: Session, ctx: TenantContext, names: list[str]) -> dict[str, list[SimilarTerm]]:
    """Merge suggestions: fuzzy match of normalized names against term names and aliases."""
    if not names:
        return {}
    threshold = get_settings().onto_similarity_threshold
    terms = _terms(db, ctx).all()
    aliases = _alias_map(db, ctx)
    labels = [(t, [t.term, *(a.alias for a in aliases.get(t.id, []))]) for t in terms]
    out: dict[str, list[SimilarTerm]] = {}
    for name in set(names):
        key = normalize(name)
        hits: list[SimilarTerm] = []
        for term, texts in labels:
            best: tuple[int, str] | None = None
            for text in texts:
                other = normalize(text)
                if not key or not other:
                    continue
                score = 100 if key == other else round(fuzz.ratio(key, other))
                if score >= threshold and (best is None or score > best[0]):
                    best = (score, text)
            if best is not None:
                hits.append(SimilarTerm(term_id=term.id, term=term.term, matched=best[1], score=best[0]))
        hits.sort(key=lambda h: (-h.score, h.term))
        out[name] = hits[:MAX_SIMILAR]
    return out


def candidates_out(db: Session, ctx: TenantContext, rows: list[OntoCandidate]) -> list[CandidateOut]:
    similar = similar_terms(db, ctx, [c.name for c in rows if c.status == "open"])
    return [
        CandidateOut.model_validate(c).model_copy(update={"similar": similar.get(c.name, [])})
        if c.status == "open"
        else CandidateOut.model_validate(c)
        for c in rows
    ]


def candidate_filter(
    ctx: TenantContext, db: Session, *, status: str | None, source_type: str | None, source_id: str | None
) -> Select[OntoCandidate]:
    stmt = TenantScopedRepository(db, ctx, OntoCandidate).query()
    if status:
        stmt = stmt.where(OntoCandidate.status == status)
    if source_type:
        stmt = stmt.where(OntoCandidate.source_type == source_type)
    if source_id:
        stmt = stmt.where(OntoCandidate.source_id == source_id)
    return stmt


@audited("ontomap.candidate_create", "onto_candidate")
def _create_candidate(ctx: TenantContext, db: Session, body: CandidateIn) -> OntoCandidate:
    payload: dict[str, Any] = {
        k: v
        for k, v in body.model_dump(include={"session_question_id", "context", "definition", "department"}).items()
        if v
    }
    return TenantScopedRepository(db, ctx, OntoCandidate).create(
        kind=body.kind, name=body.name, payload=payload, source_type=body.source_type, source_id=body.source_id
    )


def register_candidate(ctx: TenantContext, db: Session, body: CandidateIn) -> tuple[OntoCandidate, bool]:
    """Idempotent per (kind, source, name): re-registering returns the existing candidate."""
    if body.source_type == "coach_session":
        if body.source_id is None:
            raise AppError(422, "invalid_reference", detail={"field": "source_id"})
        ensure_tenant_ref(db, ctx, "coach_sessions", body.source_id, "source_id")
        ensure_tenant_ref(db, ctx, "coach_session_questions", body.session_question_id, "session_question_id")
    elif body.source_id is not None or body.session_question_id is not None:
        raise AppError(422, "invalid_reference", detail={"field": "source_id"})
    repo = TenantScopedRepository(db, ctx, OntoCandidate)
    source_match = (
        OntoCandidate.source_id.is_(None) if body.source_id is None else OntoCandidate.source_id == body.source_id
    )
    existing = db.scalars(
        repo.query().where(
            OntoCandidate.kind == body.kind,
            OntoCandidate.source_type == body.source_type,
            source_match,
            OntoCandidate.name == body.name,
        )
    ).first()
    if existing is not None:
        return existing, False
    return _create_candidate(ctx, db, body), True


def _ensure_open(candidate: OntoCandidate) -> None:
    if candidate.status != "open":
        raise AppError(409, "candidate_resolved")


@audited("ontomap.candidate_accept", "onto_candidate")
def accept_candidate(ctx: TenantContext, db: Session, candidate: OntoCandidate, body: AcceptIn) -> OntoCandidate:
    _ensure_open(candidate)
    dept = candidate.payload.get("department")
    name = body.term or candidate.name
    aliases = list(body.aliases)
    if name != candidate.name or dept:
        aliases.append(AliasIn(alias=candidate.name, department=dept))
    term_in = TermIn(
        term=name,
        definition=body.definition if body.definition is not None else candidate.payload.get("definition"),
        abbreviation=body.abbreviation,
        notes=body.notes,
        status=body.status,
        aliases=aliases,
    )
    term = _create_term(db, ctx, term_in, source_type=candidate.source_type, source_id=candidate.source_id)
    candidate.status = "accepted"
    candidate.resolved_into_id = term.id
    db.flush()
    return candidate


@audited("ontomap.candidate_merge", "onto_candidate")
def merge_candidate(ctx: TenantContext, db: Session, candidate: OntoCandidate, body: MergeIn) -> OntoCandidate:
    _ensure_open(candidate)
    term = _terms(db, ctx).get(body.term_id)
    if term is None:
        raise AppError(422, "invalid_reference", detail={"field": "term_id"})
    dept = body.department if body.department is not None else candidate.payload.get("department")
    _add_aliases(db, ctx, term, [AliasIn(alias=candidate.name, department=dept)])
    candidate.status = "merged"
    candidate.resolved_into_id = term.id
    db.flush()
    return candidate


@audited("ontomap.candidate_ignore", "onto_candidate")
def ignore_candidate(ctx: TenantContext, db: Session, candidate: OntoCandidate) -> OntoCandidate:
    _ensure_open(candidate)
    candidate.status = "ignored"
    db.flush()
    return candidate


@audited("ontomap.candidate_reopen", "onto_candidate")
def reopen_candidate(ctx: TenantContext, db: Session, candidate: OntoCandidate) -> OntoCandidate:
    if candidate.status != "ignored":
        raise AppError(409, "candidate_resolved")
    candidate.status = "open"
    db.flush()
    return candidate


def _row_values(row: excel.SheetRow) -> tuple[ImportRowValues, list[ImportRowError]]:
    v = row.values
    errors: list[ImportRowError] = []
    status_raw = v.get("status")
    status = excel.parse_status(status_raw)
    if status_raw is not None and status is None:
        errors.append(ImportRowError(field="status", code="invalid_status"))
    term = " ".join((v.get("term") or "").split()) or None
    if term is None:
        errors.append(ImportRowError(field="term", code="required"))
    for key, limit in (("term", 200), ("abbreviation", 50), ("definition", 5000), ("notes", 5000)):
        value = v.get(key)
        if value is not None and len(value) > limit:
            errors.append(ImportRowError(field=key, code="too_long"))
    parsed = excel.parse_aliases(v.get("aliases"))
    aliases = [{"alias": a[:200], "department": d[:100] if d else None} for a, d in parsed]
    values = ImportRowValues.model_validate(
        {
            "term": term,
            "definition": v.get("definition"),
            "abbreviation": v.get("abbreviation"),
            "aliases": aliases,
            "status": status,
            "notes": v.get("notes"),
        }
    )
    return values, errors


def _analyze(db: Session, ctx: TenantContext, filename: str, data: bytes) -> ImportResult:
    try:
        parsed = excel.parse_workbook(data)
    except excel.WorkbookError as exc:
        raise AppError(400, exc.code, detail=exc.detail) from exc
    existing = {t.term.lower() for t in _terms(db, ctx).all()}
    seen: set[str] = set()
    rows: list[ImportRow] = []
    for sheet_row in parsed:
        values, errors = _row_values(sheet_row)
        if values.term is not None:
            key = values.term.lower()
            if key in seen:
                errors.append(ImportRowError(field="term", code="duplicate_in_file"))
            seen.add(key)
        action = "skip" if errors else ("update" if values.term and values.term.lower() in existing else "create")
        rows.append(ImportRow(row=sheet_row.row, values=values, action=action, errors=errors))
    valid = [r for r in rows if not r.errors]
    summary = ImportSummary(
        total=len(rows),
        valid=len(valid),
        invalid=len(rows) - len(valid),
        create=sum(r.action == "create" for r in rows),
        update=sum(r.action == "update" for r in rows),
    )
    return ImportResult(filename=filename, applied=False, summary=summary, rows=rows)


def import_workbook(ctx: TenantContext, db: Session, file: UploadFile, apply: bool) -> ImportResult:
    """Dry run by default; with ``apply`` valid rows are created or merged into existing terms."""
    name, data = read_upload(file, WORKBOOK_EXTENSIONS)
    result = _analyze(db, ctx, name, data)
    if not apply:
        return result
    try:
        for row in result.rows:
            v = row.values
            if row.action == "skip" or v.term is None:
                continue
            aliases = [AliasIn(alias=a.alias, department=a.department) for a in v.aliases]
            if row.action == "create":
                _create_term(
                    db,
                    ctx,
                    TermIn(
                        term=v.term,
                        definition=v.definition,
                        abbreviation=v.abbreviation,
                        notes=v.notes,
                        status=v.status or "confirmed",
                        aliases=aliases,
                    ),
                    source_type="import",
                )
                continue
            term = find_term(db, ctx, v.term)
            if term is None:
                continue
            fields = {"definition": v.definition, "abbreviation": v.abbreviation, "notes": v.notes, "status": v.status}
            updates = {k: value for k, value in fields.items() if value is not None}
            _terms(db, ctx).update(term, **updates)
            _add_aliases(db, ctx, term, aliases)
        record(
            db,
            action="ontomap.terms_import",
            actor_id=ctx.user_id,
            tenant_id=ctx.tenant_id,
            target_type="onto_term",
            detail={"filename": name, "create": result.summary.create, "update": result.summary.update},
            ip=ctx.ip,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result.model_copy(update={"applied": True})


def _export_rows(db: Session, ctx: TenantContext, status: str | None) -> list[list[Any]]:
    repo = _terms(db, ctx)
    stmt = repo.query().order_by(OntoTerm.term)
    if status:
        stmt = stmt.where(OntoTerm.status == status)
    terms = repo.all(stmt)
    aliases = _alias_map(db, ctx, [t.id for t in terms])
    return [
        [
            t.term,
            t.definition,
            excel.format_aliases([(a.alias, a.department) for a in aliases.get(t.id, [])]),
            t.abbreviation,
            None,
            t.notes,
            excel.STATUS_LABELS.get(t.status, t.status),
        ]
        for t in terms
    ]


def _record_export(ctx: TenantContext, db: Session, fmt: str) -> None:
    record(
        db,
        action="ontomap.terms_export",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="onto_term",
        detail={"format": fmt},
        ip=ctx.ip,
    )
    db.commit()


def export_workbook(ctx: TenantContext, db: Session, status: str | None) -> bytes:
    data = excel.build_workbook(_export_rows(db, ctx, status), with_status=True)
    _record_export(ctx, db, "xlsx")
    return data


def export_csv(ctx: TenantContext, db: Session, status: str | None) -> str:
    headers = [h for _, h in excel.COLUMNS] + [excel.STATUS_COLUMN[1]]
    text = csv_text(headers, _export_rows(db, ctx, status))
    _record_export(ctx, db, "csv")
    return text


def template_workbook() -> bytes:
    return excel.build_workbook([], with_status=False)
