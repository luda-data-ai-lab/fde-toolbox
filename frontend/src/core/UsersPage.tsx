import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Page, Role, Tenant, UserAdmin } from "../api/types";
import { Empty, ErrorText, Field, PageHeader, Select } from "../components/ui";

const ROLES: Role[] = ["luda_admin", "fde", "client_admin", "client_user"];
const EMPTY = { email: "", name: "", role: "fde" as Role, password: "", tenant: "" };

export function UsersPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: () => api<Page<UserAdmin>>("/admin/users", { query: { limit: 200 } }),
  });
  const { data: tenants } = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api<Page<Tenant>>("/admin/tenants", { query: { limit: 200 } }),
  });
  const tenantName = (id: string | null) => tenants?.items.find((x) => x.id === id)?.name ?? "";
  const create = useMutation({
    mutationFn: () => {
      const isClient = form.role === "client_admin" || form.role === "client_user";
      return api<UserAdmin>("/admin/users", {
        method: "POST",
        body: {
          email: form.email,
          name: form.name,
          role: form.role,
          password: form.password,
          home_tenant_id: isClient ? form.tenant || null : null,
          tenant_ids: form.role === "fde" && form.tenant ? [form.tenant] : [],
        },
      });
    },
    onSuccess: () => {
      setForm(EMPTY);
      void qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api<UserAdmin>(`/admin/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["users"] }),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  const tenantIds = tenants?.items.map((x) => x.id) ?? [];
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.users")} />
      <form onSubmit={submit} className="card grid grid-cols-6 items-end gap-3">
        <Field label={t("auth.email")}>
          <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        </Field>
        <Field label={t("common.name")}>
          <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        </Field>
        <Field label={t("users.role")}>
          <Select value={form.role} onChange={(v) => setForm({ ...form, role: v as Role })} options={ROLES} group="roles" />
        </Field>
        <Field label={t("users.tenant")}>
          <select className="input" value={form.tenant} onChange={(e) => setForm({ ...form, tenant: e.target.value })} disabled={form.role === "luda_admin"}>
            <option value="">{t("common.none")}</option>
            {tenants?.items.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("auth.password")}>
          <input className="input" type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </Field>
        <button className="btn btn-primary w-fit">{t("common.create")}</button>
        <div className="col-span-6">
          <ErrorText error={create.error ?? update.error} />
        </div>
      </form>
      <div className="card">
        {!users?.items.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("auth.email")}</th>
                <th>{t("common.name")}</th>
                <th>{t("users.role")}</th>
                <th>{t("users.tenants")}</th>
                <th>{t("common.status")}</th>
              </tr>
            </thead>
            <tbody>
              {users.items.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{u.name}</td>
                  <td>{t(`roles.${u.role}`)}</td>
                  <td>
                    {u.role === "fde" ? (
                      <div className="flex flex-wrap gap-2">
                        {tenantIds.map((tid) => (
                          <label key={tid} className="flex items-center gap-1 text-xs">
                            <input
                              type="checkbox"
                              checked={u.tenant_ids.includes(tid)}
                              onChange={(e) =>
                                update.mutate({
                                  id: u.id,
                                  body: {
                                    tenant_ids: e.target.checked
                                      ? [...u.tenant_ids, tid]
                                      : u.tenant_ids.filter((x) => x !== tid),
                                  },
                                })
                              }
                            />
                            {tenantName(tid)}
                          </label>
                        ))}
                      </div>
                    ) : (
                      tenantName(u.home_tenant_id)
                    )}
                  </td>
                  <td>
                    <button className="btn" onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                      {u.is_active ? t("users.active") : t("users.inactive")}
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
