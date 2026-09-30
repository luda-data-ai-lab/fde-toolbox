from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.auth.deps import DB
from app.core.pagination import Page
from app.core.systems import service
from app.core.systems.models import System
from app.core.systems.schemas import SystemIn, SystemOut, SystemPatch
from app.core.tenancy.deps import Ctx, WriteCtx, path_entity, repo

router = APIRouter(prefix="/t/{tenant_id}/systems", tags=["systems"])

SystemDep = Annotated[System, Depends(path_entity(System, "system_id"))]


@router.get("", response_model=Page[SystemOut])
def list_systems(ctx: Ctx, db: DB, limit: int = 50, cursor: str | None = None) -> Page[SystemOut]:
    rows, nxt = repo(db, ctx, System).page(limit=limit, cursor=cursor)
    return Page(items=[SystemOut.model_validate(r) for r in rows], next_cursor=nxt)


@router.post("", response_model=SystemOut, status_code=201)
def create_system(body: SystemIn, ctx: WriteCtx, db: DB) -> SystemOut:
    return SystemOut.model_validate(service.create_system(ctx, db, body))


@router.get("/{system_id}", response_model=SystemOut)
def get_system(obj: SystemDep) -> SystemOut:
    return SystemOut.model_validate(obj)


@router.patch("/{system_id}", response_model=SystemOut)
def update_system(obj: SystemDep, body: SystemPatch, ctx: WriteCtx, db: DB) -> SystemOut:
    return SystemOut.model_validate(service.update_system(ctx, db, obj, body))


@router.delete("/{system_id}", status_code=204)
def delete_system(obj: SystemDep, ctx: WriteCtx, db: DB) -> Response:
    service.delete_system(ctx, db, obj)
    return Response(status_code=204)
