import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, tenantPath } from "../../api/client";
import type { InterfaceDashboard } from "../../api/types";
import { Empty, Loading } from "../../components/ui";
import { IF_STATUSES, LINK_TYPES, ifKeys } from "./shared";

function CountList({
  title,
  counts,
  keys,
  group,
}: {
  title: string;
  counts: Record<string, number>;
  keys: readonly string[];
  group: string;
}) {
  const { t } = useTranslation();
  return (
    <div className="card">
      <h2 className="mb-2 font-semibold">{title}</h2>
      <ul className="space-y-1 text-sm">
        {keys.map((k) => (
          <li key={k} className="flex justify-between">
            <span>{t(`${group}.${k}`)}</span>
            <span className="font-mono">{counts[k] ?? 0}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function InterfaceDashboardView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ifKeys(tenantId).dashboard,
    queryFn: () =>
      api<InterfaceDashboard>(tenantPath(tenantId, "/interfaces/dashboard")),
  });
  if (isLoading) return <Loading />;
  if (!data) return <Empty />;
  const bars = data.by_system
    .filter((s) => s.outgoing + s.incoming > 0)
    .map((s) => ({
      name: s.name,
      [t("interfaces.outgoing")]: s.outgoing,
      [t("interfaces.incoming")]: s.incoming,
    }));
  return (
    <div className="grid grid-cols-3 gap-4" data-testid="interface-dashboard">
      <div className="card">
        <h2 className="mb-2 font-semibold">{t("interfaces.total")}</h2>
        <p className="text-3xl font-semibold" data-testid="interface-total">
          {data.total}
        </p>
      </div>
      <CountList
        title={t("ifField.link_type")}
        counts={data.by_link_type}
        keys={LINK_TYPES}
        group="linkType"
      />
      <CountList
        title={t("ifField.status")}
        counts={data.by_status}
        keys={IF_STATUSES}
        group="ifStatus"
      />
      <div className="card col-span-3">
        <h2 className="mb-2 font-semibold">{t("interfaces.bySystem")}</h2>
        {bars.length === 0 ? (
          <Empty />
        ) : (
          <div style={{ height: Math.max(200, bars.length * 36) }}>
            <ResponsiveContainer>
              <BarChart data={bars} layout="vertical" margin={{ left: 40 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={120} />
                <Tooltip />
                <Legend />
                <Bar
                  dataKey={t("interfaces.outgoing")}
                  stackId="a"
                  fill="#1d4ed8"
                />
                <Bar
                  dataKey={t("interfaces.incoming")}
                  stackId="a"
                  fill="#93c5fd"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
