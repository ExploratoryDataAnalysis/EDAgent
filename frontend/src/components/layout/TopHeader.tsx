import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Database,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  Layers,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import { DEMO_SAMPLE_DATASETS } from '../../services/demoData';

export const TopHeader: React.FC = () => {
  const location = useLocation();
  const { activeDataset, datasets, selectDataset, isDemoMode, loadDemoBenchmark } = useDataset();

  // Page title mapping based on current pathname
  const pageTitles: Record<string, { title: string; subtitle: string }> = {
    '/': { title: 'Home & Welcome', subtitle: 'Modern Autonomous Exploratory Data Analysis' },
    '/upload': { title: 'Dataset Upload', subtitle: 'Ingest CSV, TSV, or multi-sheet Excel workbooks' },
    '/overview': { title: 'Dataset Overview', subtitle: 'Automatic statistical profiling & quality checks' },
    '/inventory': { title: 'Column Inventory', subtitle: 'Storage types, semantic roles & sample preview' },
    '/workspace': { title: 'Analysis Workspace', subtitle: 'Interactive 3-panel analytics & Plotly canvas' },
    '/chat': { title: 'AI Dataset Chat', subtitle: 'Conversational data exploration with verified execution' },
    '/visualize': { title: 'Visualization Studio', subtitle: 'Plotly chart builder with auto-binning & IQR fences' },
    '/history': { title: 'Analysis History', subtitle: 'Chronological audit trail of analytical queries' },
    '/reports': { title: 'Report Builder', subtitle: 'Compile one-click publication-ready EDA reports' },
    '/exports': { title: 'Export Centre', subtitle: 'Download cleaned datasets, plots, and code recipes' },
  };

  const currentInfo = pageTitles[location.pathname] || {
    title: 'EDAgent',
    subtitle: 'Autonomous Exploratory Data Analysis',
  };

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 flex items-center justify-between z-20 shrink-0">
      {/* Page Title & Breadcrumb */}
      <div>
        <h1 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-2">
          <span>{currentInfo.title}</span>
          {activeDataset && (
            <>
              <span className="text-slate-300 dark:text-slate-600">•</span>
              <span className="text-xs font-mono font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded-md">
                {activeDataset.name}
              </span>
            </>
          )}
        </h1>
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          {currentInfo.subtitle}
        </p>
      </div>

      {/* Right Controls: Dataset Switcher, Status & Upload Button */}
      <div className="flex items-center space-x-3">
        {/* Dataset Quick Switcher Dropdown */}
        <div className="relative group">
          <button className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
            <Database className="w-3.5 h-3.5 text-indigo-500" />
            <span className="max-w-[130px] truncate">
              {activeDataset ? activeDataset.name : 'Switch Dataset'}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {/* Switcher Dropdown Menu */}
          <div className="absolute right-0 mt-1 w-64 rounded-xl bg-white dark:bg-slate-900 shadow-xl border border-slate-200 dark:border-slate-800 py-1.5 hidden group-hover:block hover:block z-50">
            <div className="px-3 py-1 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
              Sample Benchmarks
            </div>
            {DEMO_SAMPLE_DATASETS.map((sample) => (
              <button
                key={sample.id}
                onClick={() => loadDemoBenchmark(sample.id)}
                className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 flex items-center justify-between"
              >
                <span className="truncate">{sample.name}</span>
                <span className="text-[10px] text-slate-400">{sample.rows} rows</span>
              </button>
            ))}

            {datasets.length > 0 && (
              <>
                <div className="px-3 pt-2 pb-1 text-[10px] font-semibold tracking-wider text-slate-400 uppercase border-t border-slate-100 dark:border-slate-800 mt-1">
                  Uploaded Datasets
                </div>
                {datasets.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => selectDataset(d.id)}
                    className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 flex items-center justify-between"
                  >
                    <span className="truncate">{d.name}</span>
                    <span className="text-[10px] text-slate-400">{d.row_count || 0} rows</span>
                  </button>
                ))}
              </>
            )}
          </div>
        </div>

        {/* Backend Online / Demo Mode indicator */}
        <div
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
            isDemoMode
              ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300'
              : 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300'
          }`}
          title={
            isDemoMode
              ? 'Using deterministic sample benchmark for interactive preview.'
              : 'Connected to local FastAPI backend on port 8000.'
          }
        >
          {isDemoMode ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              <span>Demo Preview</span>
            </>
          ) : (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>API Connected</span>
            </>
          )}
        </div>

        {/* Quick Upload CTA */}
        <Link
          to="/upload"
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 shadow-sm transition-all"
        >
          <UploadCloud className="w-3.5 h-3.5" />
          <span>Upload</span>
        </Link>
      </div>
    </header>
  );
};
