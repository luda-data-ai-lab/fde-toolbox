import { useInfiniteQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../api/client";
import type { AuditLog, Page } from "../api/types";
import { Empty, NeedTenant, PageHeader } from "../components/ui";
import { useTenantId } from "../app/hooks";
import { fmtDate } from "../app/format";

export function AuditPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const q = useInfiniteQuery({
    queryKey: ["audit", tenantId],
    queryFn: ({ pageParam }) =>
      api<Page<AuditLog>>(tenantPath(tenantId, "/audit-logs"), { query: { limit: 100, cursor: pageParam } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!tenantId,
  });
  if (!tenantId) return <NeedTenant />;
  const rows = q.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.audit")}
        actions={
          <a className="btn" href={`/api/v1/t/${tenantId}/audit-logs/export.csv`}>
            {t("audit.exportCsv")}
          </a>
        }
      />
      <div className="card">
        {!rows.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("audit.at")}</th>
                <th>{t("audit.action")}</th>
                <th>{t("audit.target")}</th>
                <th>{t("audit.actor")}</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap">{fmtDate(r.at)}</td>
                  <td className="font-mono text-xs">{r.action}</td>
                  <td className="font-mono text-xs">
                    {r.target_type} {r.target_id}
                  </td>
                  <td className="font-mono text-xs">{r.actor_id}</td>
                  <td>{r.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {q.hasNextPage && (
          <button className="btn mt-3" onClick={() => void q.fetchNextPage()}>
            {t("common.more")}
          </button>
        )}
      </div>
    </div>
  );
}
