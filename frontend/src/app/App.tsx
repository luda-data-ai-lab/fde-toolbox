import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./Layout";
import { Loading } from "../components/ui";
import { useMe } from "./hooks";
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
import { ProjectPage } from "../modules/devtracker/ProjectPage";
import { ProjectsPage } from "../modules/devtracker/ProjectsPage";

function Protected() {
  const { data, isLoading } = useMe();
  if (isLoading) return <Loading />;
  if (!data) return <Navigate to="/login" replace />;
  return <Layout />;
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
        <Route path="audit" element={<AuditPage />} />
        <Route path="assets" element={<AssetsPage />} />
        <Route path="assets/:assetId" element={<AssetDetailPage />} />
        <Route path="devtracker" element={<ProjectsPage />} />
        <Route path="devtracker/projects/:projectId" element={<ProjectPage />} />
        <Route path="agenthub" element={<AgentHubPage />} />
        <Route path="agenthub/templates/:assetId" element={<TemplatePage />} />
        <Route path="admin/tenants" element={<TenantsPage />} />
        <Route path="admin/users" element={<UsersPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
