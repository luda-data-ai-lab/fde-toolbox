from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.assets.router import router as assets_router
from app.core.audit.router import admin_router as audit_admin_router
from app.core.audit.router import router as audit_router
from app.core.auth.router import router as auth_router
from app.core.errors import install_error_handlers
from app.core.files.router import router as files_router
from app.core.systems.router import router as systems_router
from app.core.tenants.router import admin_router as tenants_admin_router
from app.core.tenants.router import router as engagements_router
from app.core.transfer.router import admin_router as transfer_admin_router
from app.core.transfer.router import router as transfer_router
from app.core.users.router import router as users_router
from app.home.router import router as home_router
from app.modules.agenthub.router import asset_router as agenthub_asset_router
from app.modules.agenthub.router import router as agenthub_router
from app.modules.coachq.router import router as coachq_router
from app.modules.devtracker.router import router as devtracker_router
from app.modules.interfaces.router import router as interfaces_router

API_PREFIX = "/api/v1"


def api_router() -> APIRouter:
    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for r in (
        auth_router,
        users_router,
        transfer_admin_router,
        tenants_admin_router,
        engagements_router,
        systems_router,
        files_router,
        audit_router,
        audit_admin_router,
        transfer_router,
        assets_router,
        agenthub_asset_router,
        home_router,
        devtracker_router,
        agenthub_router,
        interfaces_router,
        coachq_router,
    ):
        api.include_router(r)
    return api


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="static-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FDE Toolbox", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None
    )
    install_error_handlers(app)
    app.include_router(api_router())
    if settings.static_dir and (settings.static_dir / "index.html").exists():
        _mount_spa(app, settings.static_dir)
    return app


app = create_app()
