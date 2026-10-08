import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { Flow, FlowGraph, FlowNodeType, FlowSnapshot, Page, System } from "../../api/types";
import { AUDIT_ROLES, useCanWrite, useRole } from "../../app/hooks";
import { ErrorText, Field, Loading, Select, StatusBadge } from "../../components/ui";
import {
  LANE_HEIGHT,
  LANE_LABEL_WIDTH,
  NODE_HEIGHT,
  NODE_TYPES,
  NODE_WIDTH,
  PERSPECTIVES,
  downloadPng,
  downloadSvg,
  flowKeys,
  flowPath,
  graphToSvg,
  laneAt,
  nextId,
  nodeFill,
} from "./shared";

type StepData = { label: string; kind: FlowNodeType; systemId: string | null; systemName: string };
type StepNode = Node<StepData, "step">;
type LaneNode = Node<{ label: string; width: number }, "lane">;
type CanvasNode = StepNode | LaneNode;

const LANE_PREFIX = "lane:";

function StepView({ data, selected }: NodeProps<StepNode>) {
  const round = data.kind === "start" || data.kind === "end";
  return (
    <div
      className="flex items-center justify-center px-2 text-center text-xs text-slate-900"
      style={{
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        background: nodeFill(data.kind),
        border: `${selected ? 2 : 1}px ${data.kind === "note" ? "dashed" : "solid"} ${selected ? "#1d4ed8" : "#334155"}`,
        borderRadius: round ? NODE_HEIGHT / 2 : data.kind === "decision" ? 2 : 8,
      }}
      data-testid="flow-node"
    >
      <Handle type="target" position={Position.Left} />
      <span className="line-clamp-2">{data.label || data.systemName || "…"}</span>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function LaneView({ data }: NodeProps<LaneNode>) {
  return (
    <div className="border-y border-slate-300 bg-slate-50/60" style={{ width: data.width, height: LANE_HEIGHT }}>
      <div
        className="flex h-full items-center border-r border-slate-300 px-2 text-sm font-semibold text-slate-700"
        style={{ width: LANE_LABEL_WIDTH }}
      >
        {data.label}
      </div>
    </div>
  );
}

const nodeTypes = { step: StepView, lane: LaneView };

function toCanvas(graph: FlowGraph, systems: Map<string, string>): { nodes: StepNode[]; edges: Edge[] } {
  return {
    nodes: graph.nodes.map((n) => ({
      id: n.id,
      type: "step",
      position: n.position,
      data: {
        label: n.label,
        kind: n.type,
        systemId: n.system_id ?? null,
        systemName: n.system_id ? (systems.get(n.system_id) ?? "") : "",
      },
    })),
    edges: graph.edges.map((e) => ({ id: e.id, source: e.source, target: e.target, label: e.label ?? undefined })),
  };
}

function toGraph(lanes: string[], nodes: StepNode[], edges: Edge[]): FlowGraph {
  return {
    schema_version: 1,
    lanes,
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.data.kind,
      label: n.data.label,
      lane: laneAt(lanes, n.position.y),
      system_id: n.data.systemId,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      data: {},
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: typeof e.label === "string" && e.label ? e.label : null,
    })),
  };
}

export function FlowEditor({
  tenantId,
  flowId,
  onOpen,
}: {
  tenantId: string;
  flowId: string;
  onOpen: (id: string | null) => void;
}) {
  const keys = flowKeys(tenantId);
  const flow = useQuery({
    queryKey: keys.flow(flowId),
    queryFn: () => api<Flow>(flowPath(tenantId, `/flows/${flowId}`)),
  });
  const systems = useQuery({
    queryKey: ["systems", tenantId, "all"],
    queryFn: () => api<Page<System>>(`/t/${tenantId}/systems`, { query: { limit: 200 } }),
  });
  if (flow.isLoading || systems.isLoading) return <Loading />;
  if (!flow.data) return <ErrorText error={flow.error} />;
  return (
    <Canvas
      key={`${flow.data.id}:${flow.data.updated_at}`}
      tenantId={tenantId}
      flow={flow.data}
      systems={systems.data?.items ?? []}
      onOpen={onOpen}
    />
  );
}

function Canvas({
  tenantId,
  flow,
  systems,
  onOpen,
}: {
  tenantId: string;
  flow: Flow;
  systems: System[];
  onOpen: (id: string | null) => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const canWrite = useCanWrite();
  const role = useRole();
  const canExport = role !== undefined && AUDIT_ROLES.includes(role);
  const keys = flowKeys(tenantId);
  const systemNames = useMemo(() => new Map(systems.map((s) => [s.id, s.short_name ?? s.name])), [systems]);
  const initial = useMemo(() => toCanvas(flow.graph, systemNames), [flow.graph, systemNames]);
  const [lanes, setLanes] = useState<string[]>(flow.graph.lanes);
  const [nodes, setNodes] = useState<StepNode[]>(initial.nodes);
  const [edges, setEdges] = useState<Edge[]>(initial.edges);
  const [dirty, setDirty] = useState(false);
  const [meta, setMeta] = useState({ title: flow.title, perspective: flow.perspective });
  const [newType, setNewType] = useState<FlowNodeType>("task");
  const [laneName, setLaneName] = useState("");
  const selectedNode = nodes.find((n) => n.selected);
  const selectedEdge = edges.find((e) => e.selected);
  const graph = () => toGraph(lanes, nodes, edges);
  const touch = () => setDirty(true);

  const laneWidth = LANE_LABEL_WIDTH + Math.max(800, ...nodes.map((n) => n.position.x + NODE_WIDTH + 80));
  const laneNodes: LaneNode[] = lanes.map((label, i) => ({
    id: `${LANE_PREFIX}${i}`,
    type: "lane",
    position: { x: -LANE_LABEL_WIDTH, y: i * LANE_HEIGHT },
    data: { label, width: laneWidth },
    draggable: false,
    selectable: false,
    connectable: false,
    zIndex: -1,
    style: { pointerEvents: "none" },
  }));
  const canvasNodes: CanvasNode[] = [...laneNodes, ...nodes];

  const onNodesChange = useCallback((changes: NodeChange<CanvasNode>[]) => {
    const own = changes.filter((c) => !("id" in c) || !c.id.startsWith(LANE_PREFIX)) as NodeChange<StepNode>[];
    if (own.some((c) => c.type === "position" || c.type === "remove")) setDirty(true);
    setNodes((ns) => applyNodeChanges(own, ns));
  }, []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    if (changes.some((c) => c.type === "remove")) setDirty(true);
    setEdges((es) => applyEdgeChanges(changes, es));
  }, []);
  const onConnect = useCallback((c: Connection) => {
    setDirty(true);
    setEdges((es) =>
      addEdge(
        {
          ...c,
          id: nextId(
            "e",
            es.map((e) => e.id),
          ),
        },
        es,
      ),
    );
  }, []);

  const updateNode = (patch: Partial<StepData>) => {
    if (!selectedNode) return;
    touch();
    setNodes((ns) => ns.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, ...patch } } : n)));
  };
  const addNode = () => {
    const id = nextId(
      "n",
      nodes.map((n) => n.id),
    );
    const x = 40 + (nodes.length ? Math.max(...nodes.map((n) => n.position.x)) + NODE_WIDTH + 40 : 0);
    const node: StepNode = {
      id,
      type: "step",
      position: { x, y: 40 },
      data: { label: t(`flowNodeType.${newType}`), kind: newType, systemId: null, systemName: "" },
      selected: true,
    };
    touch();
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), node]);
  };
  const addLane = () => {
    const name = laneName.trim();
    if (!name || lanes.includes(name)) return;
    touch();
    setLanes((ls) => [...ls, name]);
    setLaneName("");
  };
  const removeLane = (name: string) => {
    touch();
    setLanes((ls) => ls.filter((x) => x !== name));
  };

  const refresh = () => qc.invalidateQueries({ queryKey: keys.all });
  const save = useMutation({
    mutationFn: () =>
      api<Flow>(flowPath(tenantId, `/flows/${flow.id}`), {
        method: "PATCH",
        body: { title: meta.title, perspective: meta.perspective, graph: graph() },
      }),
    onSuccess: refresh,
  });
  const pair = useMutation({
    mutationFn: () =>
      api<Flow>(flowPath(tenantId, `/flows/${flow.id}/pair`), { method: "POST", body: { copy_graph: true } }),
    onSuccess: async (other) => {
      await refresh();
      onOpen(other.id);
    },
  });
  const remove = useMutation({
    mutationFn: () => api<unknown>(flowPath(tenantId, `/flows/${flow.id}`), { method: "DELETE" }),
    onSuccess: async () => {
      await refresh();
      onOpen(null);
    },
  });
  const exportImage = (fmt: "svg" | "png") => {
    const { svg, width, height } = graphToSvg(graph(), systemNames);
    const name = `flow-${flow.id}.${fmt}`;
    if (fmt === "svg") downloadSvg(svg, name);
    else downloadPng(svg, width, height, name);
  };
  const base = `/api/v1${flowPath(tenantId, `/flows/${flow.id}`)}`;

  return (
    <div className="space-y-3">
      <div className="card flex flex-wrap items-end gap-3">
        <button className="btn" onClick={() => onOpen(null)}>
          {t("flowdesk.back")}
        </button>
        <Field label={t("flowdesk.field.title")}>
          <input
            className="input"
            value={meta.title}
            disabled={!canWrite}
            onChange={(e) => {
              touch();
              setMeta((m) => ({ ...m, title: e.target.value }));
            }}
          />
        </Field>
        <Field label={t("flowdesk.field.perspective")}>
          {canWrite ? (
            <Select
              value={meta.perspective}
              onChange={(v) => {
                touch();
                setMeta((m) => ({ ...m, perspective: v }));
              }}
              options={PERSPECTIVES}
              group="perspective"
            />
          ) : (
            <span className="input block">{t(`perspective.${meta.perspective}`)}</span>
          )}
        </Field>
        <StatusBadge group="flowKind" value={flow.kind} />
        {flow.pair_id ? (
          <button className="btn" onClick={() => flow.pair_id && onOpen(flow.pair_id)}>
            {t(flow.kind === "as_is" ? "flowdesk.openToBe" : "flowdesk.openAsIs")}
          </button>
        ) : (
          canWrite && (
            <button className="btn" onClick={() => pair.mutate()} disabled={pair.isPending}>
              {t(flow.kind === "as_is" ? "flowdesk.createToBe" : "flowdesk.createAsIs")}
            </button>
          )
        )}
        <div className="ml-auto flex flex-wrap gap-2">
          {canWrite && (
            <button className="btn btn-primary" onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
              {dirty ? t("common.save") : t("flowdesk.saved")}
            </button>
          )}
          {canExport && (
            <>
              <a className="btn" href={`${base}/export.json`}>
                JSON
              </a>
              <a className="btn" href={`${base}/export.mmd`}>
                Mermaid
              </a>
            </>
          )}
          <button className="btn" onClick={() => exportImage("svg")}>
            SVG
          </button>
          <button className="btn" onClick={() => exportImage("png")}>
            PNG
          </button>
          {canWrite && (
            <button
              className="btn btn-danger"
              onClick={() => window.confirm(t("flowdesk.confirmDelete")) && remove.mutate()}
            >
              {t("common.delete")}
            </button>
          )}
        </div>
      </div>
      <ErrorText error={save.error ?? pair.error ?? remove.error} />
      <div className="grid gap-3 lg:grid-cols-[1fr_18rem]">
        <div className="card h-[600px] p-0" data-testid="flow-canvas">
          <ReactFlow<CanvasNode, Edge>
            nodes={canvasNodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodesDraggable={canWrite}
            nodesConnectable={canWrite}
            deleteKeyCode={canWrite ? ["Backspace", "Delete"] : null}
            defaultEdgeOptions={{ type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed } }}
            fitView
            minZoom={0.2}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <div className="space-y-3">
          {canWrite && (
            <div className="card space-y-2">
              <h2 className="font-semibold">{t("flowdesk.addNode")}</h2>
              <div className="flex gap-2">
                <Select
                  value={newType}
                  onChange={(v) => setNewType(v as FlowNodeType)}
                  options={NODE_TYPES}
                  group="flowNodeType"
                  ariaLabel={t("flowdesk.field.nodeType")}
                />
                <button className="btn shrink-0" onClick={addNode}>
                  {t("flowdesk.add")}
                </button>
              </div>
              <p className="text-xs text-slate-500">{t("flowdesk.hint")}</p>
            </div>
          )}
          {selectedNode && (
            <div className="card space-y-2" data-testid="node-panel">
              <h2 className="font-semibold">{t("flowdesk.node")}</h2>
              <Field label={t("flowdesk.field.label")}>
                <input
                  className="input"
                  value={selectedNode.data.label}
                  disabled={!canWrite}
                  onChange={(e) => updateNode({ label: e.target.value })}
                />
              </Field>
              <Field label={t("flowdesk.field.nodeType")}>
                <select
                  className="input"
                  value={selectedNode.data.kind}
                  disabled={!canWrite}
                  onChange={(e) => updateNode({ kind: e.target.value as FlowNodeType })}
                >
                  {NODE_TYPES.map((x) => (
                    <option key={x} value={x}>
                      {t(`flowNodeType.${x}`)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("flowdesk.field.system")}>
                <select
                  className="input"
                  value={selectedNode.data.systemId ?? ""}
                  disabled={!canWrite}
                  onChange={(e) => {
                    const id = e.target.value || null;
                    updateNode({ systemId: id, systemName: id ? (systemNames.get(id) ?? "") : "" });
                  }}
                >
                  <option value="">{t("common.none")}</option>
                  {systems.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </Field>
              <p className="text-xs text-slate-500">
                {t("flowdesk.field.lane")}: {laneAt(lanes, selectedNode.position.y) ?? "—"}
              </p>
            </div>
          )}
          {selectedEdge && (
            <div className="card space-y-2" data-testid="edge-panel">
              <h2 className="font-semibold">{t("flowdesk.edge")}</h2>
              <Field label={t("flowdesk.field.condition")}>
                <input
                  className="input"
                  value={typeof selectedEdge.label === "string" ? selectedEdge.label : ""}
                  disabled={!canWrite}
                  onChange={(e) => {
                    touch();
                    const label = e.target.value;
                    setEdges((es) => es.map((x) => (x.id === selectedEdge.id ? { ...x, label } : x)));
                  }}
                />
              </Field>
            </div>
          )}
          <div className="card space-y-2">
            <h2 className="font-semibold">{t("flowdesk.lanes")}</h2>
            <ul className="space-y-1 text-sm">
              {lanes.map((l) => (
                <li key={l} className="flex items-center justify-between">
                  <span>{l}</span>
                  {canWrite && (
                    <button className="text-xs text-red-700" onClick={() => removeLane(l)}>
                      {t("common.delete")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {canWrite && (
              <div className="flex gap-2">
                <input
                  className="input"
                  value={laneName}
                  placeholder={t("flowdesk.laneName")}
                  aria-label={t("flowdesk.laneName")}
                  onChange={(e) => setLaneName(e.target.value)}
                />
                <button className="btn shrink-0" onClick={addLane}>
                  {t("flowdesk.add")}
                </button>
              </div>
            )}
          </div>
          <Snapshots tenantId={tenantId} flowId={flow.id} dirty={dirty} />
        </div>
      </div>
    </div>
  );
}

function Snapshots({ tenantId, flowId, dirty }: { tenantId: string; flowId: string; dirty: boolean }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const canWrite = useCanWrite();
  const keys = flowKeys(tenantId);
  const [note, setNote] = useState("");
  const list = useQuery({
    queryKey: keys.snapshots(flowId),
    queryFn: () => api<FlowSnapshot[]>(flowPath(tenantId, `/flows/${flowId}/snapshots`)),
  });
  const create = useMutation({
    mutationFn: () =>
      api<FlowSnapshot>(flowPath(tenantId, `/flows/${flowId}/snapshots`), {
        method: "POST",
        body: { note: note || null },
      }),
    onSuccess: () => {
      setNote("");
      return qc.invalidateQueries({ queryKey: keys.snapshots(flowId) });
    },
  });
  const restore = useMutation({
    mutationFn: (id: string) =>
      api<Flow>(flowPath(tenantId, `/flows/${flowId}/snapshots/${id}/restore`), { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
  return (
    <div className="card space-y-2" data-testid="snapshots">
      <h2 className="font-semibold">{t("flowdesk.snapshots")}</h2>
      {canWrite && (
        <>
          <div className="flex gap-2">
            <input
              className="input"
              value={note}
              placeholder={t("flowdesk.snapshotNote")}
              aria-label={t("flowdesk.snapshotNote")}
              onChange={(e) => setNote(e.target.value)}
            />
            <button className="btn shrink-0" onClick={() => create.mutate()} disabled={dirty || create.isPending}>
              {t("flowdesk.takeSnapshot")}
            </button>
          </div>
          {dirty && <p className="text-xs text-amber-700">{t("flowdesk.saveFirst")}</p>}
        </>
      )}
      <ul className="space-y-1 text-sm">
        {(list.data ?? []).map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-2">
            <span>
              v{s.version} · {s.note ?? "—"} <span className="text-xs text-slate-500">({s.node_count})</span>
            </span>
            {canWrite && (
              <button
                className="text-xs text-blue-700"
                onClick={() => window.confirm(t("flowdesk.confirmRestore")) && restore.mutate(s.id)}
              >
                {t("flowdesk.restore")}
              </button>
            )}
          </li>
        ))}
      </ul>
      <ErrorText error={create.error ?? restore.error} />
    </div>
  );
}
