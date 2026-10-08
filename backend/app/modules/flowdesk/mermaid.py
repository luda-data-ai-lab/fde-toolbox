"""Mermaid `flowchart` text for a flow graph (lanes become subgraphs)."""

from app.modules.flowdesk.schemas import FlowGraph, GraphNode

_SHAPES = {
    "start": ('(["', '"])'),
    "end": ('(["', '"])'),
    "task": ('["', '"]'),
    "decision": ('{"', '"}'),
    "system": ('[("', '")]'),
    "document": ('[/"', '"/]'),
    "role": ('(("', '"))'),
    "note": ('>"', '"]'),
}


def _text(value: str) -> str:
    return value.replace('"', "#quot;").replace("\r", "").replace("\n", "<br/>")


def _node(key: str, node: GraphNode, label: str) -> str:
    left, right = _SHAPES.get(node.type, _SHAPES["task"])
    return f"{key}{left}{_text(label)}{right}"


def to_mermaid(graph: FlowGraph, system_names: dict[str, str] | None = None) -> str:
    names = system_names or {}
    keys = {n.id: f"n{i}" for i, n in enumerate(graph.nodes)}

    def label(n: GraphNode) -> str:
        return n.label or (names.get(n.system_id, "") if n.system_id else "") or n.type

    lines = ["flowchart LR"]
    for li, lane in enumerate(graph.lanes):
        members = [n for n in graph.nodes if n.lane == lane]
        if not members:
            continue
        lines.append(f'  subgraph lane{li}["{_text(lane)}"]')
        lines.extend(f"    {_node(keys[n.id], n, label(n))}" for n in members)
        lines.append("  end")
    lines.extend(f"  {_node(keys[n.id], n, label(n))}" for n in graph.nodes if n.lane is None)
    for e in graph.edges:
        arrow = f'-->|"{_text(e.label)}"|' if e.label else "-->"
        lines.append(f"  {keys[e.source]} {arrow} {keys[e.target]}")
    for n in graph.nodes:
        if n.type == "note":
            lines.append(f"  style {keys[n.id]} fill:#fef9c3,stroke:#ca8a04")
    return "\n".join(lines) + "\n"
