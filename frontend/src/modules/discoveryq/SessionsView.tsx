import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { DiscoverySession, Page } from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  Select,
  StatusBadge,
} from "../../components/ui";
import { AUDIT_ROLES, useCanWrite, useRole } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import { EngagementSelect } from "./EngagementSelect";
import {
  SESSION_TYPES,
  discoveryKeys,
  discoveryPath,
  useSubjects,
} from "./shared";

const EMPTY = {
  engagement_id: "",
  type: "interview",
  subject_id: "",
  title: "",
  session_date: "",
};

export function SessionsView({
  tenantId,
  onOpen,
}: {
  tenantId: string;
  onOpen: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const canWrite = useCanWrite();
  const role = useRole();
  const lang = i18n.language.startsWith("en") ? "en" : "ko";
  const engagementId = useWorkspace((s) => s.engagementId);
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ type: "", q: "" });
  const [form, setForm] = useState(EMPTY);
  const formEngagement = form.engagement_id || engagementId;
  const subjects = useSubjects(tenantId, formEngagement).data?.items ?? [];
  const allSubjects = useSubjects(tenantId, engagementId).data?.items ?? [];
  const subjectName = new Map(allSubjects.map((s) => [s.id, s.name]));
  const { data } = useQuery({
    queryKey: discoveryKeys(tenantId).sessions({ ...filters, engagementId }),
    queryFn: () =>
      api<Page<DiscoverySession>>(discoveryPath(tenantId, "/sessions"), {
        query: { limit: 200, engagement_id: engagementId, ...filters },
      }),
  });
  const create = useMutation({
    mutationFn: () =>
      api<DiscoverySession>(discoveryPath(tenantId, "/sessions"), {
        method: "POST",
        body: {
          ...form,
          engagement_id: formEngagement,
          subject_id: form.subject_id || null,
          session_date: form.session_date || null,
        },
      }),
    onSuccess: (s) => {
      setForm(EMPTY);
      void qc.invalidateQueries({ queryKey: discoveryKeys(tenantId).all });
      onOpen(s.id);
    },
  });
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
          aria-label={t("discoveryq.session.new")}
        >
          <EngagementSelect
            tenantId={tenantId}
            value={form.engagement_id}
            onChange={(v) =>
              setForm({ ...form, engagement_id: v, subject_id: "" })
            }
          />
          <Field label={t("discoveryq.field.type")}>
            <Select
              value={form.type}
              onChange={(v) => setForm({ ...form, type: v })}
              options={SESSION_TYPES}
              group="sessionType"
            />
          </Field>
          <Field
            label={
              form.type === "coaching"
                ? t("discoveryq.field.mentee")
                : t("discoveryq.field.subject")
            }
          >
            <select
              className="input"
              value={form.subject_id}
              onChange={(e) => setForm({ ...form, subject_id: e.target.value })}
            >
              <option value="">{t("common.none")}</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("common.title")}>
            <input
              className="input"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </Field>
          <Field label={t("discoveryq.field.date")}>
            <input
              className="input"
              type="date"
              value={form.session_date}
              onChange={(e) =>
                setForm({ ...form, session_date: e.target.value })
              }
            />
          </Field>
          <div className="col-span-full flex items-center gap-2">
            <button className="btn btn-primary" type="submit">
              {t("common.create")}
            </button>
            <ErrorText error={create.error} />
          </div>
        </form>
      )}
      <div className="card grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label={t("discoveryq.field.type")}>
          <Select
            value={filters.type}
            onChange={(v) => setFilters({ ...filters, type: v })}
            options={SESSION_TYPES}
            group="sessionType"
            allowEmpty
          />
        </Field>
        <Field label={t("common.search")}>
          <input
            className="input"
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
          />
        </Field>
        {engagementId && role && AUDIT_ROLES.includes(role) && (
          <div className="col-span-full flex justify-end md:col-span-2 md:items-end">
            <a
              className="btn"
              href={`/api/v1/t/${tenantId}/discoveryq/engagements/${engagementId}/report.docx?lang=${lang}`}
            >
              {t("discoveryq.engagementReport")}
            </a>
          </div>
        )}
      </div>
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table" data-testid="session-table">
            <thead>
              <tr>
                <th>{t("common.title")}</th>
                <th>{t("discoveryq.field.type")}</th>
                <th>{t("discoveryq.field.subject")}</th>
                <th>{t("discoveryq.field.date")}</th>
                <th>{t("common.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr key={s.id}>
                  <td>{s.title}</td>
                  <td>
                    <StatusBadge group="sessionType" value={s.type} />
                  </td>
                  <td>{s.subject_id ? subjectName.get(s.subject_id) : ""}</td>
                  <td>{s.session_date}</td>
                  <td>
                    <StatusBadge
                      group="discoverySessionStatus"
                      value={s.status}
                    />
                  </td>
                  <td className="text-right">
                    <button className="btn" onClick={() => onOpen(s.id)}>
                      {t("discoveryq.session.open")}
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
