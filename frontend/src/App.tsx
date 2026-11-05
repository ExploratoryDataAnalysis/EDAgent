import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { UploadPage } from './pages/UploadPage';
import { OverviewPage } from './pages/OverviewPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { ReportBuilderPage } from './pages/ReportBuilderPage';
import { HistoryPage } from './pages/HistoryPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Navigation Bar */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center space-x-3">
                <span className="text-2xl font-black text-blue-600 tracking-tight">EDA<span className="text-gray-900">gent</span></span>
                <span className="text-xs bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 rounded border border-blue-200">Phase 1</span>
              </div>
              <nav className="flex space-x-6 text-sm font-medium">
                <Link to="/" className="text-gray-700 hover:text-blue-600">Home</Link>
                <Link to="/upload" className="text-gray-700 hover:text-blue-600">Upload Dataset</Link>
                <Link to="/overview" className="text-gray-700 hover:text-blue-600">Profiler</Link>
                <Link to="/workspace" className="text-gray-700 hover:text-blue-600">Workspace</Link>
                <Link to="/reports" className="text-gray-700 hover:text-blue-600">Reports</Link>
                <Link to="/history" className="text-gray-700 hover:text-blue-600">History</Link>
              </nav>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/reports" element={<ReportBuilderPage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};

export default App;
