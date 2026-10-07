import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../api/client";
import type { AdapterActivation, AdapterHealth, AdapterInfo, JsonScalar, Role } from "../api/types";
import { Empty, ErrorText, Field, NeedTenant, PageHeader, StatusBadge } from "../components/ui";
import { AUDIT_ROLES, WRITE_ROLES, useRole, useTenantId } from "../app/hooks";
import { fmtDate } from "../app/format";

const APPROVE_ROLES: Role[] = ["luda_admin", "client_admin"];

export function AdaptersPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const role = useRole();
  const { data } = useQuery({
    queryKey: ["adapters", tenantId],
    queryFn: () => api<AdapterInfo[]>(tenantPath(tenantId, "/adapters")),
    enabled: !!tenantId,
  });
  if (!tenantId) return <NeedTenant />;
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.adapters")} />
      <p className="text-sm text-slate-600">{t("adapters.intro")}</p>
      {!data?.length ? (
        <div className="card">
          <Empty />
        </div>
      ) : (
        data.map((a) => <AdapterCard key={a.key} adapter={a} role={role} tenantId={tenantId} />)
      )}
    </div>
  );
}

function AdapterCard({ adapter, role, tenantId }: { adapter: AdapterInfo; role: Role | undefined; tenantId: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const activation = adapter.activation;
  const status = activation?.status ?? "not_configured";
  const [form, setForm] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [ack, setAck] = useState(false);
  const [reason, setReason] = useState("");
  const [health, setHealth] = useState<AdapterHealth | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["adapters", tenantId] });
  const act = (path: string) => tenantPath(tenantId, `/adapters/activations/${activation?.id}${path}`);
  const request = useMutation({
    mutationFn: () => {
      const config: Record<string, JsonScalar> = {};
      const credentials: Record<string, string> = {};
      for (const f of adapter.config_fields) {
        const v = (form[f.name] ?? "").trim();
        if (!v) continue;
        if (f.kind === "secret") credentials[f.name] = v;
        else config[f.name] = f.kind === "int" ? Number(v) : v;
      }
      return api<AdapterActivation>(tenantPath(tenantId, "/adapters/activations"), {
        method: "POST",
        body: {
          adapter_key: adapter.key,
          config,
          credentials,
          note: note || null,
        },
      });
    },
    onSuccess: () => {
      setForm({});
      setNote("");
      refresh();
    },
  });
  const decide = useMutation({
    mutationFn: (action: "approve" | "reject" | "deactivate") =>
      api<AdapterActivation>(act(`/${action}`), {
        method: "POST",
        body: action === "approve" ? { acknowledged_egress: true, reason: reason || null } : { reason: reason || null },
      }),
    onSuccess: () => {
      setAck(false);
      setReason("");
      setHealth(null);
      refresh();
    },
  });
  const check = useMutation({
    mutationFn: () => api<AdapterHealth>(act("/health-check"), { method: "POST" }),
    onSuccess: setHealth,
  });
  const canRequest =
    adapter.implemented && !!role && WRITE_ROLES.includes(role) && status !== "requested" && status !== "active";
  const canApprove = status === "requested" && !!role && APPROVE_ROLES.includes(role);
  const canDeactivate = (status === "requested" || status === "active") && !!role && AUDIT_ROLES.includes(role);
  const notice = adapter.egress_notice;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    request.mutate();
  };
  return (
    <section className="card space-y-3" aria-label={adapter.display_name}>
      <div className="flex items-center gap-3">
        <h2 className="text-base font-semibold">{adapter.display_name}</h2>
        <StatusBadge group="adapterStatus" value={status} />
      </div>
      {!adapter.implemented && <p className="text-sm text-slate-500">{t("adapters.notImplemented")}</p>}
      <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm">
        <div className="mb-1 font-semibold">{t("adapters.egress")}</div>
        <dl className="grid grid-cols-[8rem_1fr] gap-1">
          <dt className="text-slate-500">{t("adapters.destination")}</dt>
          <dd className="font-mono">{notice.destination}</dd>
          <dt className="text-slate-500">{t("adapters.dataKinds")}</dt>
          <dd>{notice.data_kinds.map((k) => t(`adapters.data.${k}`, { defaultValue: k })).join(", ")}</dd>
          <dt className="text-slate-500">{t("adapters.features")}</dt>
          <dd>{notice.features.map((k) => t(`adapters.feature.${k}`, { defaultValue: k })).join(", ")}</dd>
        </dl>
      </div>
      {activation && (
        <dl className="grid grid-cols-[8rem_1fr] gap-1 text-sm">
          {Object.entries(activation.config).map(([k, v]) => (
            <Row key={k} label={t(`adapters.field.${k}`, { defaultValue: k })} value={String(v)} />
          ))}
          <Row label={t("adapters.requestedAt")} value={fmtDate(activation.requested_at)} />
          {activation.request_note && <Row label={t("adapters.note")} value={activation.request_note} />}
          {activation.approved_at && <Row label={t("adapters.approvedAt")} value={fmtDate(activation.approved_at)} />}
          {activation.approval_reason && (
            <Row label={t("adapters.approvalReason")} value={activation.approval_reason} />
          )}
          {activation.deactivated_at && (
            <Row label={t("adapters.deactivatedAt")} value={fmtDate(activation.deactivated_at)} />
          )}
        </dl>
      )}
      {activation && !activation.has_credentials && status === "disabled" && activation.approved_at && (
        <p className="text-sm text-amber-700">{t("adapters.credentialsMissing")}</p>
      )}
      {canRequest && (
        <form onSubmit={submit} className="grid grid-cols-4 items-end gap-3">
          {adapter.config_fields.map((f) => (
            <Field key={f.name} label={t(`adapters.field.${f.name}`, { defaultValue: f.name })}>
              <input
                className="input"
                type={f.kind === "secret" ? "password" : f.kind === "int" ? "number" : "text"}
                autoComplete="off"
                placeholder={f.default === null ? "" : String(f.default)}
                required={f.required}
                value={form[f.name] ?? ""}
                onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.value }))}
              />
            </Field>
          ))}
          <Field label={t("adapters.note")}>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <button className="btn btn-primary w-fit">{t("adapters.request")}</button>
          <ErrorText error={request.error} />
        </form>
      )}
      {(canApprove || canDeactivate) && (
        <div className="space-y-2 border-t border-slate-100 pt-3">
          {canApprove && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
              {t("adapters.acknowledge")}
            </label>
          )}
          <Field label={role === "luda_admin" && canApprove ? t("adapters.reasonRequired") : t("adapters.reason")}>
            <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
          <div className="flex gap-2">
            {canApprove && (
              <>
                <button className="btn btn-primary" disabled={!ack} onClick={() => decide.mutate("approve")}>
                  {t("adapters.approve")}
                </button>
                <button className="btn" onClick={() => decide.mutate("reject")}>
                  {t("adapters.reject")}
                </button>
              </>
            )}
            {canDeactivate && status === "active" && (
              <button className="btn btn-danger" onClick={() => decide.mutate("deactivate")}>
                {t("adapters.deactivate")}
              </button>
            )}
          </div>
          <ErrorText error={decide.error} />
        </div>
      )}
      {status === "active" && !!role && WRITE_ROLES.includes(role) && (
        <div className="flex items-center gap-3">
          <button className="btn" onClick={() => check.mutate()} disabled={check.isPending}>
            {t("adapters.healthCheck")}
          </button>
          {health && (
            <span className={`text-sm ${health.ok ? "text-green-700" : "text-red-700"}`}>
              {health.ok
                ? t("adapters.healthOk", { ms: health.latency_ms })
                : t("adapters.healthFail", { reason: health.message ?? "" })}
            </span>
          )}
          <ErrorText error={check.error} />
        </div>
      )}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
