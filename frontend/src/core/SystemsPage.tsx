import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../api/client";
import type { Page, System } from "../api/types";
import { Empty, ErrorText, Field, NeedTenant, PageHeader, Select } from "../components/ui";
import { useCanWrite, useTenantId } from "../app/hooks";

const TYPES = ["MES", "ERP", "LIMS", "WMS", "SCADA", "GROUPWARE", "OTHER"] as const;
const HOSTING = ["on_premise", "cloud"] as const;
const EMPTY = { name: "", short_name: "", type: "OTHER", owner_dept: "", hosting: "", db_type: "", notes: "" };

export function SystemsPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const key = ["systems", tenantId];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () => api<Page<System>>(tenantPath(tenantId, "/systems"), { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
  const create = useMutation({
    mutationFn: () =>
      api<System>(tenantPath(tenantId, "/systems"), {
        method: "POST",
        body: Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v])),
      }),
    onSuccess: () => {
      setForm(EMPTY);
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api<unknown>(tenantPath(tenantId, `/systems/${id}`), { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: key }),
  });
  if (!tenantId) return <NeedTenant />;
  const set = (k: keyof typeof EMPTY) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.systems")} />
      {canWrite && (
        <form onSubmit={submit} className="card grid grid-cols-4 items-end gap-3">
          <Field label={t("common.name")}>
            <input className="input" value={form.name} onChange={(e) => set("name")(e.target.value)} required />
          </Field>
          <Field label={t("systems.shortName")}>
            <input className="input" value={form.short_name} onChange={(e) => set("short_name")(e.target.value)} />
          </Field>
          <Field label={t("systems.type")}>
            <Select value={form.type} onChange={set("type")} options={TYPES} group="systemType" />
          </Field>
          <Field label={t("systems.ownerDept")}>
            <input className="input" value={form.owner_dept} onChange={(e) => set("owner_dept")(e.target.value)} />
          </Field>
          <Field label={t("systems.hosting")}>
            <Select value={form.hosting} onChange={set("hosting")} options={HOSTING} group="hosting" allowEmpty />
          </Field>
          <Field label={t("systems.dbType")}>
            <input className="input" value={form.db_type} onChange={(e) => set("db_type")(e.target.value)} />
          </Field>
          <Field label={t("common.notes")}>
            <input className="input" value={form.notes} onChange={(e) => set("notes")(e.target.value)} />
          </Field>
          <button className="btn btn-primary w-fit">{t("common.create")}</button>
          <ErrorText error={create.error} />
        </form>
      )}
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.name")}</th>
                <th>{t("systems.shortName")}</th>
                <th>{t("systems.type")}</th>
                <th>{t("systems.ownerDept")}</th>
                <th>{t("systems.hosting")}</th>
                <th>{t("systems.dbType")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.short_name}</td>
                  <td>{t(`systemType.${s.type}`)}</td>
                  <td>{s.owner_dept}</td>
                  <td>{s.hosting && t(`hosting.${s.hosting}`)}</td>
                  <td>{s.db_type}</td>
                  <td className="text-right">
                    {canWrite && (
                      <button className="btn btn-danger" onClick={() => remove.mutate(s.id)}>
                        {t("common.delete")}
                      </button>
                    )}
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
