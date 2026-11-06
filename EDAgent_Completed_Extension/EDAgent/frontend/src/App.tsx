import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DatasetProvider } from './context/DatasetContext';
import { LoginPage } from './pages/LoginPage';
import { LoadingSpinner } from './components/ui/LoadingSpinner';
import { AppLayout } from './components/layout/AppLayout';

// 10 Specified Pages
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

/** Shows the login screen until a valid session exists. */
const Gate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, initialising } = useAuth();
  if (initialising) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <LoadingSpinner text="Restoring your session…" />
      </div>
    );
  }
  return user ? <>{children}</> : <LoginPage />;
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
      <Gate>
      <DatasetProvider>
        <BrowserRouter>
          <AppLayout>
            <Routes>
              {/* 1. Home / Landing page */}
              <Route path="/" element={<HomePage />} />

              {/* 2. Dataset upload page */}
              <Route path="/upload" element={<UploadPage />} />

              {/* 3. Dataset overview dashboard */}
              <Route path="/overview" element={<OverviewPage />} />

              {/* 4. Dataset preview & column inventory */}
              <Route path="/inventory" element={<InventoryPage />} />

              {/* 5. Analysis workspace */}
              <Route path="/workspace" element={<WorkspacePage />} />

              {/* 6. AI dataset chat interface */}
              <Route path="/chat" element={<ChatPage />} />

              {/* 7. Visualization workspace */}
              <Route path="/visualize" element={<VisualizePage />} />

              {/* 8. Analysis history & audit trail */}
              <Route path="/history" element={<HistoryPage />} />

              {/* 9. Report builder */}
              <Route path="/reports" element={<ReportBuilderPage />} />

              {/* 10. Export centre */}
              <Route path="/exports" element={<ExportCentrePage />} />

              {/* Fallback route */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AppLayout>
        </BrowserRouter>
      </DatasetProvider>
      </Gate>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
