import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type {
  DiscoveryActionItem,
  DiscoverySession,
  Page,
} from "../../api/types";
import { Empty, ErrorText, Field, Select } from "../../components/ui";
import { AUDIT_ROLES, useCanWrite, useRole } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import { ACTION_STATUSES, discoveryKeys, discoveryPath } from "./shared";

export function ActionItemRow({
  tenantId,
  item,
  sessionTitle,
}: {
  tenantId: string;
  item: DiscoveryActionItem;
  sessionTitle?: string;
}) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: discoveryKeys(tenantId).all });
  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<DiscoveryActionItem>(
        discoveryPath(tenantId, `/action-items/${item.id}`),
        {
          method: "PATCH",
          body,
        },
      ),
    onSuccess: () => void invalidate(),
  });
  const remove = useMutation({
    mutationFn: () =>
      api(discoveryPath(tenantId, `/action-items/${item.id}`), {
        method: "DELETE",
      }),
    onSuccess: () => void invalidate(),
  });
  return (
    <tr data-testid="action-row">
      {sessionTitle !== undefined && <td>{sessionTitle}</td>}
      <td>{item.title}</td>
      <td>{item.assignee}</td>
      <td>
        {canWrite ? (
          <input
            className="input"
            type="date"
            aria-label={t("discoveryq.field.due")}
            value={item.due ?? ""}
            onChange={(e) => patch.mutate({ due: e.target.value || null })}
          />
        ) : (
          item.due
        )}
      </td>
      <td>
        {canWrite ? (
          <Select
            value={item.status}
            onChange={(v) => patch.mutate({ status: v })}
            options={ACTION_STATUSES}
            group="actionStatus"
            ariaLabel={t("common.status")}
          />
        ) : (
          t(`actionStatus.${item.status}`)
        )}
        <ErrorText error={patch.error ?? remove.error} />
      </td>
      <td className="text-right">
        {canWrite && (
          <button className="btn btn-danger" onClick={() => remove.mutate()}>
            {t("common.delete")}
          </button>
        )}
      </td>
    </tr>
  );
}

export function ActionItemsView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const role = useRole();
  const engagementId = useWorkspace((s) => s.engagementId);
  const [status, setStatus] = useState("");
  const { data } = useQuery({
    queryKey: discoveryKeys(tenantId).actions({ status, engagementId }),
    queryFn: () =>
      api<Page<DiscoveryActionItem>>(discoveryPath(tenantId, "/action-items"), {
        query: { limit: 200, status, engagement_id: engagementId },
      }),
  });
  const sessions = useQuery({
    queryKey: discoveryKeys(tenantId).sessions({ all: true }),
    queryFn: () =>
      api<Page<DiscoverySession>>(discoveryPath(tenantId, "/sessions"), {
        query: { limit: 200 },
      }),
  }).data?.items;
  const title = new Map((sessions ?? []).map((s) => [s.id, s.title]));
  const exportUrl = new URL(
    `/api/v1/t/${tenantId}/discoveryq/action-items/export.csv`,
    window.location.origin,
  );
  if (status) exportUrl.searchParams.set("status", status);
  if (engagementId) exportUrl.searchParams.set("engagement_id", engagementId);
  return (
    <div className="space-y-3">
      <div className="card flex items-end justify-between gap-3">
        <div className="w-48">
          <Field label={t("common.status")}>
            <Select
              value={status}
              onChange={setStatus}
              options={ACTION_STATUSES}
              group="actionStatus"
              allowEmpty
            />
          </Field>
        </div>
        {role && AUDIT_ROLES.includes(role) && (
          <a className="btn" href={exportUrl.pathname + exportUrl.search}>
            {t("discoveryq.exportCsv")}
          </a>
        )}
      </div>
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("discoveryq.field.session")}</th>
                <th>{t("discoveryq.field.action")}</th>
                <th>{t("discoveryq.field.assignee")}</th>
                <th>{t("discoveryq.field.due")}</th>
                <th>{t("common.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((a) => (
                <ActionItemRow
                  key={a.id}
                  tenantId={tenantId}
                  item={a}
                  sessionTitle={title.get(a.session_id) ?? ""}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
