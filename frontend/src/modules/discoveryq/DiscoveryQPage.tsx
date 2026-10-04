import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { NeedTenant, PageHeader } from "../../components/ui";
import { useTenantId } from "../../app/hooks";
import { ActionItemsView } from "./ActionItemsView";
import { CustomQuestionsView } from "./CustomQuestionsView";
import { QuestionBankView } from "./QuestionBankView";
import { SessionsView } from "./SessionsView";
import { SubjectsView } from "./SubjectsView";
import { WorksheetView } from "./WorksheetView";

const TABS = ["sessions", "subjects", "bank", "custom", "actions"] as const;
type Tab = (typeof TABS)[number];

export function DiscoveryQPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : "sessions";
  const sessionId = params.get("session");
  if (!tenantId) return <NeedTenant />;
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.discoveryq")} />
      <div role="tablist" className="flex gap-1 border-b border-slate-200">
        {TABS.map((x) => (
          <button
            key={x}
            role="tab"
            aria-selected={tab === x && !sessionId}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === x && !sessionId ? "border-blue-700 font-semibold text-blue-800" : "border-transparent text-slate-600"}`}
            onClick={() => setParams({ tab: x })}
          >
            {t(`discoveryq.tab.${x}`)}
          </button>
        ))}
      </div>
      {sessionId ? (
        <WorksheetView
          key={sessionId}
          tenantId={tenantId}
          sessionId={sessionId}
          onBack={() => setParams({ tab: "sessions" })}
        />
      ) : (
        <>
          {tab === "sessions" && (
            <SessionsView
              tenantId={tenantId}
              onOpen={(id) => setParams({ tab: "sessions", session: id })}
            />
          )}
          {tab === "subjects" && <SubjectsView tenantId={tenantId} />}
          {tab === "bank" && <QuestionBankView tenantId={tenantId} />}
          {tab === "custom" && <CustomQuestionsView tenantId={tenantId} />}
          {tab === "actions" && <ActionItemsView tenantId={tenantId} />}
        </>
      )}
    </div>
  );
}
