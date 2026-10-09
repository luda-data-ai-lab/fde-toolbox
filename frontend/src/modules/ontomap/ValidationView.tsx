import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { ValidationIssue } from "../../api/types";
import { Empty } from "../../components/ui";
import { ontoKeys, ontoPath } from "./shared";

export function ValidationView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ontoKeys(tenantId).validation,
    queryFn: () =>
      api<{ issues: ValidationIssue[] }>(ontoPath(tenantId, "/validation")),
  });
  return (
    <div className="card space-y-2">
      <p className="text-sm text-slate-600">{t("ontomap.validation.hint")}</p>
      {!data?.issues.length ? (
        <Empty />
      ) : (
        <table className="table" data-testid="validation-table">
          <thead>
            <tr>
              <th>{t("ontomap.validation.target")}</th>
              <th>{t("ontomap.validation.issue")}</th>
            </tr>
          </thead>
          <tbody>
            {data.issues.map((i) => (
              <tr key={`${i.code}:${i.target_id}`} data-testid="validation-row">
                <td className="font-medium">
                  {i.name}{" "}
                  <span className="badge">
                    {t(`ontomap.validation.type.${i.target_type}`)}
                  </span>
                </td>
                <td>{t(`ontomap.validation.${i.code}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
