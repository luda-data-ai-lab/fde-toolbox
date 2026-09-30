import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Page, Tenant } from "../api/types";
import { Empty, ErrorText, Field, PageHeader, StatusBadge } from "../components/ui";

export function TenantsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", code: "" });
  const [importCode, setImportCode] = useState("");
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["tenants"] });
    void qc.invalidateQueries({ queryKey: ["me"] });
  };
  const { data } = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api<Page<Tenant>>("/admin/tenants", { query: { limit: 200 } }),
  });
  const create = useMutation({
    mutationFn: () => api<Tenant>("/admin/tenants", { method: "POST", body: form }),
    onSuccess: () => {
      setForm({ name: "", code: "" });
      refresh();
    },
  });
  const archive = useMutation({
    mutationFn: (x: Tenant) =>
      api<Tenant>(`/admin/tenants/${x.id}`, {
        method: "PATCH",
        body: { status: x.status === "active" ? "archived" : "active" },
      }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api<unknown>(`/admin/tenants/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  const importZip = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      body.append("code", importCode);
      return api<Tenant>("/admin/tenants/import", { method: "POST", body });
    },
    onSuccess: () => {
      setImportCode("");
      refresh();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.tenants")} />
      <form onSubmit={submit} className="card grid grid-cols-3 items-end gap-3">
        <Field label={t("common.name")}>
          <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        </Field>
        <Field label={t("tenants.code")}>
          <input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
        </Field>
        <button className="btn btn-primary w-fit">{t("common.create")}</button>
        <ErrorText error={create.error} />
      </form>
      <div className="card flex items-end gap-3">
        <Field label={t("tenants.importCode")}>
          <input className="input" value={importCode} onChange={(e) => setImportCode(e.target.value)} />
        </Field>
        <label className={`btn ${importCode ? "cursor-pointer" : "pointer-events-none opacity-50"}`}>
          {t("tenants.importZip")}
          <input
            type="file"
            accept=".zip"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) importZip.mutate(f);
              e.target.value = "";
            }}
          />
        </label>
        <ErrorText error={importZip.error} />
      </div>
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.name")}</th>
                <th>{t("tenants.code")}</th>
                <th>{t("common.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((x) => (
                <tr key={x.id}>
                  <td>{x.name}</td>
                  <td className="font-mono text-xs">{x.code}</td>
                  <td>
                    <StatusBadge group="tenantStatus" value={x.status} />
                  </td>
                  <td className="space-x-2 text-right">
                    <a className="btn" href={`/api/v1/t/${x.id}/export`}>
                      {t("tenants.export")}
                    </a>
                    <button className="btn" onClick={() => archive.mutate(x)}>
                      {x.status === "active" ? t("tenants.archive") : t("tenants.restore")}
                    </button>
                    <button
                      className="btn btn-danger"
                      onClick={() => {
                        if (window.confirm(t("tenants.confirmDelete", { name: x.name }))) remove.mutate(x.id);
                      }}
                    >
                      {t("common.delete")}
                    </button>
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
