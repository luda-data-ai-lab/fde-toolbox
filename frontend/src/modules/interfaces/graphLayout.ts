import type { GraphEdge, GraphNode } from "../../api/types";

export interface Point {
  x: number;
  y: number;
}
export interface LinkGroup {
  key: string;
  source: string;
  target: string;
  edges: GraphEdge[];
}

/** Places nodes on a circle (busiest first) so dense hubs stay readable; isolated nodes go last. */
export function circleLayout(
  nodes: GraphNode[],
  width: number,
  height: number,
  margin = 70,
): Map<string, Point> {
  const ordered = [...nodes].sort(
    (a, b) => b.degree - a.degree || a.name.localeCompare(b.name),
  );
  const r = Math.max(0, Math.min(width, height) / 2 - margin);
  const pos = new Map<string, Point>();
  ordered.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, ordered.length) - Math.PI / 2;
    pos.set(n.id, {
      x: width / 2 + r * Math.cos(angle),
      y: height / 2 + r * Math.sin(angle),
    });
  });
  return pos;
}

/** One drawable link per directed system pair, keeping the interfaces it stands for. */
export function groupEdges(edges: GraphEdge[]): LinkGroup[] {
  const groups = new Map<string, LinkGroup>();
  for (const e of edges) {
    const key = `${e.source}->${e.target}`;
    const g = groups.get(key) ?? {
      key,
      source: e.source,
      target: e.target,
      edges: [],
    };
    g.edges.push(e);
    groups.set(key, g);
  }
  return [...groups.values()];
}

/** Quadratic curve between two points; bends to one side so A→B and B→A don't overlap. */
export function linkPath(a: Point, b: Point, nodeRadius = 22): string {
  if (a.x === b.x && a.y === b.y) {
    const r = nodeRadius;
    return `M ${a.x - r / 2} ${a.y - r} C ${a.x - 2 * r} ${a.y - 3 * r}, ${a.x + 2 * r} ${a.y - 3 * r}, ${a.x + r / 2} ${a.y - r}`;
  }
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy);
  const ux = dx / len;
  const uy = dy / len;
  const start = { x: a.x + ux * nodeRadius, y: a.y + uy * nodeRadius };
  const end = {
    x: b.x - ux * (nodeRadius + 4),
    y: b.y - uy * (nodeRadius + 4),
  };
  const bend = Math.min(40, len / 6);
  const cx = (start.x + end.x) / 2 - uy * bend;
  const cy = (start.y + end.y) / 2 + ux * bend;
  return `M ${start.x} ${start.y} Q ${cx} ${cy} ${end.x} ${end.y}`;
}
