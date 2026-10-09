"""Rule-based candidate extractors: pure functions over another module's data, no DB writes and no LLM.

Their output always lands in `onto_candidates`; the FDE decides what becomes a term, concept, attribute or relation.
"""

import re
from dataclasses import dataclass, field
from typing import Any

MAX_NAME = 200
_TYPES = {"integer": "integer", "decimal": "decimal", "boolean": "boolean", "date": "date", "datetime": "datetime"}
_IF_SUFFIX = re.compile(
    r"\s*(?:정보|데이터)?\s*(?:송신|수신|전송|연동|동기화|인터페이스|조회|등록|I/?F|interface|sync|transfer)\s*$",
    re.IGNORECASE,
)


Payload = dict[str, str | int | float | bool | list[str] | None]


@dataclass(frozen=True)
class Extracted:
    kind: str
    name: str
    payload: Payload = field(default_factory=dict)


def _label(item: dict[str, Any]) -> str:
    return " ".join(str(item.get("label") or item.get("name") or "").split())


def attribute_name(concept: str, attribute: str) -> str:
    """Attribute candidates are named `개념.속성` so equal column labels in different tables stay distinct."""
    return f"{concept}.{attribute}"[:MAX_NAME]


def relation_name(source: str, target: str) -> str:
    return f"{source} → {target}"[:MAX_NAME]


def from_erd(erd: dict[str, Any]) -> list[Extracted]:
    """Confirmed ERD: tables → concepts, columns → attributes, FK-like relations → relations."""
    tables: list[dict[str, Any]] = [t for t in erd.get("tables", []) if _label(t)]
    label = {str(t["name"]): _label(t) for t in tables}
    columns = {(str(t["name"]), str(c["name"])): _label(c) for t in tables for c in t.get("columns", [])}
    out: list[Extracted] = []
    for t in tables:
        concept = label[str(t["name"])]
        cols = [c for c in t.get("columns", []) if _label(c)]
        out.append(
            Extracted(
                "concept",
                concept[:MAX_NAME],
                {"table": t["name"], "attributes": [_label(c) for c in cols]},
            )
        )
        for c in cols:
            out.append(
                Extracted(
                    "attribute",
                    attribute_name(concept, _label(c)),
                    {
                        "concept": concept,
                        "attribute": _label(c),
                        "table": t["name"],
                        "column": c["name"],
                        "data_type": _TYPES.get(str(c.get("type")), "string"),
                        "required": not c.get("nullable", True),
                    },
                )
            )
    for r in erd.get("relations", []):
        src, dst = label.get(str(r.get("from_table"))), label.get(str(r.get("to_table")))
        if not src or not dst or src == dst:
            continue
        col = columns.get((str(r["from_table"]), str(r.get("from_column"))), str(r.get("from_column") or ""))
        out.append(
            Extracted(
                "relation",
                relation_name(src, dst),
                {
                    "source": src,
                    "target": dst,
                    "relation": col or dst,
                    "table": r["from_table"],
                    "column": r.get("from_column"),
                    "cardinality": "1:N",
                },
            )
        )
    return _dedupe(out)


def interface_subject(name: str) -> str:
    """`수주 정보 전송` → `수주`: the data an I/F carries, without the transport verb."""
    cleaned = " ".join(name.split())
    stripped = _IF_SUFFIX.sub("", cleaned).strip()
    return stripped or cleaned


def from_interface(name: str, if_code: str, description: str | None) -> list[Extracted]:
    subject = interface_subject(name)
    if not subject:
        return []
    payload: Payload = {"if_code": if_code, "interface": name}
    if description and description.strip():
        payload["context"] = description.strip()[:2000]
    return [Extracted("concept", subject[:MAX_NAME], payload)]


def from_flow(title: str, graph: dict[str, Any]) -> list[Extracted]:
    """FlowDesk document nodes (forms, reports, spreadsheets) are the business objects of the flow."""
    out: list[Extracted] = []
    for node in graph.get("nodes", []):
        name = _label(node)
        if node.get("type") != "document" or not name:
            continue
        payload: Payload = {"node_id": node.get("id"), "flow": title}
        if node.get("lane"):
            payload["department"] = node["lane"]
        out.append(Extracted("concept", name[:MAX_NAME], payload))
    return _dedupe(out)


def _dedupe(items: list[Extracted]) -> list[Extracted]:
    seen: set[tuple[str, str]] = set()
    out: list[Extracted] = []
    for item in items:
        key = (item.kind, item.name)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
