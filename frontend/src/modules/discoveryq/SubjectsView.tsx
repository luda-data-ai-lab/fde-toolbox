import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { DiscoverySubject } from "../../api/types";
import { Empty, ErrorText, Field } from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import { useSystems } from "../interfaces/shared";
import { EngagementSelect } from "./EngagementSelect";
import {
  discoveryKeys,
  discoveryPath,
  useEngagements,
  useSubjects,
} from "./shared";

const EMPTY = {
  engagement_id: "",
  name: "",
  department: "",
  job_title: "",
  system_ids: [] as string[],
};

export function SubjectsView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const engagementId = useWorkspace((s) => s.engagementId);
  const qc = useQueryClient();
  const { data } = useSubjects(tenantId, engagementId);
  const systems = useSystems(tenantId).data?.items ?? [];
  const engagements = useEngagements(tenantId).data?.items ?? [];
  const [form, setForm] = useState(EMPTY);
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: discoveryKeys(tenantId).all });
  const create = useMutation({
    mutationFn: () =>
      api<DiscoverySubject>(discoveryPath(tenantId, "/subjects"), {
        method: "POST",
        body: {
          ...form,
          engagement_id: form.engagement_id || engagementId,
          department: form.department || null,
          job_title: form.job_title || null,
        },
      }),
    onSuccess: () => {
      setForm(EMPTY);
      void invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api(discoveryPath(tenantId, `/subjects/${id}`), { method: "DELETE" }),
    onSuccess: () => void invalidate(),
  });
  const systemName = new Map(systems.map((s) => [s.id, s.name]));
  const engName = new Map(engagements.map((e) => [e.id, e.name]));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="space-y-3">
      {canWrite && (
        <form
          className="card grid grid-cols-2 gap-3 md:grid-cols-5"
          onSubmit={submit}
          aria-label={t("discoveryq.subject.new")}
        >
          <EngagementSelect
            tenantId={tenantId}
            value={form.engagement_id}
            onChange={(v) => setForm({ ...form, engagement_id: v })}
          />
          <Field label={t("discoveryq.field.subjectName")}>
            <input
              className="input"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field label={t("discoveryq.field.department")}>
            <input
              className="input"
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
            />
          </Field>
          <Field label={t("discoveryq.field.jobTitle")}>
            <input
              className="input"
              value={form.job_title}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
            />
          </Field>
          <Field label={t("discoveryq.field.systems")}>
            <select
              className="input"
              multiple
              value={form.system_ids}
              onChange={(e) =>
                setForm({
                  ...form,
                  system_ids: Array.from(
                    e.target.selectedOptions,
                    (o) => o.value,
                  ),
                })
              }
            >
              {systems.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="col-span-full flex items-center gap-2">
            <button className="btn btn-primary" type="submit">
              {t("common.create")}
            </button>
            <ErrorText error={create.error} />
          </div>
        </form>
      )}
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table" data-testid="subject-table">
            <thead>
              <tr>
                <th>{t("discoveryq.field.subjectName")}</th>
                <th>{t("discoveryq.field.department")}</th>
                <th>{t("discoveryq.field.jobTitle")}</th>
                <th>{t("discoveryq.field.systems")}</th>
                <th>{t("nav.engagements")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.department}</td>
                  <td>{s.job_title}</td>
                  <td>
                    {s.system_ids
                      .map((id) => systemName.get(id) ?? id)
                      .join(", ")}
                  </td>
                  <td>{engName.get(s.engagement_id)}</td>
                  <td className="text-right">
                    {canWrite && (
                      <button
                        className="btn btn-danger"
                        onClick={() => remove.mutate(s.id)}
                      >
                        {t("common.delete")}
                      </button>
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
