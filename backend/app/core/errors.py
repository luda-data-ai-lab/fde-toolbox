from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str | None = None, detail: Any = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message or f"errors.{code}"
        self.detail = detail


def not_found() -> AppError:
    return AppError(404, "not_found")


def forbidden() -> AppError:
    return AppError(403, "forbidden")


def bad_request(code: str, detail: Any = None) -> AppError:
    return AppError(400, code, detail=detail)


def _body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        err["detail"] = detail
    return {"error": err}


_STATUS_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_req: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, exc.detail))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_body(code, f"errors.{code}"))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, exc: RequestValidationError) -> JSONResponse:
        detail = [{"loc": list(e.get("loc", [])), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=_body("validation_error", "errors.validation_error", detail))
