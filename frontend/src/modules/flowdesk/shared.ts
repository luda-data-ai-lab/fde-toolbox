import { tenantPath } from "../../api/client";
import type { FlowGraph, FlowNodeType } from "../../api/types";

export const FLOW_KINDS = ["as_is", "to_be"] as const;
export const PERSPECTIVES = ["business", "pm", "developer", "executive", "consultant"] as const;
export const NODE_TYPES: FlowNodeType[] = ["start", "end", "task", "decision", "system", "document", "role", "note"];
export const LANE_HEIGHT = 140;
export const LANE_LABEL_WIDTH = 120;
export const NODE_WIDTH = 160;
export const NODE_HEIGHT = 56;

export function flowPath(tenantId: string | null, path: string): string {
  return tenantPath(tenantId, `/flowdesk${path}`);
}

export function flowKeys(tenantId: string | null) {
  return {
    all: ["flowdesk", tenantId] as const,
    list: (filters: object) => ["flowdesk", tenantId, "flows", filters] as const,
    flow: (id: string) => ["flowdesk", tenantId, "flow", id] as const,
    pair: (id: string) => ["flowdesk", tenantId, "pair", id] as const,
    snapshots: (id: string) => ["flowdesk", tenantId, "snapshots", id] as const,
    templates: ["flowdesk", tenantId, "templates"] as const,
  };
}

export function emptyGraph(): FlowGraph {
  return { schema_version: 1, lanes: [], nodes: [], edges: [] };
}

/** Lane whose band contains the given y (node top); null when lanes are unused or outside all bands. */
export function laneAt(lanes: string[], y: number): string | null {
  if (lanes.length === 0) return null;
  const idx = Math.floor((y + NODE_HEIGHT / 2) / LANE_HEIGHT);
  return idx >= 0 && idx < lanes.length ? (lanes[idx] ?? null) : null;
}

export function nextId(prefix: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  let i = used.size + 1;
  while (used.has(`${prefix}${i}`)) i += 1;
  return `${prefix}${i}`;
}

const FILL: Record<FlowNodeType, string> = {
  start: "#dcfce7",
  end: "#fee2e2",
  task: "#eff6ff",
  decision: "#fef3c7",
  system: "#ede9fe",
  document: "#f1f5f9",
  role: "#e0f2fe",
  note: "#fef9c3",
};
export const nodeFill = (type: FlowNodeType) => FILL[type] ?? FILL.task;

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Standalone SVG of a flow graph (lanes, nodes, edges), independent of the canvas DOM. */
export function graphToSvg(
  graph: FlowGraph,
  systemNames: Map<string, string> = new Map(),
): { svg: string; width: number; height: number } {
  const offsetX = graph.lanes.length ? LANE_LABEL_WIDTH : 0;
  const xs = graph.nodes.map((n) => n.position.x);
  const ys = graph.nodes.map((n) => n.position.y);
  const minX = Math.min(0, ...xs);
  const minY = Math.min(0, ...ys);
  const width = Math.max(400, ...xs.map((x) => x + NODE_WIDTH + 40)) - minX + offsetX;
  const height = Math.max(graph.lanes.length * LANE_HEIGHT, ...ys.map((y) => y + NODE_HEIGHT + 40), 200) - minY;
  const tx = (x: number) => x - minX + offsetX;
  const ty = (y: number) => y - minY;
  const pos = new Map(graph.nodes.map((n) => [n.id, n.position]));
  const parts: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="Pretendard, sans-serif" font-size="13">`,
    `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#475569"/></marker></defs>`,
    `<rect width="${width}" height="${height}" fill="#ffffff"/>`,
  ];
  graph.lanes.forEach((lane, i) => {
    const y = ty(i * LANE_HEIGHT);
    parts.push(
      `<rect x="0" y="${y}" width="${width}" height="${LANE_HEIGHT}" fill="${i % 2 ? "#f8fafc" : "#ffffff"}" stroke="#cbd5e1"/>`,
      `<text x="12" y="${y + LANE_HEIGHT / 2}" dominant-baseline="middle" font-weight="600" fill="#334155">${esc(lane)}</text>`,
    );
  });
  for (const e of graph.edges) {
    const a = pos.get(e.source);
    const b = pos.get(e.target);
    if (!a || !b) continue;
    const x1 = tx(a.x) + NODE_WIDTH;
    const y1 = ty(a.y) + NODE_HEIGHT / 2;
    const x2 = tx(b.x);
    const y2 = ty(b.y) + NODE_HEIGHT / 2;
    const mx = (x1 + x2) / 2;
    parts.push(
      `<path d="M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}" fill="none" stroke="#475569" stroke-width="1.5" marker-end="url(#arrow)"/>`,
    );
    if (e.label)
      parts.push(
        `<text x="${mx}" y="${(y1 + y2) / 2 - 6}" text-anchor="middle" fill="#334155" font-size="12">${esc(e.label)}</text>`,
      );
  }
  for (const n of graph.nodes) {
    const x = tx(n.position.x);
    const y = ty(n.position.y);
    const label = n.label || (n.system_id ? (systemNames.get(n.system_id) ?? "") : "");
    const rx = n.type === "start" || n.type === "end" ? NODE_HEIGHT / 2 : n.type === "decision" ? 2 : 8;
    parts.push(
      `<rect x="${x}" y="${y}" width="${NODE_WIDTH}" height="${NODE_HEIGHT}" rx="${rx}" fill="${nodeFill(n.type)}" stroke="#334155" stroke-width="${n.type === "decision" ? 2 : 1}"${n.type === "note" ? ' stroke-dasharray="4 3"' : ""}/>`,
      `<text x="${x + NODE_WIDTH / 2}" y="${y + NODE_HEIGHT / 2}" text-anchor="middle" dominant-baseline="middle" fill="#0f172a">${esc(label)}</text>`,
    );
  }
  parts.push("</svg>");
  return { svg: parts.join(""), width, height };
}

export function download(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function downloadSvg(svg: string, filename: string) {
  download(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), filename);
}

export function downloadPng(svg: string, width: number, height: number, filename: string) {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width * 2;
    canvas.height = height * 2;
    const g = canvas.getContext("2d");
    if (!g) return;
    g.drawImage(img, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => blob && download(blob, filename));
  };
  img.src = url;
}
