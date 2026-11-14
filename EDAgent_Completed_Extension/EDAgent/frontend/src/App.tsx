import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DatasetProvider } from './context/DatasetContext';
import { LoginPage } from './pages/LoginPage';
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
import { InterventionPage } from './pages/InterventionPage';

function WorkspaceEntry({ login = false }: { login?: boolean }) {
  const { user, initialising } = useAuth();
  if (initialising) return <p role="status" className="p-6">Restoring your session…</p>;
  if (!user) return <LoginPage />;
  if (login) return <Navigate to="/analyser" replace />;
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
          <Route path="/illustrative-scenario" element={<InterventionPage />} />
        </Route>
        <Route element={<WorkspaceEntry />}>
          <Route path="/analyser" element={<HomePage />} />
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
