import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type {
  DiscoverySession,
  FlowSummary,
  Page,
  SpecDocType,
  SpecDocument,
  SpecDocumentSummary,
  SpecRulePack,
  SpecTemplate,
  XlAnalysisSummary,
} from "../../api/types";
import { fmtDate } from "../../app/format";
import { listParam } from "../../app/handoff";
import { AUDIT_ROLES, useCanWrite, useRole, useTenantId } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import { Empty, ErrorText, Field, Loading, NeedTenant, PageHeader, Select, StatusBadge } from "../../components/ui";
import { EngagementSelect } from "../discoveryq/EngagementSelect";
import { SpecEditor } from "./SpecEditor";
import { DOC_TYPES, specKeys, specPath, toggle } from "./shared";

export function SpecForgePage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const [params, setParams] = useSearchParams();
  const docId = params.get("doc");
  if (!tenantId) return <NeedTenant />;
  const open = (id: string | null) => setParams(id ? { doc: id } : {});
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.specforge")} />
      {docId ? (
        <SpecEditor tenantId={tenantId} docId={docId} onBack={() => open(null)} />
      ) : (
        <DocList tenantId={tenantId} onOpen={open} />
      )}
    </div>
  );
}

function DocList({ tenantId, onOpen }: { tenantId: string; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const role = useRole();
  const canExport = role !== undefined && AUDIT_ROLES.includes(role);
  const qc = useQueryClient();
  const workspaceEngagement = useWorkspace((s) => s.engagementId);
  const [params] = useSearchParams();
  const [engagementId, setEngagementId] = useState(params.get("engagement") ?? "");
  const engagement = engagementId || workspaceEngagement || "";
  const keys = specKeys(tenantId);
  const { data, isLoading } = useQuery({
    queryKey: keys.list({ engagement }),
    queryFn: () =>
      api<Page<SpecDocumentSummary>>(specPath(tenantId, "/documents"), {
        query: { limit: 200, engagement_id: engagement },
      }),
  });
  const items = data?.items ?? [];
  const zip = `/api/v1${specPath(tenantId, "/documents/export.zip")}${engagement ? `?engagement_id=${engagement}` : ""}`;
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3">
        <EngagementSelect tenantId={tenantId} value={engagementId} onChange={setEngagementId} optional />
        {canExport && items.length > 0 && (
          <a className="btn" href={zip} data-testid="spec-zip">
            {t("specforge.exportZip")}
          </a>
        )}
      </div>
      {canWrite && (
        <CreateDoc
          key={engagement}
          params={params}
          tenantId={tenantId}
          engagementId={engagement}
          onCreated={(d) => {
            void qc.invalidateQueries({ queryKey: keys.all });
            onOpen(d.id);
          }}
        />
      )}
      <div className="card">
        {isLoading ? (
          <Loading />
        ) : items.length === 0 ? (
          <Empty />
        ) : (
          <table className="table" data-testid="spec-list">
            <thead>
              <tr>
                <th>{t("specforge.field.title")}</th>
                <th>{t("specforge.field.docType")}</th>
                <th>{t("common.status")}</th>
                <th>{t("specforge.field.versions")}</th>
                <th>{t("specforge.field.updated")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>
                    <button type="button" className="text-blue-700 underline" onClick={() => onOpen(d.id)}>
                      {d.title}
                    </button>
                  </td>
                  <td>{t(`specDocType.${d.doc_type}`)}</td>
                  <td>
                    <StatusBadge group="specStatus" value={d.status} />
                  </td>
                  <td>{d.version_count}</td>
                  <td>{fmtDate(d.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function CreateDoc({
  params,
  tenantId,
  engagementId,
  onCreated,
}: {
  params: URLSearchParams;
  tenantId: string;
  engagementId: string;
  onCreated: (d: SpecDocument) => void;
}) {
  const { t } = useTranslation();
  const keys = specKeys(tenantId);
  const [docType, setDocType] = useState<SpecDocType>("spec");
  const [title, setTitle] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [packs, setPacks] = useState<string[]>([]);
  const [sessionIds, setSessionIds] = useState<string[]>(() => listParam(params, "sessions"));
  const [flowIds, setFlowIds] = useState<string[]>(() => listParam(params, "flows"));
  const [erdIds, setErdIds] = useState<string[]>(() => listParam(params, "analyses"));
  const [interfaces, setInterfaces] = useState(params.get("interfaces") === "1");
  const [glossary, setGlossary] = useState(true);
  const [requirements, setRequirements] = useState("");
  const templates = useQuery({
    queryKey: keys.templates,
    queryFn: () => api<SpecTemplate[]>(specPath(tenantId, "/templates")),
  }).data;
  const rulePacks = useQuery({
    queryKey: keys.rulePacks,
    queryFn: () => api<SpecRulePack[]>(specPath(tenantId, "/rule-packs")),
  }).data;
  const sessions = useQuery({
    queryKey: ["specforge", tenantId, "sessions", engagementId],
    enabled: !!engagementId,
    queryFn: () =>
      api<Page<DiscoverySession>>(`/t/${tenantId}/discoveryq/sessions`, {
        query: { limit: 200, engagement_id: engagementId },
      }),
  }).data?.items;
  const flows = useQuery({
    queryKey: ["specforge", tenantId, "flows", engagementId],
    enabled: !!engagementId,
    queryFn: () =>
      api<Page<FlowSummary>>(`/t/${tenantId}/flowdesk/flows`, {
        query: { limit: 200, engagement_id: engagementId },
      }),
  }).data?.items;
  const erds = useQuery({
    queryKey: ["specforge", tenantId, "erds", engagementId],
    enabled: !!engagementId,
    queryFn: () =>
      api<Page<XlAnalysisSummary>>(`/t/${tenantId}/exmigrate/analyses`, {
        query: { limit: 200, engagement_id: engagementId },
      }),
  }).data?.items.filter((a) => a.erd_confirmed);
  const forType = (templates ?? []).filter((x) => x.doc === docType);
  const template = forType.find((x) => x.asset_id === templateId) ?? forType[0];
  const create = useMutation({
    mutationFn: () =>
      api<SpecDocument>(specPath(tenantId, "/documents"), {
        method: "POST",
        body: {
          engagement_id: engagementId,
          doc_type: docType,
          title: title || (docType === "spec" ? "Spec.md" : "Devin.md"),
          template_ref: template ? { asset_id: template.asset_id, version: template.version } : null,
          rule_pack_refs: (rulePacks ?? [])
            .filter((p) => packs.includes(p.asset_id))
            .map((p) => ({ asset_id: p.asset_id, version: p.version })),
          sources: {
            discovery_session_ids: sessionIds,
            flow_ids: flowIds,
            erd_analysis_ids: erdIds,
            interfaces,
            glossary,
            requirements: requirements || null,
          },
        },
      }),
    onSuccess: onCreated,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  if (!engagementId) return <p className="card text-sm text-slate-600">{t("specforge.needEngagement")}</p>;
  return (
    <form className="card space-y-3" onSubmit={submit} aria-label={t("specforge.new")} data-testid="spec-create">
      <h2 className="font-semibold">{t("specforge.new")}</h2>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("specforge.field.docType")}>
          <Select
            value={docType}
            onChange={(v) => {
              setDocType(v === "devin" ? "devin" : "spec");
              setTemplateId("");
            }}
            options={DOC_TYPES}
            group="specDocType"
            ariaLabel={t("specforge.field.docType")}
          />
        </Field>
        <Field label={t("specforge.field.title")}>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
        </Field>
        <Field label={t("specforge.field.template")}>
          <select
            className="input"
            value={template?.asset_id ?? ""}
            onChange={(e) => setTemplateId(e.target.value)}
            aria-label={t("specforge.field.template")}
          >
            {forType.map((x) => (
              <option key={x.asset_id} value={x.asset_id}>
                {x.title} v{x.version}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">{t("specforge.field.rulePacks")}</legend>
        {(rulePacks ?? []).map((p) => (
          <label key={p.asset_id} className="mr-4 inline-flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={packs.includes(p.asset_id)}
              onChange={() => setPacks((s) => toggle(s, p.asset_id))}
            />
            {p.title} ({p.rules.length})
          </label>
        ))}
        {docType === "spec" && <p className="text-xs text-slate-500">{t("specforge.rulePackHint")}</p>}
      </fieldset>
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">{t("specforge.field.sources")}</legend>
        <div className="text-sm">
          <span className="mr-2 text-slate-500">DiscoveryQ:</span>
          {(sessions ?? []).length === 0 && <span className="text-slate-400">—</span>}
          {(sessions ?? []).map((s) => (
            <label key={s.id} className="mr-4 inline-flex items-center gap-1">
              <input
                type="checkbox"
                checked={sessionIds.includes(s.id)}
                onChange={() => setSessionIds((x) => toggle(x, s.id))}
              />
              {s.title}
            </label>
          ))}
        </div>
        <div className="text-sm">
          <span className="mr-2 text-slate-500">FlowDesk:</span>
          {(flows ?? []).length === 0 && <span className="text-slate-400">—</span>}
          {(flows ?? []).map((f) => (
            <label key={f.id} className="mr-4 inline-flex items-center gap-1">
              <input
                type="checkbox"
                checked={flowIds.includes(f.id)}
                onChange={() => setFlowIds((x) => toggle(x, f.id))}
              />
              {f.title}
            </label>
          ))}
        </div>
        <div className="text-sm">
          <span className="mr-2 text-slate-500">ExMigrate ERD:</span>
          {(erds ?? []).length === 0 && <span className="text-slate-400">—</span>}
          {(erds ?? []).map((a) => (
            <label key={a.id} className="mr-4 inline-flex items-center gap-1">
              <input type="checkbox" checked={erdIds.includes(a.id)} onChange={() => setErdIds((x) => toggle(x, a.id))} />
              {a.filename}
            </label>
          ))}
        </div>
        <label className="mr-4 inline-flex items-center gap-1 text-sm">
          <input type="checkbox" checked={interfaces} onChange={(e) => setInterfaces(e.target.checked)} />
          {t("specforge.source.interfaces")}
        </label>
        <label className="mr-4 inline-flex items-center gap-1 text-sm">
          <input type="checkbox" checked={glossary} onChange={(e) => setGlossary(e.target.checked)} />
          {t("specforge.source.glossary")}
        </label>
      </fieldset>
      <Field label={t("specforge.field.requirements")}>
        <textarea
          className="input min-h-20 w-full"
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          maxLength={20000}
        />
      </Field>
      <div className="flex items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={create.isPending || !template}>
          {t("specforge.assemble")}
        </button>
        {create.error && <ErrorText error={create.error} />}
      </div>
    </form>
  );
}
