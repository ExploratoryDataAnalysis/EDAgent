import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { DatasetProvider } from './context/DatasetContext';
import { LoginPage } from './pages/LoginPage';
import { AppLayout } from './components/layout/AppLayout';

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

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <DatasetProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<AppLayout><Outlet /></AppLayout>}>
                <Route index element={<HomePage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/overview" element={<OverviewPage />} />
                <Route path="/inventory" element={<InventoryPage />} />
                <Route path="/workspace" element={<WorkspacePage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/visualize" element={<VisualizePage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/reports" element={<ReportBuilderPage />} />
                <Route path="/exports" element={<ExportCentrePage />} />
                <Route path="/road-safety" element={<RoadSafetyPage />} />
                <Route path="/illustrative-scenario" element={<InterventionPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </DatasetProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
