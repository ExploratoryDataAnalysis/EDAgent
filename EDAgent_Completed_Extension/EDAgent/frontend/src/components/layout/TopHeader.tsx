import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Database,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  Layers,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import { chatService } from '../../services/api';
import { AIStatus } from '../../types';

export const TopHeader: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { activeDataset, datasets, samples, selectDataset, loadSample } = useDataset();
  const [menuOpen, setMenuOpen] = useState(false);
  const [ai, setAi] = useState<AIStatus | null>(null);

  useEffect(() => {
    chatService.status().then(setAi).catch(() => setAi(null));
  }, []);

  // Page title mapping based on current pathname
  const pageTitles: Record<string, { title: string; subtitle: string }> = {
    '/': { title: 'Home & Welcome', subtitle: 'Modern Autonomous Exploratory Data Analysis' },
    '/upload': { title: 'Dataset Upload', subtitle: 'Ingest CSV, TSV, or multi-sheet Excel workbooks' },
    '/overview': { title: 'Dataset Overview', subtitle: 'Automatic statistical profiling & quality checks' },
    '/inventory': { title: 'Column Inventory', subtitle: 'Storage types, semantic roles & sample preview' },
    '/workspace': { title: 'Analysis Workspace', subtitle: 'Run verified analyses on your data' },
    '/chat': { title: 'AI Dataset Chat', subtitle: 'Conversational data exploration with verified execution' },
    '/visualize': { title: 'Visualization Studio', subtitle: 'Build charts from verified backend computations' },
    '/history': { title: 'Analysis History', subtitle: 'Chronological audit trail of analytical queries' },
    '/reports': { title: 'Report Builder', subtitle: 'Compile one-click publication-ready EDA reports' },
    '/exports': { title: 'Export Centre', subtitle: 'Download charts, tables, code and reports' },
  };

  const currentInfo = pageTitles[location.pathname] || {
    title: 'EDAgent',
    subtitle: 'Autonomous Exploratory Data Analysis',
  };

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-3 sm:px-6 flex items-center justify-between z-20 shrink-0">
      {/* Page Title & Breadcrumb */}
      <div className="min-w-0">
        <h1 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-2 min-w-0">
          <span>{currentInfo.title}</span>
          {activeDataset && (
            <>
              <span className="hidden md:inline text-slate-300 dark:text-slate-600">•</span>
              <span className="hidden md:inline text-xs font-mono font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded-md truncate max-w-[16rem]">
                {activeDataset.name}
              </span>
            </>
          )}
        </h1>
        <p className="hidden sm:block text-[11px] text-slate-500 dark:text-slate-400">
          {currentInfo.subtitle}
        </p>
      </div>

      {/* Right Controls: Dataset Switcher, AI status & Upload Button */}
      <div className="flex items-center space-x-3">
        {/* Dataset quick switcher (click to open so it also works on touch screens) */}
        <div className="relative">
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            <Database className="w-3.5 h-3.5 text-indigo-500" />
            <span className="max-w-[90px] sm:max-w-[130px] truncate">{activeDataset ? activeDataset.name : 'Switch Dataset'}</span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {menuOpen && (
            <div
              className="absolute right-0 mt-1 w-72 max-h-96 overflow-y-auto rounded-xl bg-white dark:bg-slate-900 shadow-xl border border-slate-200 dark:border-slate-800 py-1.5 z-50"
              onMouseLeave={() => setMenuOpen(false)}
            >
              {datasets.length > 0 && (
                <>
                  <div className="px-3 py-1 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">Your datasets</div>
                  {datasets.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => { setMenuOpen(false); selectDataset(d.id); }}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 flex items-center justify-between"
                    >
                      <span className="truncate">{d.name}</span>
                      <span className="text-[10px] text-slate-400 ml-2 shrink-0">{(d.row_count ?? 0).toLocaleString()} rows</span>
                    </button>
                  ))}
                </>
              )}
              {samples.length > 0 && (
                <>
                  <div className="px-3 pt-2 pb-1 text-[10px] font-semibold tracking-wider text-slate-400 uppercase border-t border-slate-100 dark:border-slate-800 mt-1">
                    Sample datasets (copies are added to your account)
                  </div>
                  {samples.map((sm) => (
                    <button
                      key={sm.id}
                      onClick={async () => { setMenuOpen(false); await loadSample(sm.id); navigate('/overview'); }}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-600 flex items-center justify-between"
                    >
                      <span className="truncate">{sm.name}</span>
                      <span className="text-[10px] px-1.5 rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 ml-2">Sample</span>
                    </button>
                  ))}
                </>
              )}
              {datasets.length === 0 && samples.length === 0 && (
                <div className="px-3 py-2 text-xs text-slate-500">No datasets yet. Upload one to get started.</div>
              )}
            </div>
          )}
        </div>

        {/* AI status: honest about whether a language model is configured */}
        {ai && (
          <div
            className={`hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              ai.configured
                ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300'
                : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300'
            }`}
            title={ai.message || undefined}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${ai.configured ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span>{ai.configured ? `AI: ${ai.provider}` : 'AI not configured'}</span>
          </div>
        )}

        {/* Quick Upload CTA */}
        <Link
          to="/upload"
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 shadow-sm transition-all"
        >
          <UploadCloud className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Upload</span>
        </Link>
      </div>
    </header>
  );
};
