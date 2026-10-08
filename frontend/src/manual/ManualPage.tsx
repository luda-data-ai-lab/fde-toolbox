import { useTranslation } from "react-i18next";
import { NavLink, useParams } from "react-router-dom";
import { Markdown } from "./markdown";
import { TOPICS, isTopic, manualSource, manualTitle, type ManualLocale } from "./topics";

export function ManualPage() {
  const { t, i18n } = useTranslation();
  const { topic } = useParams();
  const locale: ManualLocale = i18n.language === "en" ? "en" : "ko";
  if (topic !== undefined && !isTopic(topic)) return <p className="card">{t("errors.not_found")}</p>;
  const current = topic ?? "start";
  return (
    <div className="flex gap-6">
      <nav aria-label={t("manual.contents")} className="card h-fit w-56 shrink-0 p-0">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">{t("manual.title")}</div>
        <ul className="py-1">
          {TOPICS.map((x) => (
            <li key={x}>
              <NavLink
                to={`/manual/${x}`}
                className={() =>
                  `block px-4 py-1.5 text-sm ${x === current ? "bg-blue-50 font-semibold text-blue-800" : "text-slate-600 hover:bg-slate-50"}`
                }
              >
                {manualTitle(manualSource(locale, x))}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="card min-w-0 flex-1" data-testid="manual-content">
        <Markdown source={manualSource(locale, current)} />
      </div>
    </div>
  );
}
