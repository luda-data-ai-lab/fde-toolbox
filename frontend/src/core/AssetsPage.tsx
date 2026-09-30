import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Asset, AssetDiff, AssetSummary } from "../api/types";
import { Empty, ErrorText, Field, Loading, PageHeader, Select, StatusBadge } from "../components/ui";
import { useAssetVersions, useRole } from "../app/hooks";

const ASSET_TYPES = [
  "question_bank",
  "flow_template",
  "if_template",
  "upper_ontology",
  "glossary_template",
  "spec_template",
  "rule_pack",
  "agent_template",
] as const;
const ASSET_STATUSES = ["draft", "published", "deprecated"] as const;

function parseJson(text: string): Record<string, unknown> | null {
  try {
    const v: unknown = JSON.parse(text);
    return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function AssetsPage() {
  const { t } = useTranslation();
  const isAdmin = useRole() === "luda_admin";
  const qc = useQueryClient();
  const [type, setType] = useState("");
  const [form, setForm] = useState({ asset_type: "rule_pack", asset_key: "", title: "", payload: "{}" });
  const [jsonError, setJsonError] = useState(false);
  const { data } = useQuery({
    queryKey: ["assets", type],
    queryFn: () => api<AssetSummary[]>("/assets", { query: { asset_type: type } }),
  });
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api<Asset>("/assets", { method: "POST", body: { ...form, payload } }),
    onSuccess: () => {
      setForm({ ...form, asset_key: "", title: "", payload: "{}" });
      void qc.invalidateQueries({ queryKey: ["assets"] });
    },
  });
  const importPkg = useMutation({
    mutationFn: async (file: File) => api("/assets/import", { method: "POST", body: JSON.parse(await file.text()) }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["assets"] }),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const payload = parseJson(form.payload);
    setJsonError(!payload);
    if (payload) create.mutate(payload);
  };
  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.assets")}
        actions={
          <>
            <a className="btn" href="/api/v1/assets/export">
              {t("assets.exportPackage")}
            </a>
            {isAdmin && (
              <label className="btn cursor-pointer">
                {t("assets.importPackage")}
                <input
                  type="file"
                  accept="application/json"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) importPkg.mutate(f);
                    e.target.value = "";
                  }}
                />
              </label>
            )}
          </>
        }
      />
      <ErrorText error={importPkg.error} />
      <div className="w-64">
        <Select value={type} onChange={setType} options={ASSET_TYPES} group="assetType" allowEmpty ariaLabel={t("assets.type")} />
      </div>
      {isAdmin && (
        <form onSubmit={submit} className="card grid grid-cols-4 items-end gap-3">
          <Field label={t("assets.type")}>
            <Select value={form.asset_type} onChange={(v) => setForm({ ...form, asset_type: v })} options={ASSET_TYPES} group="assetType" />
          </Field>
          <Field label={t("assets.key")}>
            <input className="input" value={form.asset_key} onChange={(e) => setForm({ ...form, asset_key: e.target.value })} required />
          </Field>
          <Field label={t("common.title")}>
            <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </Field>
          <button className="btn btn-primary w-fit">{t("common.create")}</button>
          <div className="col-span-4">
            <Field label={t("assets.payload")}>
              <textarea
                className="input h-24 font-mono text-xs"
                value={form.payload}
                onChange={(e) => setForm({ ...form, payload: e.target.value })}
              />
            </Field>
            {jsonError && <p className="text-sm text-red-700">{t("errors.invalid_json")}</p>}
            <ErrorText error={create.error} />
          </div>
        </form>
      )}
      <div className="card">
        {!data?.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.title")}</th>
                <th>{t("assets.type")}</th>
                <th>{t("assets.key")}</th>
                <th>{t("assets.latest")}</th>
                <th>{t("common.status")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.asset_id}>
                  <td>
                    <Link className="text-blue-700 hover:underline" to={`/assets/${a.asset_id}`}>
                      {a.title}
                    </Link>
                  </td>
                  <td>{t(`assetType.${a.asset_type}`)}</td>
                  <td className="font-mono text-xs">{a.asset_key}</td>
                  <td>v{a.latest_version}</td>
                  <td>
                    <StatusBadge group="assetStatus" value={a.latest_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function DiffView({ text }: { text: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
      {text.split("\n").map((line, i) => (
        <div
          key={i}
          className={line.startsWith("+") ? "text-green-300" : line.startsWith("-") ? "text-red-300" : undefined}
        >
          {line || " "}
        </div>
      ))}
    </pre>
  );
}

export function AssetDiffPanel({ assetId, versions }: { assetId: string; versions: number[] }) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState<{ from?: number; to?: number }>({});
  const from = picked.from ?? versions[versions.length - 2] ?? versions[0] ?? 1;
  const to = picked.to ?? versions[versions.length - 1] ?? 1;
  const { data } = useQuery({
    queryKey: ["asset-diff", assetId, from, to],
    queryFn: () => api<AssetDiff>(`/assets/${assetId}/diff`, { query: { from_version: from, to_version: to } }),
    enabled: versions.length > 1,
  });
  if (versions.length < 2) return null;
  const opts = versions.map(String);
  return (
    <section className="card space-y-2">
      <div className="flex items-center gap-2">
        <h2 className="font-semibold">{t("assets.diff")}</h2>
        <div className="w-24">
          <Select value={String(from)} onChange={(v) => setPicked({ ...picked, from: Number(v) })} options={opts} group="version" ariaLabel={t("assets.from")} />
        </div>
        →
        <div className="w-24">
          <Select value={String(to)} onChange={(v) => setPicked({ ...picked, to: Number(v) })} options={opts} group="version" ariaLabel={t("assets.to")} />
        </div>
      </div>
      {data?.prompt_diff && (
        <>
          <h3 className="label">{t("assets.promptDiff")}</h3>
          <DiffView text={data.prompt_diff} />
        </>
      )}
      {data && (
        <>
          <h3 className="label">{t("assets.payloadDiff")}</h3>
          <DiffView text={data.payload_diff} />
        </>
      )}
    </section>
  );
}

export function NewVersionForm({ asset, onDone }: { asset: Asset; onDone: () => void }) {
  const { t } = useTranslation();
  const [payload, setPayload] = useState(JSON.stringify(asset.payload, null, 2));
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("draft");
  const [jsonError, setJsonError] = useState(false);
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Asset>(`/assets/${asset.asset_id}/versions`, {
        method: "POST",
        body: { payload: body, change_note: note, status },
      }),
    onSuccess: onDone,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const body = parseJson(payload);
    setJsonError(!body);
    if (body) create.mutate(body);
  };
  return (
    <form onSubmit={submit} className="card space-y-2">
      <h2 className="font-semibold">{t("assets.newVersion")}</h2>
      <textarea className="input h-64 font-mono text-xs" value={payload} onChange={(e) => setPayload(e.target.value)} aria-label={t("assets.payload")} />
      {jsonError && <p className="text-sm text-red-700">{t("errors.invalid_json")}</p>}
      <div className="grid grid-cols-3 items-end gap-3">
        <Field label={t("assets.changeNote")}>
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)} required />
        </Field>
        <Field label={t("common.status")}>
          <Select value={status} onChange={setStatus} options={ASSET_STATUSES} group="assetStatus" />
        </Field>
        <button className="btn btn-primary w-fit">{t("common.save")}</button>
      </div>
      <ErrorText error={create.error} />
    </form>
  );
}

export function AssetDetailPage() {
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
  return (
    <div className="space-y-4">
      <PageHeader title={`${latest.title} (${t(`assetType.${latest.asset_type}`)})`} />
      <section className="card">
        <table className="table">
          <thead>
            <tr>
              <th>{t("assets.version")}</th>
              <th>{t("common.status")}</th>
              <th>{t("assets.changeNote")}</th>
              <th>{t("common.createdAt")}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((v) => (
              <tr key={v.version} className={v.version === current.version ? "bg-blue-50" : undefined}>
                <td>
                  <button className="text-blue-700 hover:underline" onClick={() => setSelected(v.version)}>
                    v{v.version}
                  </button>
                </td>
                <td>
                  <StatusBadge group="assetStatus" value={v.status} />
                </td>
                <td>{v.change_note}</td>
                <td>{new Date(v.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="card">
        <h2 className="mb-2 font-semibold">
          {t("assets.payload")} v{current.version}
        </h2>
        <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(current.payload, null, 2)}</pre>
      </section>
      <AssetDiffPanel assetId={latest.asset_id} versions={data.map((v) => v.version)} />
      {isAdmin && (
        <NewVersionForm asset={latest} onDone={() => void qc.invalidateQueries({ queryKey: ["asset", assetId] })} />
      )}
      {!data.length && <Empty />}
    </div>
  );
}
