import difflib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.assets.models import AssetItem
from app.core.assets.schemas import (
    PACKAGE_SCHEMA_VERSION,
    AssetIn,
    AssetPackage,
    AssetVersionIn,
    AssetVersionPatch,
    ImportResult,
    PackageRow,
)
from app.core.audit.service import audited
from app.core.errors import AppError, bad_request, not_found
from app.core.serialization import row_from_json, row_to_json, table_of
from app.core.tenancy.context import Principal
from app.db.base import AssetModel, Base, new_id


def versions(db: Session, asset_id: str) -> list[AssetItem]:
    return list(db.scalars(select(AssetItem).where(AssetItem.asset_id == asset_id).order_by(AssetItem.version)))


def get_version(db: Session, asset_id: str, version: int) -> AssetItem:
    row = db.scalars(select(AssetItem).where(AssetItem.asset_id == asset_id, AssetItem.version == version)).first()
    if row is None:
        raise not_found()
    return row


def latest(db: Session, asset_id: str) -> AssetItem:
    rows = versions(db, asset_id)
    if not rows:
        raise not_found()
    return rows[-1]


def ref_exists(db: Session, asset_id: str, version: int, asset_type: str | None = None) -> bool:
    stmt = select(AssetItem.id).where(AssetItem.asset_id == asset_id, AssetItem.version == version)
    if asset_type:
        stmt = stmt.where(AssetItem.asset_type == asset_type)
    return db.scalars(stmt).first() is not None


@audited("asset.create", "asset")
def create_asset(ctx: Principal, db: Session, body: AssetIn) -> AssetItem:
    item = AssetItem(asset_id=new_id(), version=1, created_by=ctx.user_id, **body.model_dump())
    db.add(item)
    db.flush()
    return item


@audited("asset.version_create", "asset")
def create_version(ctx: Principal, db: Session, asset_id: str, body: AssetVersionIn) -> AssetItem:
    prev = latest(db, asset_id)
    item = AssetItem(
        asset_id=asset_id,
        version=prev.version + 1,
        asset_type=prev.asset_type,
        asset_key=prev.asset_key,
        title=body.title or prev.title,
        payload=body.payload,
        status=body.status,
        change_note=body.change_note,
        created_by=ctx.user_id,
    )
    db.add(item)
    db.flush()
    return item


@audited("asset.version_update", "asset")
def update_version(ctx: Principal, db: Session, item: AssetItem, body: AssetVersionPatch) -> AssetItem:
    data = body.model_dump(exclude_unset=True)
    if data.get("payload") is not None:
        if item.status != "draft":
            raise bad_request("asset_version_frozen")
        item.payload = data["payload"]
    if data.get("title") is not None:
        item.title = data["title"]
    if data.get("status") is not None:
        item.status = data["status"]
    if "change_note" in data:
        item.change_note = data["change_note"]
    db.flush()
    return item


def _pretty(payload: dict[str, Any]) -> list[str]:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)


def diff(db: Session, asset_id: str, from_version: int, to_version: int) -> tuple[str, str | None]:
    a = get_version(db, asset_id, from_version)
    b = get_version(db, asset_id, to_version)
    payload_diff = "".join(
        difflib.unified_diff(_pretty(a.payload), _pretty(b.payload), f"v{a.version}", f"v{b.version}")
    )
    prompt_diff = None
    pa, pb = a.payload.get("system_prompt"), b.payload.get("system_prompt")
    if isinstance(pa, str) or isinstance(pb, str):
        prompt_diff = "".join(
            difflib.unified_diff(
                str(pa or "").splitlines(keepends=True),
                str(pb or "").splitlines(keepends=True),
                f"v{a.version}",
                f"v{b.version}",
            )
        )
    return payload_diff, prompt_diff


def summaries(db: Session, asset_type: str | None) -> list[dict[str, Any]]:
    counts = select(AssetItem.asset_id, func.max(AssetItem.version).label("maxv"), func.count().label("n")).group_by(
        AssetItem.asset_id
    )
    if asset_type:
        counts = counts.where(AssetItem.asset_type == asset_type)
    sub = counts.subquery()
    rows = db.execute(
        select(AssetItem, sub.c.n)
        .join(sub, (AssetItem.asset_id == sub.c.asset_id) & (AssetItem.version == sub.c.maxv))
        .order_by(AssetItem.asset_type, AssetItem.title)
    ).all()
    return [
        {
            "asset_id": item.asset_id,
            "asset_type": item.asset_type,
            "asset_key": item.asset_key,
            "title": item.title,
            "latest_version": item.version,
            "latest_status": item.status,
            "versions": n,
        }
        for item, n in rows
    ]


def related_asset_models() -> list[type[AssetModel]]:
    """Other asset tables (e.g. evaluation cases) keyed by (asset_id, version)."""
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, AssetModel) and m.class_ is not AssetItem]


def export_package(db: Session, asset_ids: list[str]) -> AssetPackage:
    asset_table = table_of(AssetItem)
    stmt = select(asset_table).order_by(asset_table.c.asset_id, asset_table.c.version)
    if asset_ids:
        stmt = stmt.where(asset_table.c.asset_id.in_(asset_ids))
    items = [dict(r) for r in db.execute(stmt).mappings()]
    ids = {i["asset_id"] for i in items}
    related: list[PackageRow] = []
    for model in related_asset_models():
        table = table_of(model)
        rows = db.execute(select(table).where(table.c.asset_id.in_(ids))).mappings().all() if ids else []
        related.extend(PackageRow(table=table.name, row=row_to_json(table, dict(r))) for r in rows)
    return AssetPackage(assets=[row_to_json(asset_table, i) for i in items], related=related)


@audited("asset.import", "asset_package")
def import_package(ctx: Principal, db: Session, package: AssetPackage) -> ImportResult:
    if package.schema_version != PACKAGE_SCHEMA_VERSION:
        raise bad_request("unsupported_schema_version")
    created = skipped = 0
    for raw in package.assets:
        values = row_from_json(table_of(AssetItem), raw)
        if not values.get("asset_id") or not values.get("version"):
            raise AppError(422, "invalid_package")
        if ref_exists(db, values["asset_id"], values["version"]):
            skipped += 1
            continue
        values["id"] = new_id()
        values["created_by"] = ctx.user_id
        db.add(AssetItem(**values))
        created += 1
    tables = {table_of(m).name: m for m in related_asset_models()}
    for rel in package.related:
        model = tables.get(rel.table)
        if model is None:
            raise AppError(422, "invalid_package")
        values = row_from_json(table_of(model), rel.row)
        if db.get(model, values.get("id")) is not None:
            skipped += 1
            continue
        db.add(model(**values))
        created += 1
    db.flush()
    return ImportResult(created=created, skipped=skipped)
