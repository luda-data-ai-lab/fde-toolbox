import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { api, tenantPath } from "../../api/client";
import type { AssetSummary, Engagement, EvalCase, EvalRun, Instance, Page, Project, System } from "../../api/types";
import { Empty, ErrorText, Field, Loading, NeedTenant, PageHeader, Select, StatusBadge } from "../../components/ui";
import { useAssetVersions, useCanWrite, useRole, useTenantId } from "../../app/hooks";
import { AssetDiffPanel, NewVersionForm } from "../../core/AssetsPage";
import { fmtDate } from "../../app/format";

const INSTANCE_STATUSES = ["ready", "pilot", "production", "stopped"] as const;
const DEPLOYMENTS = ["standalone", "hosted", "customer_env"] as const;

function useTemplates() {
  return useQuery({
    queryKey: ["assets", "agent_template"],
    queryFn: () => api<AssetSummary[]>("/assets", { query: { asset_type: "agent_template" } }),
  });
}

function useTenantList<T>(tenantId: string | null, key: string, path: string) {
  return useQuery({
    queryKey: [key, tenantId],
    queryFn: () => api<Page<T>>(tenantPath(tenantId, path), { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
}

function InstanceForm({ tenantId, onDone }: { tenantId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const templates = useTemplates();
  const engagements = useTenantList<Engagement>(tenantId, "engagements", "/engagements");
  const systems = useTenantList<System>(tenantId, "systems", "/systems");
  const projects = useTenantList<Project>(tenantId, "projects-all", "/devtracker/projects");
  const [form, setForm] = useState({
    name: "",
    asset_id: "",
    version: "",
    engagement_id: "",
    deployment: "standalone",
    dev_project_id: "",
    system_ids: [] as string[],
  });
  const versions = useAssetVersions(form.asset_id || undefined);
  const create = useMutation({
    mutationFn: () =>
      api<Instance>(tenantPath(tenantId, "/agenthub/instances"), {
        method: "POST",
        body: {
          name: form.name,
          template_ref: { asset_id: form.asset_id, version: Number(form.version) },
          engagement_id: form.engagement_id,
          deployment: form.deployment,
          system_ids: form.system_ids,
          dev_project_id: form.dev_project_id || null,
        },
      }),
    onSuccess: onDone,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <form onSubmit={submit} className="card grid grid-cols-4 items-end gap-3" data-testid="instance-form">
      <Field label={t("common.name")}>
        <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </Field>
      <Field label={t("agenthub.template")}>
        <select className="input" value={form.asset_id} onChange={(e) => setForm({ ...form, asset_id: e.target.value, version: "" })} required>
          <option value="">{t("common.none")}</option>
          {templates.data?.map((a) => (
            <option key={a.asset_id} value={a.asset_id}>
              {a.title}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("assets.version")}>
        <select className="input" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} required>
          <option value="">{t("common.none")}</option>
          {versions.data?.map((v) => (
            <option key={v.version} value={v.version}>
              v{v.version} ({t(`assetStatus.${v.status}`)})
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("nav.engagements")}>
        <select className="input" value={form.engagement_id} onChange={(e) => setForm({ ...form, engagement_id: e.target.value })} required>
          <option value="">{t("common.none")}</option>
          {engagements.data?.items.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("agenthub.deployment")}>
        <Select value={form.deployment} onChange={(deployment) => setForm({ ...form, deployment })} options={DEPLOYMENTS} group="deployment" />
      </Field>
      <Field label={t("agenthub.devProject")}>
        <select className="input" value={form.dev_project_id} onChange={(e) => setForm({ ...form, dev_project_id: e.target.value })}>
          <option value="">{t("common.none")}</option>
          {projects.data?.items.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
      </Field>
      <fieldset className="col-span-2">
        <legend className="label">{t("agenthub.systems")}</legend>
        <div className="flex flex-wrap gap-2">
          {systems.data?.items.map((s) => (
            <label key={s.id} className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={form.system_ids.includes(s.id)}
                onChange={(e) =>
                  setForm({
                    ...form,
                    system_ids: e.target.checked ? [...form.system_ids, s.id] : form.system_ids.filter((x) => x !== s.id),
                  })
                }
              />
              {s.name}
            </label>
          ))}
        </div>
      </fieldset>
      <button className="btn btn-primary w-fit">{t("common.create")}</button>
      <div className="col-span-3">
        <ErrorText error={create.error} />
      </div>
    </form>
  );
}

export function AgentHubPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const templates = useTemplates();
  const instances = useTenantList<Instance>(tenantId, "instances", "/agenthub/instances");
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api<Instance>(tenantPath(tenantId, `/agenthub/instances/${id}`), { method: "PATCH", body: { status } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["instances"] }),
  });
  const title = (id: string) => templates.data?.find((a) => a.asset_id === id)?.title ?? id;
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.agenthub")} />
      <section className="card">
        <h2 className="mb-2 font-semibold">{t("agenthub.templates")}</h2>
        {!templates.data?.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.title")}</th>
                <th>{t("assets.latest")}</th>
                <th>{t("common.status")}</th>
              </tr>
            </thead>
            <tbody>
              {templates.data.map((a) => (
                <tr key={a.asset_id}>
                  <td>
                    <Link className="text-blue-700 hover:underline" to={`/agenthub/templates/${a.asset_id}`}>
                      {a.title}
                    </Link>
                  </td>
                  <td>v{a.latest_version}</td>
                  <td>
                    <StatusBadge group="assetStatus" value={a.latest_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {!tenantId ? (
        <NeedTenant />
      ) : (
        <>
          {canWrite && (
            <InstanceForm tenantId={tenantId} onDone={() => void qc.invalidateQueries({ queryKey: ["instances"] })} />
          )}
          <section className="card">
            <h2 className="mb-2 font-semibold">{t("agenthub.instances")}</h2>
            {!instances.data?.items.length ? (
              <Empty />
            ) : (
              <table className="table" data-testid="instances-table">
                <thead>
                  <tr>
                    <th>{t("common.name")}</th>
                    <th>{t("agenthub.template")}</th>
                    <th>{t("agenthub.deployment")}</th>
                    <th>{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {instances.data.items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.name}</td>
                      <td>
                        {title(i.template_ref.asset_id)} v{i.template_ref.version}
                      </td>
                      <td>{t(`deployment.${i.deployment}`)}</td>
                      <td className="w-40">
                        {canWrite ? (
                          <Select
                            value={i.status}
                            options={INSTANCE_STATUSES}
                            group="instanceStatus"
                            onChange={(status) => update.mutate({ id: i.id, status })}
                            ariaLabel={t("common.status")}
                          />
                        ) : (
                          <StatusBadge group="instanceStatus" value={i.status} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function EvalCases({ assetId, version }: { assetId: string; version: number }) {
  const { t } = useTranslation();
  const isAdmin = useRole() === "luda_admin";
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", input: "", expected: "", criteria: "" });
  const key = ["eval-cases", assetId, version];
  const cases = useQuery({
    queryKey: key,
    queryFn: () => api<EvalCase[]>(`/assets/${assetId}/versions/${version}/eval-cases`),
  });
  const create = useMutation({
    mutationFn: () => api<EvalCase>(`/assets/${assetId}/versions/${version}/eval-cases`, { method: "POST", body: form }),
    onSuccess: () => {
      setForm({ name: "", input: "", expected: "", criteria: "" });
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <section className="card space-y-2">
      <h2 className="font-semibold">
        {t("agenthub.evalCases")} v{version}
      </h2>
      {!cases.data?.length ? (
        <Empty />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("common.name")}</th>
              <th>{t("agenthub.input")}</th>
              <th>{t("agenthub.expected")}</th>
              <th>{t("agenthub.criteria")}</th>
            </tr>
          </thead>
          <tbody>
            {cases.data.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.input}</td>
                <td>{c.expected}</td>
                <td>{c.criteria}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {isAdmin && (
        <form onSubmit={submit} className="grid grid-cols-5 items-end gap-2">
          {(["name", "input", "expected", "criteria"] as const).map((k) => (
            <Field key={k} label={t(k === "name" ? "common.name" : `agenthub.${k}`)}>
              <input className="input" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} required={k !== "criteria"} />
            </Field>
          ))}
          <button className="btn btn-primary w-fit">{t("common.create")}</button>
        </form>
      )}
      <ErrorText error={create.error} />
      <EvalRuns assetId={assetId} version={version} cases={cases.data ?? []} />
    </section>
  );
}

function EvalRuns({ assetId, version, cases }: { assetId: string; version: number; cases: EvalCase[] }) {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [results, setResults] = useState<Record<string, boolean>>({});
  const [notes, setNotes] = useState("");
  const key = ["eval-runs", tenantId, assetId, version];
  const runs = useQuery({
    queryKey: key,
    queryFn: () =>
      api<Page<EvalRun>>(tenantPath(tenantId, "/agenthub/eval-runs"), { query: { asset_id: assetId, limit: 200 } }),
    enabled: !!tenantId,
  });
  const record = useMutation({
    mutationFn: () =>
      api<EvalRun>(tenantPath(tenantId, "/agenthub/eval-runs"), {
        method: "POST",
        body: {
          template_ref: { asset_id: assetId, version },
          results: cases.map((c) => ({ case_id: c.id, passed: !!results[c.id] })),
          notes,
        },
      }),
    onSuccess: () => {
      setResults({});
      setNotes("");
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  if (!tenantId) return null;
  return (
    <div className="space-y-2 border-t border-slate-100 pt-2">
      <h3 className="label">{t("agenthub.evalRuns")}</h3>
      <ul className="text-sm">
        {runs.data?.items.filter((r) => r.template_ref.version === version).map((r) => (
          <li key={r.id}>
            {fmtDate(r.run_at)} — {t("agenthub.passRate")} {Math.round((r.pass_rate ?? 0) * 100)}% {r.notes}
          </li>
        ))}
      </ul>
      {canWrite && cases.length > 0 && (
        <div className="space-y-1">
          {cases.map((c) => (
            <label key={c.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!results[c.id]} onChange={(e) => setResults({ ...results, [c.id]: e.target.checked })} />
              {c.name} — {t("agenthub.passed")}
            </label>
          ))}
          <input className="input" placeholder={t("common.notes")} value={notes} onChange={(e) => setNotes(e.target.value)} />
          <button className="btn btn-primary" onClick={() => record.mutate()}>
            {t("agenthub.recordRun")}
          </button>
          <ErrorText error={record.error} />
        </div>
      )}
    </div>
  );
}

export function TemplatePage() {
  const { t } = useTranslation();
  const { assetId } = useParams();
  const isAdmin = useRole() === "luda_admin";
  const qc = useQueryClient();
  const { data, error } = useAssetVersions(assetId);
  const [selected, setSelected] = useState<number | null>(null);
  if (error) return <ErrorText error={error} />;
  const latest = data?.[data.length - 1];
  if (!data || !latest) return <Loading />;
  const current = data.find((v) => v.version === selected) ?? latest;
  const payload = current.payload as { system_prompt?: string; purpose?: string };
  return (
    <div className="space-y-4">
      <PageHeader title={latest.title} />
      <div className="flex gap-2">
        {data.map((v) => (
          <button key={v.version} className={`btn ${v.version === current.version ? "btn-primary" : ""}`} onClick={() => setSelected(v.version)}>
            v{v.version}
          </button>
        ))}
      </div>
      <section className="card space-y-2">
        <p className="text-sm text-slate-600">{payload.purpose}</p>
        <h3 className="label">{t("agenthub.systemPrompt")}</h3>
        <pre className="whitespace-pre-wrap rounded bg-slate-50 p-3 text-sm">{payload.system_prompt}</pre>
        <p className="text-xs text-slate-500">
          {t("assets.changeNote")}: {current.change_note}
        </p>
      </section>
      <AssetDiffPanel assetId={latest.asset_id} versions={data.map((v) => v.version)} />
      <EvalCases key={current.version} assetId={latest.asset_id} version={current.version} />
      {isAdmin && <NewVersionForm asset={latest} onDone={() => void qc.invalidateQueries({ queryKey: ["asset", assetId] })} />}
    </div>
  );
}
