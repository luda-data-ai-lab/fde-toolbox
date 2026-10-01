import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { api, tenantPath } from "../../api/client";
import type { Interface, Page } from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  NeedTenant,
  PageHeader,
  Select,
  StatusBadge,
} from "../../components/ui";
import {
  AUDIT_ROLES,
  useCanWrite,
  useRole,
  useTenantId,
} from "../../app/hooks";
import { IF_STATUSES, LINK_TYPES, ifKeys, useSystems } from "./shared";
import { UploadPanel } from "./UploadPanel";
import { InterfaceDashboardView } from "./InterfaceDashboardView";
import { InterfaceGraphView } from "./InterfaceGraphView";

const TABS = ["list", "upload", "dashboard", "graph"] as const;
type Tab = (typeof TABS)[number];
const EMPTY = {
  if_code: "",
  name: "",
  source_system_id: "",
  target_system_id: "",
  link_type: "other",
  schedule: "",
  description: "",
  daily_volume: "",
  owner: "",
  status: "operating",
  notes: "",
};
type FormState = typeof EMPTY;

function toForm(i: Interface): FormState {
  return {
    if_code: i.if_code,
    name: i.name,
    source_system_id: i.source_system_id,
    target_system_id: i.target_system_id,
    link_type: i.link_type,
    schedule: i.schedule ?? "",
    description: i.description ?? "",
    daily_volume: i.daily_volume === null ? "" : String(i.daily_volume),
    owner: i.owner ?? "",
    status: i.status,
    notes: i.notes ?? "",
  };
}

function toBody(f: FormState): Record<string, unknown> {
  const body: Record<string, unknown> = Object.fromEntries(
    Object.entries(f).map(([k, v]) => [k, v === "" ? null : v]),
  );
  body.daily_volume = f.daily_volume === "" ? null : Number(f.daily_volume);
  return body;
}

function InterfaceForm({
  tenantId,
  editing,
  onDone,
}: {
  tenantId: string;
  editing: Interface | null;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const systems = useSystems(tenantId).data?.items ?? [];
  const [form, setForm] = useState<FormState>(
    editing ? toForm(editing) : EMPTY,
  );
  const save = useMutation({
    mutationFn: () =>
      editing
        ? api<Interface>(tenantPath(tenantId, `/interfaces/${editing.id}`), {
            method: "PATCH",
            body: toBody(form),
          })
        : api<Interface>(tenantPath(tenantId, "/interfaces"), {
            method: "POST",
            body: toBody(form),
          }),
    onSuccess: () => {
      setForm(EMPTY);
      onDone();
    },
  });
  const set = (k: keyof FormState) => (v: string) =>
    setForm((f) => ({ ...f, [k]: v }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const systemSelect = (
    k: "source_system_id" | "target_system_id",
    label: string,
  ) => (
    <Field label={label}>
      <select
        className="input"
        value={form[k]}
        onChange={(e) => set(k)(e.target.value)}
        required
      >
        <option value="">{t("common.none")}</option>
        {systems.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </Field>
  );
  return (
    <form
      onSubmit={submit}
      className="card grid grid-cols-4 items-end gap-3"
      data-testid="interface-form"
    >
      <Field label={t("ifField.if_code")}>
        <input
          className="input"
          value={form.if_code}
          onChange={(e) => set("if_code")(e.target.value)}
          required
        />
      </Field>
      <Field label={t("ifField.name")}>
        <input
          className="input"
          value={form.name}
          onChange={(e) => set("name")(e.target.value)}
          required
        />
      </Field>
      {systemSelect("source_system_id", t("ifField.source"))}
      {systemSelect("target_system_id", t("ifField.target"))}
      <Field label={t("ifField.link_type")}>
        <Select
          value={form.link_type}
          onChange={set("link_type")}
          options={LINK_TYPES}
          group="linkType"
        />
      </Field>
      <Field label={t("ifField.schedule")}>
        <input
          className="input"
          value={form.schedule}
          onChange={(e) => set("schedule")(e.target.value)}
        />
      </Field>
      <Field label={t("ifField.daily_volume")}>
        <input
          className="input"
          type="number"
          min={0}
          value={form.daily_volume}
          onChange={(e) => set("daily_volume")(e.target.value)}
        />
      </Field>
      <Field label={t("ifField.owner")}>
        <input
          className="input"
          value={form.owner}
          onChange={(e) => set("owner")(e.target.value)}
        />
      </Field>
      <Field label={t("ifField.status")}>
        <Select
          value={form.status}
          onChange={set("status")}
          options={IF_STATUSES}
          group="ifStatus"
        />
      </Field>
      <Field label={t("ifField.description")}>
        <input
          className="input"
          value={form.description}
          onChange={(e) => set("description")(e.target.value)}
        />
      </Field>
      <Field label={t("ifField.notes")}>
        <input
          className="input"
          value={form.notes}
          onChange={(e) => set("notes")(e.target.value)}
        />
      </Field>
      <div className="flex gap-2">
        <button className="btn btn-primary">
          {editing ? t("common.save") : t("common.create")}
        </button>
        {editing && (
          <button type="button" className="btn" onClick={onDone}>
            {t("common.cancel")}
          </button>
        )}
      </div>
      <ErrorText error={save.error} />
    </form>
  );
}

function InterfaceList({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const keys = ifKeys(tenantId);
  const systems = useSystems(tenantId).data?.items ?? [];
  const names = new Map(systems.map((s) => [s.id, s.name]));
  const [filters, setFilters] = useState({
    system_id: "",
    link_type: "",
    status: "",
    q: "",
  });
  const [editing, setEditing] = useState<Interface | null>(null);
  const { data } = useQuery({
    queryKey: keys.list(filters),
    queryFn: () =>
      api<Page<Interface>>(tenantPath(tenantId, "/interfaces"), {
        query: { ...filters, limit: 200 },
      }),
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.all });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api<unknown>(tenantPath(tenantId, `/interfaces/${id}`), {
        method: "DELETE",
      }),
    onSuccess: refresh,
  });
  const setFilter = (k: keyof typeof filters) => (v: string) =>
    setFilters((f) => ({ ...f, [k]: v }));
  return (
    <div className="space-y-4">
      {canWrite && (
        <InterfaceForm
          key={editing?.id ?? "new"}
          tenantId={tenantId}
          editing={editing}
          onDone={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
      <div className="card grid grid-cols-4 gap-3">
        <Field label={t("common.search")}>
          <input
            className="input"
            value={filters.q}
            onChange={(e) => setFilter("q")(e.target.value)}
          />
        </Field>
        <Field label={t("interfaces.system")}>
          <select
            className="input"
            value={filters.system_id}
            onChange={(e) => setFilter("system_id")(e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {systems.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("ifField.link_type")}>
          <Select
            value={filters.link_type}
            onChange={setFilter("link_type")}
            options={LINK_TYPES}
            group="linkType"
            allowEmpty
          />
        </Field>
        <Field label={t("ifField.status")}>
          <Select
            value={filters.status}
            onChange={setFilter("status")}
            options={IF_STATUSES}
            group="ifStatus"
            allowEmpty
          />
        </Field>
      </div>
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table" data-testid="interface-table">
            <thead>
              <tr>
                <th>{t("ifField.if_code")}</th>
                <th>{t("ifField.name")}</th>
                <th>{t("ifField.source")}</th>
                <th>{t("ifField.target")}</th>
                <th>{t("ifField.link_type")}</th>
                <th>{t("ifField.schedule")}</th>
                <th>{t("ifField.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td className="font-mono text-xs">{i.if_code}</td>
                  <td>{i.name}</td>
                  <td>{names.get(i.source_system_id)}</td>
                  <td>{names.get(i.target_system_id)}</td>
                  <td>
                    <StatusBadge group="linkType" value={i.link_type} />
                  </td>
                  <td>{i.schedule}</td>
                  <td>
                    <StatusBadge group="ifStatus" value={i.status} />
                  </td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    {canWrite && (
                      <>
                        <button className="btn" onClick={() => setEditing(i)}>
                          {t("common.edit")}
                        </button>
                        <button
                          className="btn btn-danger"
                          onClick={() => remove.mutate(i.id)}
                        >
                          {t("common.delete")}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <ErrorText error={remove.error} />
      </div>
    </div>
  );
}

export function InterfacesPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const role = useRole();
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : "list";
  if (!tenantId) return <NeedTenant />;
  const base = `/api/v1/t/${tenantId}/interfaces`;
  const tabs = TABS.filter((x) => x !== "upload" || canWrite);
  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.interfaces")}
        actions={
          <>
            <a className="btn" href={`${base}/template.xlsx`}>
              {t("interfaces.template")}
            </a>
            {role && AUDIT_ROLES.includes(role) && (
              <>
                <a className="btn" href={`${base}/export.xlsx`}>
                  {t("interfaces.exportXlsx")}
                </a>
                <a className="btn" href={`${base}/export.csv`}>
                  {t("interfaces.exportCsv")}
                </a>
              </>
            )}
          </>
        }
      />
      <div role="tablist" className="flex gap-1 border-b border-slate-200">
        {tabs.map((x) => (
          <button
            key={x}
            role="tab"
            aria-selected={tab === x}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === x ? "border-blue-700 font-semibold text-blue-800" : "border-transparent text-slate-600"}`}
            onClick={() => setParams({ tab: x })}
          >
            {t(`interfaces.tab.${x}`)}
          </button>
        ))}
      </div>
      {tab === "list" && <InterfaceList tenantId={tenantId} />}
      {tab === "upload" && canWrite && <UploadPanel tenantId={tenantId} />}
      {tab === "dashboard" && <InterfaceDashboardView tenantId={tenantId} />}
      {tab === "graph" && <InterfaceGraphView tenantId={tenantId} />}
    </div>
  );
}
