import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DatasetProvider } from './context/DatasetContext';
import { LoginPage } from './pages/LoginPage';
import { AnalyserStart, SamplePage } from './pages/SamplePage';
import { AppLayout } from './components/layout/AppLayout';
import { PublicLayout } from './components/layout/PublicLayout';
import { InvestigationPage } from './pages/InvestigationPage';
import { MethodsPage } from './pages/MethodsPage';

import { HomePage } from './pages/HomePage';
import { UploadPage } from './pages/UploadPage';
import { OverviewPage } from './pages/OverviewPage';
import { InventoryPage } from './pages/InventoryPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { ChatPage } from './pages/ChatPage';
import { VisualizePage } from './pages/VisualizePage';
import { HistoryPage } from './pages/HistoryPage';
import { ReportBuilderPage } from './pages/ReportBuilderPage';
import { ExportCentrePage } from './pages/ExportCentrePage';
import { RoadSafetyPage } from './pages/RoadSafetyPage';
import { CountyGridPage } from './pages/CountyGridPage';
import { SeverityEvidencePage } from './pages/SeverityEvidencePage';
import { ModelDiagnosticsPage } from './pages/ModelDiagnosticsPage';
import { InterventionPage } from './pages/InterventionPage';

function WorkspaceEntry({ login = false, onboarding = false }: { login?: boolean; onboarding?: boolean }) {
  const { user, initialising, guestNotice } = useAuth();
  const { pathname } = useLocation();
  if (initialising) return <p role="status" className="p-6">Restoring your session…</p>;
  if (!user) {
    if (onboarding) return <AnalyserStart />;
    if (guestNotice && !login) return <Navigate to="/analyser" replace />;
    return <LoginPage />;
  }
  if (login || (user.guest && pathname === '/chat')) return <Navigate to="/analyser" replace />;
  return <AppLayout><Outlet /></AppLayout>;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <DatasetProvider key={user?.id ?? 'anonymous'}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<InvestigationPage />} />
          <Route path="/methods" element={<MethodsPage />} />
          <Route path="/road-safety" element={<RoadSafetyPage />} />
          <Route path="/road-safety/map" element={<CountyGridPage />} />
          <Route path="/road-safety/evidence" element={<SeverityEvidencePage />} />
          <Route path="/road-safety/models" element={<ModelDiagnosticsPage />} />
          <Route path="/illustrative-scenario" element={<InterventionPage />} />
        </Route>
        <Route element={<WorkspaceEntry onboarding />}>
          <Route path="/analyser" element={<HomePage />} />
        </Route>
        <Route path="/analyser/sample/teaching" element={<SamplePage key="teaching" sample="teaching" />} />
        <Route path="/analyser/sample/county" element={<SamplePage key="county" sample="county" />} />
        <Route element={<WorkspaceEntry />}>
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/visualize" element={<VisualizePage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports" element={<ReportBuilderPage />} />
          <Route path="/exports" element={<ExportCentrePage />} />
        </Route>
        <Route path="/login" element={<WorkspaceEntry login />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DatasetProvider>
  );
}

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter><AppRoutes /></BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
