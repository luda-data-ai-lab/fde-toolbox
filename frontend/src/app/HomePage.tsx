import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import type { Home, TenantHome } from "../api/types";
import { ErrorText, Loading, PageHeader, StatusBadge } from "../components/ui";
import { useWorkspace } from "./store";

const INSTANCE_STATUSES = ["ready", "pilot", "production", "stopped"] as const;

function TenantCard({ tenant }: { tenant: TenantHome }) {
  const { t } = useTranslation();
  const setTenant = useWorkspace((s) => s.setTenant);
  const byStatus = tenant.agenthub.instances_by_status ?? {};
  const chart = INSTANCE_STATUSES.map((s) => ({ name: t(`instanceStatus.${s}`), count: byStatus[s] ?? 0 }));
  return (
    <section className="card space-y-3" data-testid={`home-tenant-${tenant.code}`}>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">
          {tenant.name} <span className="text-xs text-slate-500">{tenant.code}</span>
        </h2>
        <button className="btn" onClick={() => setTenant(tenant.tenant_id)}>
          {t("home.open")}
        </button>
      </div>
      <div>
        <h3 className="label">{t("nav.engagements")}</h3>
        <ul className="space-y-1 text-sm">
          {tenant.engagements.map((e) => (
            <li key={e.id}>
              {e.name} <StatusBadge group="engagementStatus" value={e.status} />
            </li>
          ))}
        </ul>
      </div>
      <p className="text-sm">
        {t("home.openTasks")}: <strong>{tenant.devtracker.open_tasks ?? 0}</strong>
      </p>
      {!!tenant.devtracker.paused_tasks?.length && (
        <div>
          <h3 className="label">{t("home.pausedTasks")}</h3>
          <ul className="space-y-1 text-sm">
            {tenant.devtracker.paused_tasks.map((task) => (
              <li key={task.id}>
                <Link className="text-blue-700 hover:underline" to={`/devtracker/projects/${task.project_id}`}>
                  {task.title}
                </Link>
                {task.pause_note && <span className="text-slate-500"> — {task.pause_note}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="h-32">
        <h3 className="label">{t("home.instances")}</h3>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chart}>
            <XAxis dataKey="name" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} width={24} />
            <Tooltip />
            <Bar dataKey="count" fill="#1d4ed8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function HomePage() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({ queryKey: ["home"], queryFn: () => api<Home>("/home") });
  if (isLoading) return <Loading />;
  if (!data) return <ErrorText error={error} />;
  return (
    <div>
      <PageHeader title={t(`home.title_${data.role}`)} />
      <div className="mb-4 flex gap-3">
        {Object.entries(data.totals).map(([k, v]) => (
          <div key={k} className="card min-w-32">
            <div className="label">{t(`home.totals.${k}`)}</div>
            <div className="text-2xl font-semibold">{v}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.tenants.map((tenant) => (
          <TenantCard key={tenant.tenant_id} tenant={tenant} />
        ))}
      </div>
    </div>
  );
}
