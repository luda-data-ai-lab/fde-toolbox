import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { handoffUrl } from "../../app/handoff";
import { NeedTenant, PageHeader } from "../../components/ui";
import {
  AUDIT_ROLES,
  useCanWrite,
  useRole,
  useTenantId,
} from "../../app/hooks";
import { CandidatesView } from "./CandidatesView";
import { ConceptsView } from "./ConceptsView";
import { GlossaryView } from "./GlossaryView";
import { ImportPanel } from "./ImportPanel";
import { ValidationView } from "./ValidationView";

const TABS = [
  "glossary",
  "concepts",
  "candidates",
  "validation",
  "import",
] as const;
type Tab = (typeof TABS)[number];

export function OntoMapPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const role = useRole();
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : "glossary";
  if (!tenantId) return <NeedTenant />;
  const base = `/api/v1/t/${tenantId}/ontomap/terms`;
  const tabs = TABS.filter((x) => x !== "import" || canWrite);
  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.ontomap")}
        actions={
          <>
            {canWrite && (
              <Link className="btn" data-testid="send-specforge" to={handoffUrl("/specforge", { glossary: true })}>
                {t("handoff.toSpecForge")}
              </Link>
            )}
            <a className="btn" href={`${base}/template.xlsx`}>
              {t("interfaces.template")}
            </a>
            {role && AUDIT_ROLES.includes(role) && (
              <>
                <a className="btn" href={`${base}/export.xlsx`}>
                  {t("interfaces.exportXlsx")}
                </a>
                <a className="btn" href={`${base}/export.csv`}>
                  {t("interfaces.exportCsv")}
                </a>
              </>
            )}
          </>
        }
      />
      <div role="tablist" className="flex gap-1 border-b border-slate-200">
        {tabs.map((x) => (
          <button
            key={x}
            role="tab"
            aria-selected={tab === x}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === x ? "border-blue-700 font-semibold text-blue-800" : "border-transparent text-slate-600"}`}
            onClick={() => setParams({ tab: x })}
          >
            {t(`ontomap.tab.${x}`)}
          </button>
        ))}
      </div>
      {tab === "glossary" && <GlossaryView tenantId={tenantId} />}
      {tab === "concepts" && <ConceptsView tenantId={tenantId} />}
      {tab === "candidates" && <CandidatesView tenantId={tenantId} />}
      {tab === "validation" && <ValidationView tenantId={tenantId} />}
      {tab === "import" && canWrite && <ImportPanel tenantId={tenantId} />}
    </div>
  );
}
