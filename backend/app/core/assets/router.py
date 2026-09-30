from typing import Annotated

from fastapi import APIRouter, Query

from app.core.assets import service
from app.core.assets.schemas import (
    AssetDiff,
    AssetIn,
    AssetOut,
    AssetPackage,
    AssetSummary,
    AssetVersionIn,
    AssetVersionPatch,
    ImportResult,
)
from app.core.audit.service import record
from app.core.auth.deps import DB, AdminPrincipal, CurrentPrincipal

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetSummary])
def list_assets(principal: CurrentPrincipal, db: DB, asset_type: str | None = None) -> list[AssetSummary]:
    return [AssetSummary(**s) for s in service.summaries(db, asset_type)]


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(body: AssetIn, principal: AdminPrincipal, db: DB) -> AssetOut:
    return AssetOut.model_validate(service.create_asset(principal, db, body))


@router.get("/export", response_model=AssetPackage)
def export_assets(
    principal: AdminPrincipal, db: DB, asset_ids: Annotated[list[str] | None, Query()] = None
) -> AssetPackage:
    package = service.export_package(db, asset_ids or [])
    record(
        db,
        action="asset.export",
        actor_id=principal.user_id,
        target_type="asset_package",
        detail={"assets": len(package.assets)},
        ip=principal.ip,
    )
    db.commit()
    return package


@router.post("/import", response_model=ImportResult)
def import_assets(package: AssetPackage, principal: AdminPrincipal, db: DB) -> ImportResult:
    return service.import_package(principal, db, package)


@router.get("/{asset_id}", response_model=list[AssetOut])
def list_versions(asset_id: str, principal: CurrentPrincipal, db: DB) -> list[AssetOut]:
    rows = service.versions(db, asset_id)
    if not rows:
        service.latest(db, asset_id)
    return [AssetOut.model_validate(r) for r in rows]


@router.post("/{asset_id}/versions", response_model=AssetOut, status_code=201)
def create_version(asset_id: str, body: AssetVersionIn, principal: AdminPrincipal, db: DB) -> AssetOut:
    return AssetOut.model_validate(service.create_version(principal, db, asset_id, body))


@router.get("/{asset_id}/versions/{version}", response_model=AssetOut)
def get_version(asset_id: str, version: int, principal: CurrentPrincipal, db: DB) -> AssetOut:
    return AssetOut.model_validate(service.get_version(db, asset_id, version))


@router.patch("/{asset_id}/versions/{version}", response_model=AssetOut)
def update_version(asset_id: str, version: int, body: AssetVersionPatch, principal: AdminPrincipal, db: DB) -> AssetOut:
    item = service.get_version(db, asset_id, version)
    return AssetOut.model_validate(service.update_version(principal, db, item, body))


@router.get("/{asset_id}/diff", response_model=AssetDiff)
def diff_versions(asset_id: str, principal: CurrentPrincipal, db: DB, from_version: int, to_version: int) -> AssetDiff:
    payload_diff, prompt_diff = service.diff(db, asset_id, from_version, to_version)
    return AssetDiff(
        asset_id=asset_id,
        from_version=from_version,
        to_version=to_version,
        payload_diff=payload_diff,
        prompt_diff=prompt_diff,
    )
