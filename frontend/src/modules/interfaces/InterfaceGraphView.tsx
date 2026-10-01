import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../../api/client";
import type { InterfaceGraph } from "../../api/types";
import {
  Empty,
  Field,
  Loading,
  Select,
  StatusBadge,
} from "../../components/ui";
import { circleLayout, groupEdges, linkPath } from "./graphLayout";
import { IF_STATUSES, LINK_TYPES, ifKeys } from "./shared";

const W = 900;
const H = 600;
const R = 22;
const LINK_COLORS: Record<string, string> = {
  db_link: "#7c3aed",
  api: "#1d4ed8",
  file: "#059669",
  mq: "#d97706",
  eai: "#db2777",
  other: "#64748b",
};

function downloadSvgAsPng(svg: SVGSVGElement, filename: string) {
  const xml = new XMLSerializer().serializeToString(svg);
  const url = URL.createObjectURL(
    new Blob([xml], { type: "image/svg+xml;charset=utf-8" }),
  );
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = W * 2;
    canvas.height = H * 2;
    const g = canvas.getContext("2d");
    if (!g) return;
    g.fillStyle = "#ffffff";
    g.fillRect(0, 0, canvas.width, canvas.height);
    g.drawImage(img, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    });
  };
  img.src = url;
}

export function InterfaceGraphView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const svgRef = useRef<SVGSVGElement>(null);
  const [filters, setFilters] = useState({ link_type: "", status: "" });
  const [selected, setSelected] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ifKeys(tenantId).graph(filters),
    queryFn: () =>
      api<InterfaceGraph>(tenantPath(tenantId, "/interfaces/graph"), {
        query: filters,
      }),
  });
  const layout = useMemo(() => {
    const nodes = data?.nodes.filter((n) => n.degree > 0) ?? [];
    return {
      nodes,
      pos: circleLayout(nodes, W, H),
      links: groupEdges(data?.edges ?? []),
    };
  }, [data]);
  const names = new Map(data?.nodes.map((n) => [n.id, n.name]));
  const related = selected
    ? (data?.edges ?? []).filter(
        (e) => e.source === selected || e.target === selected,
      )
    : [];
  return (
    <div className="space-y-4">
      <div className="card flex items-end gap-3">
        <Field label={t("ifField.link_type")}>
          <Select
            value={filters.link_type}
            onChange={(v) => setFilters((f) => ({ ...f, link_type: v }))}
            options={LINK_TYPES}
            group="linkType"
            allowEmpty
          />
        </Field>
        <Field label={t("ifField.status")}>
          <Select
            value={filters.status}
            onChange={(v) => setFilters((f) => ({ ...f, status: v }))}
            options={IF_STATUSES}
            group="ifStatus"
            allowEmpty
          />
        </Field>
        <button
          className="btn"
          onClick={() =>
            svgRef.current &&
            downloadSvgAsPng(svgRef.current, "interface-graph.png")
          }
        >
          {t("interfaces.downloadPng")}
        </button>
        <div className="ml-auto flex flex-wrap gap-3 text-xs">
          {LINK_TYPES.map((k) => (
            <span key={k} className="flex items-center gap-1">
              <span
                className="inline-block h-2 w-4 rounded"
                style={{ background: LINK_COLORS[k] }}
              />
              {t(`linkType.${k}`)}
            </span>
          ))}
        </div>
      </div>
      <div className="card overflow-auto">
        {isLoading ? (
          <Loading />
        ) : layout.nodes.length === 0 ? (
          <Empty />
        ) : (
          <svg
            ref={svgRef}
            xmlns="http://www.w3.org/2000/svg"
            viewBox={`0 0 ${W} ${H}`}
            width={W}
            height={H}
            role="img"
            aria-label={t("interfaces.tab.graph")}
            data-testid="interface-graph"
            fontFamily="sans-serif"
          >
            <defs>
              {LINK_TYPES.map((k) => (
                <marker
                  key={k}
                  id={`arrow-${k}`}
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={LINK_COLORS[k]} />
                </marker>
              ))}
            </defs>
            {layout.links.map((l) => {
              const a = layout.pos.get(l.source);
              const b = layout.pos.get(l.target);
              if (!a || !b) return null;
              const kind = l.edges[0]?.link_type ?? "other";
              const dim =
                selected !== null &&
                l.source !== selected &&
                l.target !== selected;
              return (
                <path
                  key={l.key}
                  d={linkPath(a, b, R)}
                  fill="none"
                  stroke={LINK_COLORS[kind]}
                  strokeWidth={Math.min(8, 1.5 + l.edges.length)}
                  strokeOpacity={dim ? 0.12 : 0.8}
                  markerEnd={`url(#arrow-${kind})`}
                  data-testid="graph-edge"
                >
                  <title>
                    {l.edges.map((e) => `${e.if_code} ${e.name}`).join("\n")}
                  </title>
                </path>
              );
            })}
            {layout.nodes.map((n) => {
              const p = layout.pos.get(n.id);
              if (!p) return null;
              const active = selected === n.id;
              return (
                <g
                  key={n.id}
                  transform={`translate(${p.x} ${p.y})`}
                  onClick={() => setSelected(active ? null : n.id)}
                  style={{ cursor: "pointer" }}
                  data-testid="graph-node"
                >
                  <circle
                    r={R}
                    fill={active ? "#1e3a8a" : "#eff6ff"}
                    stroke="#1e3a8a"
                    strokeWidth={2}
                  />
                  <text
                    textAnchor="middle"
                    dy="0.35em"
                    fontSize="10"
                    fill={active ? "#ffffff" : "#1e3a8a"}
                  >
                    {n.type}
                  </text>
                  <text
                    textAnchor="middle"
                    y={R + 14}
                    fontSize="12"
                    fill="#0f172a"
                  >
                    {n.short_name ?? n.name}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
      {selected && (
        <div className="card" data-testid="graph-selection">
          <h2 className="mb-2 font-semibold">{names.get(selected)}</h2>
          <table className="table">
            <tbody>
              {related.map((e) => (
                <tr key={e.id}>
                  <td className="font-mono text-xs">{e.if_code}</td>
                  <td>{e.name}</td>
                  <td>
                    {names.get(e.source)} → {names.get(e.target)}
                  </td>
                  <td>
                    <StatusBadge group="linkType" value={e.link_type} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
