import difflib
import io
import zipfile
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterDisabled
from app.adapters.registry import get_llm
from app.core.assets.models import AssetItem
from app.core.audit.service import audited, record
from app.core.errors import AppError
from app.core.schemas import AssetRef
from app.core.tenancy.context import TenantContext
from app.core.tenancy.repository import TenantScopedRepository
from app.core.tenants.models import Engagement
from app.modules.specforge import assemble
from app.modules.specforge.models import SpecDocument, SpecVersion
from app.modules.specforge.schemas import (
    DiffOut,
    DocumentIn,
    DocumentOut,
    DocumentPatch,
    DocumentSummary,
    EnrichIn,
    RulePackOut,
    SpecSources,
    TemplateOut,
    TemplateSection,
    VersionIn,
)

TEMPLATE_TYPE = "spec_template"
RULE_PACK_TYPE = "rule_pack"
FILENAMES = {"spec": "Spec.md", "devin": "Devin.md"}
ENRICH_PROMPT = """You are helping a Forward Deployed Engineer finish a {doc} document for an AI coding agent.
Improve the Markdown draft below: fill sections marked "> TODO" from the information already present,
tighten wording, and keep every heading, table and the "작업 규칙"/rules section exactly as given.
Do not invent systems, interfaces, terms or requirements that the draft does not mention; leave a
"> TODO" where information is missing. Keep the document language (Korean if the draft is Korean).
Return only the full Markdown document.
{extra}
--- DRAFT ---
{content}"""


def _docs(db: Session, ctx: TenantContext) -> TenantScopedRepository[SpecDocument]:
    return TenantScopedRepository(db, ctx, SpecDocument)


def _versions(db: Session, ctx: TenantContext) -> TenantScopedRepository[SpecVersion]:
    return TenantScopedRepository(db, ctx, SpecVersion)


def _version_count(db: Session, ctx: TenantContext, doc: SpecDocument) -> int:
    stmt = (
        select(func.count())
        .select_from(SpecVersion)
        .where(SpecVersion.tenant_id == ctx.tenant_id, SpecVersion.document_id == doc.id)
    )
    return int(db.scalar(stmt) or 0)


def summary_out(db: Session, ctx: TenantContext, doc: SpecDocument) -> DocumentSummary:
    return DocumentSummary.model_validate(doc).model_copy(update={"version_count": _version_count(db, ctx, doc)})


def document_out(db: Session, ctx: TenantContext, doc: SpecDocument) -> DocumentOut:
    return DocumentOut.model_validate(doc).model_copy(update={"version_count": _version_count(db, ctx, doc)})


def list_query(ctx: TenantContext, db: Session, engagement_id: str | None) -> Select[SpecDocument]:
    stmt = _docs(db, ctx).query()
    if engagement_id:
        stmt = stmt.where(SpecDocument.engagement_id == engagement_id)
    return stmt


# --- LUDA assets -------------------------------------------------------------


def _latest(db: Session, asset_type: str) -> list[AssetItem]:
    rows = db.scalars(
        select(AssetItem)
        .where(AssetItem.asset_type == asset_type, AssetItem.status == "published")
        .order_by(AssetItem.title, AssetItem.version.desc())
    ).all()
    latest: dict[str, AssetItem] = {}
    for row in rows:
        latest.setdefault(row.asset_id, row)
    return list(latest.values())


def _asset(db: Session, asset_type: str, ref: AssetRef, field: str) -> AssetItem:
    item = db.scalars(
        select(AssetItem).where(
            AssetItem.asset_type == asset_type, AssetItem.asset_id == ref.asset_id, AssetItem.version == ref.version
        )
    ).first()
    if item is None:
        raise AppError(422, "invalid_reference", detail={"field": field})
    return item


def _template(item: AssetItem) -> TemplateOut:
    try:
        sections = [TemplateSection.model_validate(s) for s in item.payload.get("sections", [])]
        return TemplateOut(
            asset_id=item.asset_id,
            version=item.version,
            asset_key=item.asset_key,
            title=item.title,
            doc=item.payload.get("doc", "spec"),
            sections=sections,
        )
    except (ValidationError, AttributeError, TypeError) as exc:
        raise AppError(422, "invalid_spec_template") from exc


def _rule_pack(item: AssetItem) -> RulePackOut:
    rules = item.payload.get("rules", [])
    return RulePackOut(
        asset_id=item.asset_id,
        version=item.version,
        asset_key=item.asset_key,
        title=item.title,
        rules=[str(r) for r in rules] if isinstance(rules, list) else [],
    )


def list_templates(db: Session) -> list[TemplateOut]:
    return [_template(x) for x in _latest(db, TEMPLATE_TYPE)]


def list_rule_packs(db: Session) -> list[RulePackOut]:
    return [_rule_pack(x) for x in _latest(db, RULE_PACK_TYPE)]


def _resolve_template(db: Session, doc_type: str, ref: AssetRef | None) -> TemplateOut:
    if ref is not None:
        template = _template(_asset(db, TEMPLATE_TYPE, ref, "template_ref"))
        if template.doc != doc_type:
            raise AppError(422, "invalid_reference", detail={"field": "template_ref"})
        return template
    for template in list_templates(db):
        if template.doc == doc_type:
            return template
    raise AppError(422, "spec_template_missing")


def _rule_packs(db: Session, refs: list[AssetRef]) -> list[RulePackOut]:
    return [_rule_pack(_asset(db, RULE_PACK_TYPE, r, "rule_pack_refs")) for r in refs]


def _refs(doc: SpecDocument) -> tuple[AssetRef | None, list[AssetRef], SpecSources]:
    template = AssetRef.model_validate(doc.template_ref) if doc.template_ref else None
    return (
        template,
        [AssetRef.model_validate(r) for r in doc.rule_pack_refs],
        SpecSources.model_validate(doc.source_refs),
    )


def _engagement(db: Session, ctx: TenantContext, engagement_id: str) -> Engagement:
    row = TenantScopedRepository(db, ctx, Engagement).get(engagement_id)
    if row is None:
        raise AppError(422, "invalid_reference", detail={"field": "engagement_id"})
    return row


def _assemble(db: Session, ctx: TenantContext, doc: SpecDocument) -> str:
    template_ref, pack_refs, sources = _refs(doc)
    template = _resolve_template(db, doc.doc_type, template_ref)
    packs = _rule_packs(db, pack_refs)
    inputs = assemble.collect(
        db, ctx, _engagement(db, ctx, doc.engagement_id), sources, [(p.title, p.rules) for p in packs]
    )
    return assemble.render(template, doc.title, inputs)


# --- documents ---------------------------------------------------------------


@audited("specforge.document_create", "spec_document")
def create_document(ctx: TenantContext, db: Session, body: DocumentIn) -> SpecDocument:
    _engagement(db, ctx, body.engagement_id)
    template = _resolve_template(db, body.doc_type, body.template_ref)
    _rule_packs(db, body.rule_pack_refs)
    assemble.validate_sources(db, ctx, body.engagement_id, body.sources)
    doc = _docs(db, ctx).create(
        engagement_id=body.engagement_id,
        doc_type=body.doc_type,
        title=body.title,
        template_ref={"asset_id": template.asset_id, "version": template.version},
        rule_pack_refs=[r.model_dump() for r in body.rule_pack_refs],
        source_refs=body.sources.model_dump(),
    )
    doc.content_md = _assemble(db, ctx, doc)
    return doc


@audited("specforge.document_update", "spec_document")
def update_document(ctx: TenantContext, db: Session, doc: SpecDocument, body: DocumentPatch) -> SpecDocument:
    values: dict[str, Any] = {
        k: v for k, v in body.model_dump(include={"title", "status", "content_md"}).items() if v is not None
    }
    if body.template_ref is not None:
        template = _resolve_template(db, doc.doc_type, body.template_ref)
        values["template_ref"] = {"asset_id": template.asset_id, "version": template.version}
    if body.rule_pack_refs is not None:
        _rule_packs(db, body.rule_pack_refs)
        values["rule_pack_refs"] = [r.model_dump() for r in body.rule_pack_refs]
    if body.sources is not None:
        assemble.validate_sources(db, ctx, doc.engagement_id, body.sources)
        values["source_refs"] = body.sources.model_dump()
    return _docs(db, ctx).update(doc, **values)


@audited("specforge.document_assemble", "spec_document")
def reassemble(ctx: TenantContext, db: Session, doc: SpecDocument) -> SpecDocument:
    return _docs(db, ctx).update(doc, content_md=_assemble(db, ctx, doc))


@audited("specforge.document_delete", "spec_document")
def delete_document(ctx: TenantContext, db: Session, doc: SpecDocument) -> str:
    doc_id = doc.id
    _docs(db, ctx).delete(doc)
    return doc_id


# --- versions ----------------------------------------------------------------


def versions_query(db: Session, ctx: TenantContext, doc: SpecDocument) -> Select[SpecVersion]:
    return _versions(db, ctx).query().where(SpecVersion.document_id == doc.id).order_by(SpecVersion.version.desc())


def version_of(db: Session, ctx: TenantContext, doc: SpecDocument, version_id: str) -> SpecVersion:
    row = _versions(db, ctx).get(version_id)
    if row is None or row.document_id != doc.id:
        raise AppError(404, "not_found")
    return row


def _version_by_number(db: Session, ctx: TenantContext, doc: SpecDocument, number: int) -> SpecVersion:
    row = db.scalars(versions_query(db, ctx, doc).where(SpecVersion.version == number)).first()
    if row is None:
        raise AppError(404, "not_found")
    return row


@audited("specforge.version_create", "spec_version")
def create_version(ctx: TenantContext, db: Session, doc: SpecDocument, body: VersionIn) -> SpecVersion:
    last = db.scalar(
        select(func.max(SpecVersion.version)).where(
            SpecVersion.tenant_id == ctx.tenant_id, SpecVersion.document_id == doc.id
        )
    )
    return _versions(db, ctx).create(
        document_id=doc.id, version=int(last or 0) + 1, content_md=doc.content_md, note=body.note
    )


@audited("specforge.version_restore", "spec_document")
def restore_version(ctx: TenantContext, db: Session, doc: SpecDocument, version: SpecVersion) -> SpecDocument:
    return _docs(db, ctx).update(doc, content_md=version.content_md)


def diff(db: Session, ctx: TenantContext, doc: SpecDocument, from_version: int, to_version: int | None) -> DiffOut:
    """Unified diff between two saved versions; `to_version=None` compares against the working copy."""
    a = _version_by_number(db, ctx, doc, from_version)
    b_text, b_label = (
        (doc.content_md, "working")
        if to_version is None
        else (_version_by_number(db, ctx, doc, to_version).content_md, f"v{to_version}")
    )
    text = "".join(
        difflib.unified_diff(
            a.content_md.splitlines(keepends=True), b_text.splitlines(keepends=True), f"v{a.version}", b_label
        )
    )
    return DiffOut(from_label=f"v{a.version}", to_label=b_label, diff=text)


# --- enrich (LLM or prompt-copy mode) ------------------------------------------


def enrich_prompt(doc: SpecDocument, body: EnrichIn) -> str:
    extra = f"\nAdditional instructions from the FDE:\n{body.instructions.strip()}\n" if body.instructions else ""
    return ENRICH_PROMPT.format(doc=FILENAMES[doc.doc_type], extra=extra, content=doc.content_md)


def llm_available(ctx: TenantContext, db: Session) -> bool:
    try:
        get_llm(ctx, db)
    except AdapterDisabled:
        return False
    return True


def enrich(ctx: TenantContext, db: Session, doc: SpecDocument, body: EnrichIn) -> str:
    """Return an LLM-improved draft without saving it; the editor applies it as an unsaved change."""
    text = get_llm(ctx, db).generate_markdown(enrich_prompt(doc, body), feature="specforge_enrich").strip()
    if not text:
        raise AppError(502, "llm_invalid_response", detail={"reason": "empty"})
    record(
        db,
        action="specforge.document_enrich",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="spec_document",
        target_id=doc.id,
    )
    db.commit()
    return text + "\n"


# --- exports -----------------------------------------------------------------


def _export_audit(ctx: TenantContext, db: Session, target_id: str | None, detail: dict[str, Any]) -> None:
    record(
        db,
        action="specforge.export",
        actor_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        target_type="spec_document",
        target_id=target_id,
        detail=detail,
    )
    db.commit()


def export_markdown(ctx: TenantContext, db: Session, doc: SpecDocument) -> tuple[str, str]:
    _export_audit(ctx, db, doc.id, {"format": "md"})
    return doc.content_md, FILENAMES[doc.doc_type]


def export_zip(ctx: TenantContext, db: Session, engagement_id: str | None) -> bytes:
    docs = _docs(db, ctx).all(list_query(ctx, db, engagement_id).order_by(SpecDocument.doc_type, SpecDocument.title))
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            name, n = FILENAMES[doc.doc_type], 1
            while name in used:
                n += 1
                name = f"{FILENAMES[doc.doc_type][:-3]}-{n}.md"
            used.add(name)
            zf.writestr(name, doc.content_md)
    _export_audit(ctx, db, None, {"format": "zip", "engagement_id": engagement_id, "documents": len(docs)})
    return buf.getvalue()
