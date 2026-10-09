import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { CoverageRow } from "../../api/types";
import { Empty, StatusBadge } from "../../components/ui";
import { ontoKeys, ontoPath } from "./shared";

export function CoverageView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ontoKeys(tenantId).coverage,
    queryFn: () => api<CoverageRow[]>(ontoPath(tenantId, "/coverage")),
  });
  return (
    <div className="card space-y-2">
      <p className="text-sm text-slate-600">{t("ontomap.coverage.hint")}</p>
      {!data?.length ? (
        <Empty />
      ) : (
        <table className="table" data-testid="coverage-table">
          <thead>
            <tr>
              <th>{t("ontomap.coverage.concept")}</th>
              <th>{t("ontomap.coverage.mappings")}</th>
              <th>{t("ontomap.coverage.systems")}</th>
              <th>{t("ontomap.coverage.attributes")}</th>
              <th>{t("ontomap.coverage.unmapped")}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => {
              const mapped = r.attributes_total - r.unmapped_attributes.length;
              return (
                <tr
                  key={r.concept_id}
                  data-testid="coverage-row"
                  className={r.mapping_count === 0 ? "bg-amber-50" : undefined}
                >
                  <td className="font-medium">
                    {r.name}{" "}
                    <StatusBadge group="conceptStatus" value={r.status} />
                  </td>
                  <td>{r.mapping_count}</td>
                  <td>
                    {r.systems.length}
                    {r.systems.length > 0 && (
                      <span className="text-slate-500">
                        {" "}
                        ({r.systems.join(", ")})
                      </span>
                    )}
                  </td>
                  <td>
                    {mapped} / {r.attributes_total}
                  </td>
                  <td className="text-slate-600">
                    {r.unmapped_attributes.join(", ")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
