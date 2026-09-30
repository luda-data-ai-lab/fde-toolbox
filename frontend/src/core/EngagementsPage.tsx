import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../api/client";
import type { Engagement, Page } from "../api/types";
import { Empty, ErrorText, Field, NeedTenant, PageHeader, Select } from "../components/ui";
import { useCanWrite, useTenantId } from "../app/hooks";

const ENGAGEMENT_STATUSES = ["preparing", "in_progress", "on_hold", "completed"] as const;

export function EngagementsPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const key = ["engagements", tenantId];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () => api<Page<Engagement>>(tenantPath(tenantId, "/engagements"), { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
  const create = useMutation({
    mutationFn: () =>
      api<Engagement>(tenantPath(tenantId, "/engagements"), { method: "POST", body: { name, description } }),
    onSuccess: () => {
      setName("");
      setDescription("");
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api<Engagement>(tenantPath(tenantId, `/engagements/${id}`), { method: "PATCH", body: { status } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: key }),
  });
  if (!tenantId) return <NeedTenant />;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.engagements")} />
      {canWrite && (
        <form onSubmit={submit} className="card grid grid-cols-3 items-end gap-3">
          <Field label={t("common.name")}>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <Field label={t("common.description")}>
            <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
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
                <th>{t("common.status")}</th>
                <th>{t("common.description")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id}>
                  <td>{e.name}</td>
                  <td className="w-44">
                    {canWrite ? (
                      <Select
                        value={e.status}
                        options={ENGAGEMENT_STATUSES}
                        group="engagementStatus"
                        onChange={(status) => update.mutate({ id: e.id, status })}
                        ariaLabel={t("common.status")}
                      />
                    ) : (
                      t(`engagementStatus.${e.status}`)
                    )}
                  </td>
                  <td>{e.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
