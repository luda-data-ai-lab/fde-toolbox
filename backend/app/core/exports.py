import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from fastapi import Response

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> Any:
    """Neutralise values that spreadsheet apps would evaluate as formulas."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def csv_text(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """UTF-8 CSV with BOM so Excel opens Korean text correctly."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_safe(v) for v in row])
    return "\ufeff" + buf.getvalue()


def attachment(data: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content=data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
