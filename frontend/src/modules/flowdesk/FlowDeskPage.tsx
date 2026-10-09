import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type { Flow, FlowSummary, FlowTemplate, Page } from "../../api/types";
import { useCanWrite, useTenantId } from "../../app/hooks";
import { listParam } from "../../app/handoff";
import { useWorkspace } from "../../app/store";
import { Empty, ErrorText, Field, Loading, NeedTenant, PageHeader, Select, StatusBadge } from "../../components/ui";
import { EngagementSelect } from "../discoveryq/EngagementSelect";
import { FlowEditor } from "./FlowEditor";
import { GenerateFlow } from "./GenerateFlow";
import { FLOW_KINDS, PERSPECTIVES, flowKeys, flowPath } from "./shared";

export function FlowDeskPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const [params, setParams] = useSearchParams();
  const flowId = params.get("flow");
  if (!tenantId) return <NeedTenant />;
  const open = (id: string | null) => setParams(id ? { flow: id } : {});
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.flowdesk")} />
      {flowId ? (
        <FlowEditor tenantId={tenantId} flowId={flowId} onOpen={open} />
      ) : (
        <FlowList tenantId={tenantId} onOpen={open} />
      )}
    </div>
  );
}

function FlowList({ tenantId, onOpen }: { tenantId: string; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const workspaceEngagement = useWorkspace((s) => s.engagementId);
  const [params] = useSearchParams();
  const handedInsights = listParam(params, "insights");
  const [engagementId, setEngagementId] = useState(params.get("engagement") ?? "");
  const [kind, setKind] = useState("");
  const engagement = engagementId || workspaceEngagement || "";
  const keys = flowKeys(tenantId);
  const filters = { engagement_id: engagement, kind };
  const { data, isLoading } = useQuery({
    queryKey: keys.list(filters),
    queryFn: () => api<Page<FlowSummary>>(flowPath(tenantId, "/flows"), { query: { limit: 200, ...filters } }),
  });
  const items = data?.items ?? [];
  const titles = new Map(items.map((f) => [f.id, f.title]));
  const created = (f: Flow) => {
    void qc.invalidateQueries({ queryKey: keys.all });
    onOpen(f.id);
  };
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3">
        <EngagementSelect tenantId={tenantId} value={engagementId} onChange={setEngagementId} optional />
        <Field label={t("flowdesk.field.kind")}>
          <Select value={kind} onChange={setKind} options={FLOW_KINDS} group="flowKind" allowEmpty />
        </Field>
      </div>
      {canWrite && <CreateFlow tenantId={tenantId} engagementId={engagement} onCreated={created} />}
      {canWrite && engagement && (
        <GenerateFlow
          key={engagement}
          tenantId={tenantId}
          engagementId={engagement}
          initialInsights={handedInsights}
          onCreated={created}
        />
      )}
      <div className="card">
        {isLoading ? (
          <Loading />
        ) : items.length === 0 ? (
          <Empty />
        ) : (
          <table className="table" data-testid="flow-list">
            <thead>
              <tr>
                <th>{t("flowdesk.field.title")}</th>
                <th>{t("flowdesk.field.kind")}</th>
                <th>{t("flowdesk.field.perspective")}</th>
                <th>{t("flowdesk.field.pair")}</th>
                <th>{t("flowdesk.field.nodes")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((f) => (
                <tr key={f.id}>
                  <td>
                    <button className="text-left text-blue-700 hover:underline" onClick={() => onOpen(f.id)}>
                      {f.title}
                    </button>
                  </td>
                  <td>
                    <StatusBadge group="flowKind" value={f.kind} />
                  </td>
                  <td>{t(`perspective.${f.perspective}`, { defaultValue: f.perspective })}</td>
                  <td>{f.pair_id ? (titles.get(f.pair_id) ?? t("flowdesk.paired")) : "—"}</td>
                  <td>{f.node_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function CreateFlow({
  tenantId,
  engagementId,
  onCreated,
}: {
  tenantId: string;
  engagementId: string;
  onCreated: (f: Flow) => void;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ title: "", kind: "as_is", perspective: "business", template: "" });
  const templates = useQuery({
    queryKey: flowKeys(tenantId).templates,
    queryFn: () => api<FlowTemplate[]>(flowPath(tenantId, "/templates")),
  });
  const list = templates.data ?? [];
  const create = useMutation({
    mutationFn: () => {
      const tpl = list.find((x) => x.asset_id === form.template);
      return api<Flow>(flowPath(tenantId, "/flows"), {
        method: "POST",
        body: {
          engagement_id: engagementId,
          title: form.title,
          kind: form.kind,
          perspective: form.perspective,
          template_ref: tpl ? { asset_id: tpl.asset_id, version: tpl.version } : null,
        },
      });
    },
    onSuccess: onCreated,
  });
  const importFlow = useMutation({
    mutationFn: async (file: File) => {
      const document: unknown = JSON.parse(await file.text());
      return api<Flow>(flowPath(tenantId, "/flows/import"), {
        method: "POST",
        body: { engagement_id: engagementId, document },
      });
    },
    onSuccess: onCreated,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <form className="card space-y-3" onSubmit={submit} aria-label={t("flowdesk.new")}>
      <h2 className="font-semibold">{t("flowdesk.new")}</h2>
      {!engagementId && <p className="text-sm text-slate-600">{t("flowdesk.needEngagement")}</p>}
      <div className="grid gap-3 md:grid-cols-4">
        <Field label={t("flowdesk.field.title")}>
          <input className="input" required value={form.title} onChange={(e) => set("title")(e.target.value)} />
        </Field>
        <Field label={t("flowdesk.field.kind")}>
          <Select value={form.kind} onChange={set("kind")} options={FLOW_KINDS} group="flowKind" />
        </Field>
        <Field label={t("flowdesk.field.perspective")}>
          <Select value={form.perspective} onChange={set("perspective")} options={PERSPECTIVES} group="perspective" />
        </Field>
        <Field label={t("flowdesk.field.template")}>
          <select className="input" value={form.template} onChange={(e) => set("template")(e.target.value)}>
            <option value="">{t("flowdesk.blank")}</option>
            {list.map((x) => (
              <option key={x.asset_id} value={x.asset_id}>
                {x.title} (v{x.version})
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn btn-primary" disabled={!engagementId || create.isPending}>
          {t("common.create")}
        </button>
        <label className="btn cursor-pointer">
          {t("flowdesk.importJson")}
          <input
            type="file"
            accept="application/json,.json"
            className="hidden"
            disabled={!engagementId}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importFlow.mutate(file);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <ErrorText error={create.error ?? importFlow.error} />
    </form>
  );
}
