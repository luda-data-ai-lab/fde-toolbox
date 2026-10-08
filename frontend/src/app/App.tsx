import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./Layout";
import { Loading } from "../components/ui";
import type { ReactNode } from "react";
import type { Role } from "../api/types";
import { AUDIT_ROLES, useMe, useRole } from "./hooks";
import { AdaptersPage } from "../core/AdaptersPage";
import { AssetDetailPage, AssetsPage } from "../core/AssetsPage";
import { AuditPage } from "../core/AuditPage";
import { EngagementsPage } from "../core/EngagementsPage";
import { FilesPage } from "../core/FilesPage";
import { HomePage } from "./HomePage";
import { LoginPage } from "./LoginPage";
import { SystemsPage } from "../core/SystemsPage";
import { TenantsPage } from "../core/TenantsPage";
import { UsersPage } from "../core/UsersPage";
import { AgentHubPage, TemplatePage } from "../modules/agenthub/AgentHubPage";
import { DiscoveryQPage } from "../modules/discoveryq/DiscoveryQPage";
import { InterfacesPage } from "../modules/interfaces/InterfacesPage";
import { OntoMapPage } from "../modules/ontomap/OntoMapPage";
import { FlowDeskPage } from "../modules/flowdesk/FlowDeskPage";
import { SpecForgePage } from "../modules/specforge/SpecForgePage";
import { ManualPage } from "../manual/ManualPage";
import { ProjectPage } from "../modules/devtracker/ProjectPage";
import { ProjectsPage } from "../modules/devtracker/ProjectsPage";

function Protected() {
  const { data, isLoading } = useMe();
  if (isLoading) return <Loading />;
  if (!data) return <Navigate to="/login" replace />;
  return <Layout />;
}

export function RequireRole({
  roles,
  children,
}: {
  roles: Role[];
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const role = useRole();
  if (!role || !roles.includes(role))
    return <p className="card">{t("errors.forbidden")}</p>;
  return <>{children}</>;
}

function NotFound() {
  const { t } = useTranslation();
  return <p className="card">{t("errors.not_found")}</p>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route index element={<HomePage />} />
        <Route path="engagements" element={<EngagementsPage />} />
        <Route path="systems" element={<SystemsPage />} />
        <Route path="files" element={<FilesPage />} />
        <Route
          path="audit"
          element={
            <RequireRole roles={AUDIT_ROLES}>
              <AuditPage />
            </RequireRole>
          }
        />
        <Route
          path="adapters"
          element={
            <RequireRole roles={AUDIT_ROLES}>
              <AdaptersPage />
            </RequireRole>
          }
        />
        <Route path="assets" element={<AssetsPage />} />
        <Route path="assets/:assetId" element={<AssetDetailPage />} />
        <Route path="devtracker" element={<ProjectsPage />} />
        <Route
          path="devtracker/projects/:projectId"
          element={<ProjectPage />}
        />
        <Route path="agenthub" element={<AgentHubPage />} />
        <Route path="discoveryq" element={<DiscoveryQPage />} />
        <Route path="interfaces" element={<InterfacesPage />} />
        <Route path="ontomap" element={<OntoMapPage />} />
        <Route path="flowdesk" element={<FlowDeskPage />} />
        <Route path="specforge" element={<SpecForgePage />} />
        <Route path="manual" element={<ManualPage />} />
        <Route path="manual/:topic" element={<ManualPage />} />
        <Route path="agenthub/templates/:assetId" element={<TemplatePage />} />
        <Route
          path="admin/tenants"
          element={
            <RequireRole roles={["luda_admin"]}>
              <TenantsPage />
            </RequireRole>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireRole roles={["luda_admin"]}>
              <UsersPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
