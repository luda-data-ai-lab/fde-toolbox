from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.core.auth.deps import DB, AdminPrincipal
from app.core.tenancy.deps import ExportCtx
from app.core.tenants.schemas import TenantOut
from app.core.transfer import service

router = APIRouter(prefix="/t/{tenant_id}/export", tags=["transfer"])
admin_router = APIRouter(prefix="/admin/tenants", tags=["admin"])


@router.get("")
def export_tenant(ctx: ExportCtx, db: DB) -> Response:
    data = service.export_tenant(ctx, db)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="tenant-{ctx.tenant_id}.zip"'},
    )


@admin_router.post("/import", response_model=TenantOut, status_code=201)
def import_tenant(
    principal: AdminPrincipal,
    db: DB,
    file: Annotated[UploadFile, File()],
    code: Annotated[str, Form(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")],
    name: Annotated[str | None, Form()] = None,
) -> TenantOut:
    return TenantOut.model_validate(service.import_tenant(principal, db, file.file.read(), code, name))
