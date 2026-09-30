import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, tenantPath } from "../../api/client";
import type { Engagement, Page, Project } from "../../api/types";
import { Empty, ErrorText, Field, NeedTenant, PageHeader, StatusBadge } from "../../components/ui";
import { useCanWrite, useTenantId } from "../../app/hooks";
import { useWorkspace } from "../../app/store";

export function ProjectsPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const engagementId = useWorkspace((s) => s.engagementId);
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", engagement_id: "", stack: "", description: "" });
  const key = ["projects", tenantId, engagementId];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () =>
      api<Page<Project>>(tenantPath(tenantId, "/devtracker/projects"), {
        query: { limit: 200, engagement_id: engagementId },
      }),
    enabled: !!tenantId,
  });
  const { data: engagements } = useQuery({
    queryKey: ["engagements", tenantId],
    queryFn: () => api<Page<Engagement>>(tenantPath(tenantId, "/engagements"), { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
  const create = useMutation({
    mutationFn: () =>
      api<Project>(tenantPath(tenantId, "/devtracker/projects"), {
        method: "POST",
        body: { ...form, engagement_id: form.engagement_id || engagementId },
      }),
    onSuccess: () => {
      setForm({ name: "", engagement_id: "", stack: "", description: "" });
      void qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  if (!tenantId) return <NeedTenant />;
  const engName = (id: string) => engagements?.items.find((e) => e.id === id)?.name ?? "";
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="space-y-4">
      <PageHeader title={`${t("nav.devtracker")} · ${t("devtracker.projects")}`} />
      {canWrite && (
        <form onSubmit={submit} className="card grid grid-cols-5 items-end gap-3">
          <Field label={t("nav.engagements")}>
            <select
              className="input"
              value={form.engagement_id || engagementId || ""}
              onChange={(e) => setForm({ ...form, engagement_id: e.target.value })}
              required
            >
              <option value="">{t("common.none")}</option>
              {engagements?.items.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("common.name")}>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label={t("devtracker.stack")}>
            <input className="input" value={form.stack} onChange={(e) => setForm({ ...form, stack: e.target.value })} />
          </Field>
          <Field label={t("common.description")}>
            <input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
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
                <th>{t("nav.engagements")}</th>
                <th>{t("common.status")}</th>
                <th>{t("devtracker.stack")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link className="text-blue-700 hover:underline" to={`/devtracker/projects/${p.id}`}>
                      {p.name}
                    </Link>
                  </td>
                  <td>{engName(p.engagement_id)}</td>
                  <td>
                    <StatusBadge group="projectStatus" value={p.status} />
                  </td>
                  <td>{p.stack}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
