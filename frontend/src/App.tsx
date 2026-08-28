import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { DataCenterPage } from "./pages/DataCenterPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LlmTracesPage } from "./pages/LlmTracesPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkbenchPage } from "./pages/WorkbenchPage";

export default function App() {
  return <BrowserRouter><Routes><Route element={<AppShell />}><Route index element={<ProjectsPage />} /><Route path="projects/:projectId" element={<WorkbenchPage />} /><Route path="projects/:projectId/history" element={<HistoryPage />} /><Route path="projects/:projectId/traces" element={<LlmTracesPage />} /><Route path="analytics" element={<AnalyticsPage />} /><Route path="data-center" element={<DataCenterPage />} /><Route path="settings" element={<SettingsPage />} /></Route></Routes></BrowserRouter>;
}
