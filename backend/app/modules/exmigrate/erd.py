"""ERD draft from a workbook report, validation and Mermaid export (pure functions)."""

import re

from app.modules.exmigrate.analyzer import looks_like_identifier
from app.modules.exmigrate.schemas import Erd, ErdColumn, ErdRelation, ErdTable, WorkbookReport

_NON_WORD = re.compile(r"[^\w]+")
_IDENTIFIER = re.compile(r"^[^\W\d]\w{0,62}$")
_ASCII = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def to_identifier(label: str, fallback: str) -> str:
    name = _NON_WORD.sub("_", label.strip().lower()).strip("_")
    if not name:
        return fallback
    if name[0].isdigit():
        name = f"c_{name}"
    return name[:63]


def _unique(name: str, used: set[str]) -> str:
    base, n = name, 2
    while name.lower() in used:
        suffix = f"_{n}"
        name, n = base[: 63 - len(suffix)] + suffix, n + 1
    used.add(name.lower())
    return name


def draft_erd(report: WorkbookReport) -> Erd:
    tables: list[ErdTable] = []
    by_sheet: dict[str, ErdTable] = {}
    letters: dict[str, dict[str, str]] = {}
    used_tables: set[str] = set()
    for i, sheet in enumerate(report.sheets, start=1):
        if not sheet.columns:
            continue
        used_cols: set[str] = set()
        cols: list[ErdColumn] = []
        pk_done = False
        for col in sheet.columns:
            name = _unique(to_identifier(col.name, f"col_{col.letter.lower()}"), used_cols)
            pk = (
                not pk_done
                and looks_like_identifier(col.name)
                and col.null_ratio == 0
                and sheet.data_rows > 0
                and col.distinct == sheet.data_rows
            )
            pk_done = pk_done or pk
            cols.append(
                ErdColumn(
                    name=name,
                    label=col.name,
                    type=col.inferred_type or "text",
                    nullable=not pk and col.null_ratio > 0,
                    primary_key=pk,
                    source_column=col.letter,
                )
            )
        table = ErdTable(
            name=_unique(to_identifier(sheet.name, f"table_{i}"), used_tables),
            label=sheet.name,
            source_sheet=sheet.name,
            header_row=sheet.header_row,
            columns=cols,
        )
        tables.append(table)
        by_sheet[sheet.name] = table
        letters[sheet.name] = {c.source_column or "": c.name for c in cols}

    relations: list[ErdRelation] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(rel: ErdRelation) -> None:
        key = (rel.from_table, rel.from_column, rel.to_table, rel.to_column)
        if key not in seen and rel.from_table != rel.to_table:
            seen.add(key)
            relations.append(rel)

    for sheet in report.sheets:
        src = by_sheet.get(sheet.name)
        if src is None:
            continue
        for lk in sheet.formulas.lookups:
            dst = by_sheet.get(lk.target_sheet)
            from_col = letters[sheet.name].get(lk.column)
            to_col = letters.get(lk.target_sheet, {}).get(lk.target_column)
            if dst is not None and from_col and to_col:
                add(
                    ErdRelation(
                        from_table=src.name, from_column=from_col, to_table=dst.name, to_column=to_col, origin="formula"
                    )
                )
    for dst in tables:
        for key in (c for c in dst.columns if c.primary_key):
            for src in tables:
                if src is not dst and any(c.name == key.name and not c.primary_key for c in src.columns):
                    add(
                        ErdRelation(
                            from_table=src.name,
                            from_column=key.name,
                            to_table=dst.name,
                            to_column=key.name,
                            origin="name",
                        )
                    )
    return Erd(tables=tables, relations=relations)


def erd_issues(erd: Erd) -> list[str]:
    """Problems that block confirming the ERD (and generating scripts from it)."""
    issues: list[str] = []
    if not erd.tables:
        issues.append("no_tables")
    columns: dict[str, set[str]] = {}
    for t in erd.tables:
        if not _IDENTIFIER.match(t.name):
            issues.append(f"invalid_name:{t.name}")
        if t.name.lower() in columns:
            issues.append(f"duplicate_table:{t.name}")
        names: set[str] = set()
        for c in t.columns:
            if not _IDENTIFIER.match(c.name):
                issues.append(f"invalid_name:{t.name}.{c.name}")
            if c.name.lower() in names:
                issues.append(f"duplicate_column:{t.name}.{c.name}")
            names.add(c.name.lower())
        columns[t.name.lower()] = names
    for r in erd.relations:
        if r.from_column.lower() not in columns.get(r.from_table.lower(), set()):
            issues.append(f"unknown_relation_source:{r.from_table}.{r.from_column}")
        if r.to_column.lower() not in columns.get(r.to_table.lower(), set()):
            issues.append(f"unknown_relation_target:{r.to_table}.{r.to_column}")
    return issues


def _quote(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


def to_mermaid(erd: Erd) -> str:
    ids = {t.name: (t.name if _ASCII.match(t.name) else f"t{i}") for i, t in enumerate(erd.tables, start=1)}
    lines = ["erDiagram"]
    for t in erd.tables:
        head = ids[t.name] if ids[t.name] == t.name else f'{ids[t.name]}["{_quote(t.name)}"]'
        lines.append(f"    {head} {{")
        for i, c in enumerate(t.columns, start=1):
            name = c.name if _ASCII.match(c.name) else f"col{i}"
            key = " PK" if c.primary_key else ""
            comment = c.label or c.name
            lines.append(f'        {c.type} {name}{key} "{_quote(comment)}"')
        lines.append("    }")
    for r in erd.relations:
        if r.to_table in ids and r.from_table in ids:
            lines.append(f'    {ids[r.to_table]} ||--o{{ {ids[r.from_table]} : "{_quote(r.from_column)}"')
    return "\n".join(lines) + "\n"
