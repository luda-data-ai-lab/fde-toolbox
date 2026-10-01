import { useTranslation } from "react-i18next";
import { Field } from "../../components/ui";
import { useWorkspace } from "../../app/store";
import { useEngagements } from "./shared";

export function EngagementSelect({
  tenantId,
  value,
  onChange,
  optional,
}: {
  tenantId: string;
  value: string;
  onChange: (v: string) => void;
  optional?: boolean;
}) {
  const { t } = useTranslation();
  const engagementId = useWorkspace((s) => s.engagementId);
  const engagements = useEngagements(tenantId).data?.items ?? [];
  return (
    <Field label={t("nav.engagements")}>
      <select
        className="input"
        required={!optional}
        value={value || engagementId || ""}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{optional ? t("coachq.allEngagements") : "—"}</option>
        {engagements.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
          </option>
        ))}
      </select>
    </Field>
  );
}
