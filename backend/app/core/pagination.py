import base64
import json
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import Session

from app.core.errors import bad_request
from app.db.base import Base

T = TypeVar("T")
M = TypeVar("M", bound=Base)

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


def _encode(created_at: datetime, row_id: str) -> str:
    raw = json.dumps([created_at.isoformat(), row_id]).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> tuple[datetime, str]:
    try:
        created, row_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(created), str(row_id)
    except (ValueError, TypeError) as exc:
        raise bad_request("invalid_cursor") from exc


def paginate(
    db: Session, stmt: Select[M], model: type[M], limit: int, cursor: str | None
) -> tuple[list[M], str | None]:
    """Keyset pagination, default order: newest first (created_at desc, id desc)."""
    limit = max(1, min(limit, MAX_LIMIT))
    if cursor:
        created, row_id = _decode(cursor)
        stmt = stmt.where(or_(model.created_at < created, and_(model.created_at == created, model.id < row_id)))
    stmt = stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode(last.created_at, last.id)
    return rows, next_cursor


def page_of(items: list[Any], next_cursor: str | None) -> dict[str, Any]:
    return {"items": items, "next_cursor": next_cursor}
