import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, tenantPath } from "../api/client";
import type { Engagement, Page } from "../api/types";
import { useMe, useTenantId } from "./hooks";
import { navGroups, tenantListPath } from "./nav";
import { useWorkspace } from "./store";

function TenantSelector() {
  const { t } = useTranslation();
  const { data } = useMe();
  const { tenantId, setTenant } = useWorkspace();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const tenants = useMemo(() => data?.tenants ?? [], [data]);
  useEffect(() => {
    const first = tenants[0];
    if (first && !tenants.some((x) => x.id === tenantId)) setTenant(first.id);
    if (!tenants.length && tenantId) setTenant(null);
  }, [tenants, tenantId, setTenant]);
  return (
    <select
      aria-label={t("layout.tenant")}
      className="input w-48"
      value={tenantId ?? ""}
      onChange={(e) => {
        setTenant(e.target.value || null);
        const list = tenantListPath(pathname);
        if (list) navigate(list);
      }}
    >
      {!tenants.length && <option value="">{t("layout.noTenant")}</option>}
      {tenants.map((x) => (
        <option key={x.id} value={x.id}>
          {x.name}
        </option>
      ))}
    </select>
  );
}

function EngagementSelector() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const { engagementId, setEngagement } = useWorkspace();
  const { data } = useQuery({
    queryKey: ["engagements", tenantId],
    queryFn: () => api<Page<Engagement>>(tenantPath(tenantId, "/engagements"), { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
  if (!tenantId) return null;
  return (
    <select
      aria-label={t("layout.engagement")}
      className="input w-48"
      value={engagementId ?? ""}
      onChange={(e) => setEngagement(e.target.value || null)}
    >
      <option value="">{t("layout.allEngagements")}</option>
      {data?.items.map((e) => (
        <option key={e.id} value={e.id}>
          {e.name}
        </option>
      ))}
    </select>
  );
}

export function Layout() {
  const { t, i18n } = useTranslation();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: () => api<unknown>("/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
      navigate("/login");
    },
  });
  const role = me?.user.role;
  const tenantId = useTenantId();
  const toggleLocale = () => {
    const next = i18n.language === "ko" ? "en" : "ko";
    localStorage.setItem("fde-locale", next);
    void i18n.changeLanguage(next);
  };
  return (
    <div className="flex min-h-screen bg-slate-50 font-sans text-slate-800">
      <aside className="w-52 shrink-0 border-r border-slate-200 bg-white">
        <div className="px-4 py-4 text-lg font-bold text-blue-900">{t("app.title")}</div>
        <nav className="flex flex-col gap-2">
          {navGroups(role).map((group) => (
            <div key={group.key} className="flex flex-col">
              {group.key !== "home" && (
                <div className="px-4 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {t(`nav.group.${group.key}`)}
                </div>
              )}
              {group.links.map(([to, key]) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) =>
                    `px-4 py-2 text-sm ${isActive ? "bg-blue-50 font-semibold text-blue-800" : "text-slate-600 hover:bg-slate-50"}`
                  }
                >
                  {t(key)}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
          <TenantSelector />
          <EngagementSelector />
          <div className="ml-auto flex items-center gap-3 text-sm">
            <button className="btn" onClick={toggleLocale}>
              {t("layout.locale")}
            </button>
            <span data-testid="current-user">
              {me?.user.name} · {role && t(`roles.${role}`)}
            </span>
            <button className="btn" onClick={() => logout.mutate()}>
              {t("auth.logout")}
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet key={tenantId ?? "none"} />
        </main>
      </div>
    </div>
  );
}
