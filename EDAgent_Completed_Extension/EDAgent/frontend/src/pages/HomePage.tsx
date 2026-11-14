import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  LayoutDashboard,
  Cpu,
  Sparkles,
  ShieldCheck,
  Zap,
  BarChart3,
  FileSpreadsheet,
  ArrowRight,
  Database,
  CheckCircle2,
  Compass,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { Modal } from '../components/ui/Modal';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { datasets, samples, selectDataset, loadSample, deleteDataset, activeDataset } = useDataset();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleSelectSample = async (id: string) => {
    if (await loadSample(id)) navigate('/overview');
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteDataset(pendingDelete);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Could not delete the dataset');
    }
    setPendingDelete(null);
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-10 space-y-12">
      {/* Hero Section */}
      <div className="relative rounded-3xl bg-gradient-to-b from-indigo-900/10 via-slate-50 to-white dark:from-indigo-950/30 dark:via-slate-900/50 dark:to-slate-900 p-8 sm:p-12 border border-indigo-100/60 dark:border-indigo-900/40 shadow-sm overflow-hidden">
        <div className="max-w-3xl space-y-5">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950/80 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500 animate-spin" />
            <span>Autonomous Exploratory Data Analysis & Verification</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-slate-900 dark:text-white leading-[1.15]">
            Upload your data. Discover insights. <span className="bg-gradient-to-r from-indigo-600 to-cyan-500 bg-clip-text text-transparent">Verify every result.</span>
          </h1>

          <p className="text-base text-slate-600 dark:text-slate-300 leading-relaxed">
            EDAgent delivers deterministic statistical profiling, automated anomaly checks, interactive Plotly visualization, and guardrailed conversational analysis with <strong>zero AI hallucination</strong> in underlying computations.
          </p>

          <div className="pt-2 flex flex-wrap gap-3">
            <Link
              to="/road-safety"
              className="inline-flex items-center space-x-2 px-5 py-3 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 via-indigo-700 to-cyan-600 hover:from-indigo-700 hover:to-cyan-700 shadow-lg shadow-indigo-600/25 transition-all"
            >
              <Compass className="w-4 h-4 text-cyan-200 animate-spin" />
              <span>Explore Road Safety Narrative (248k Crashes)</span>
            </Link>

            <Link
              to="/upload"
              className="inline-flex items-center space-x-2 px-5 py-3 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 dark:bg-indigo-500 dark:hover:bg-indigo-600 shadow-lg shadow-indigo-600/25 transition-all"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload Tabular Dataset</span>
            </Link>

            <button
              onClick={() => samples[0] && handleSelectSample(samples[0].id)}
              disabled={samples.length === 0}
              className="inline-flex items-center space-x-2 px-5 py-3 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 shadow-sm transition-all"
            >
              <Database className="w-4 h-4 text-indigo-500" />
              <span>Explore a Sample Dataset</span>
            </button>

            <Link
              to="/workspace"
              className="inline-flex items-center space-x-2 px-5 py-3 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 shadow-sm transition-all"
            >
              <Cpu className="w-4 h-4 text-cyan-500" />
              <span>Open Workspace</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Core Architectural Pillars */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Commercial-Grade EDA Capabilities
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Strictly engineered following the EDAgent specification blueprint.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <Zap className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Deterministic Profiler
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Computes descriptive stats, missingness, duplicates, and role inference with pure Python/Scipy. Zero LLM reliance for ground truth.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <BarChart3 className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Plotly Visual Canvas
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Auto-binned histograms, boxplots with 1.5x IQR Tukey fences, Cramér's V associations, and correlation heatmaps.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Guardrailed AI Chat
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Translates conversational queries into machine-validated execution plans. Explains findings strictly from computed numbers.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-50 dark:bg-cyan-950/40 text-cyan-600 dark:text-cyan-400 flex items-center justify-center">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              One-Click Executive Reports
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Compiles publication-grade PDF and HTML reports with SHA-256 reproducibility hashes and execution audit logs.
            </p>
          </div>
        </div>
      </div>

      {/* Sample datasets (served by the backend) */}
      <div>
        <div className="mb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Sample datasets</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Synthetic datasets for trying EDAgent without uploading anything. Choosing one adds a copy to your account.
          </p>
        </div>

        {samples.length === 0 ? (
          <p className="text-xs text-slate-400">No sample datasets are available on this server.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {samples.map((sample) => (
              <div key={sample.id} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm hover:border-indigo-400 dark:hover:border-indigo-600 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100 truncate">{sample.name}</span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300">Sample</span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">{sample.description}</p>
                </div>
                <div className="mt-5 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <span className="text-xs font-mono text-slate-400">{Math.max(1, Math.round(sample.size_bytes / 1024))} KB</span>
                  <button onClick={() => handleSelectSample(sample.id)} className="inline-flex items-center space-x-1 text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700">
                    <span>Launch EDA</span><ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Available Datasets Table (Real API Data) */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-indigo-500" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Your datasets
            </h3>
          </div>
          <Link
            to="/upload"
            className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            + Upload New Dataset
          </Link>
        </div>

        {datasets.length === 0 ? (
          <div className="text-center py-6 text-xs text-slate-400">
            You have no datasets yet. Upload a CSV, TSV or XLSX file, or launch a sample above.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800 text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800 font-semibold text-slate-500 uppercase text-[10px]">
                <tr>
                  <th className="px-4 py-2 text-left">Dataset Name</th>
                  <th className="px-4 py-2 text-left">Format</th>
                  <th className="px-4 py-2 text-left">Dimensions</th>
                  <th className="px-4 py-2 text-left">Created</th>
                  <th className="px-4 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {datasets.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="px-4 py-2.5 font-mono font-medium text-slate-900 dark:text-slate-100">
                      {d.name}
                    </td>
                    <td className="px-4 py-2.5 uppercase font-mono">{d.file_format}</td>
                    <td className="px-4 py-2.5 font-mono">{(d.row_count ?? 0).toLocaleString()}r × {d.column_count ?? 0}c</td>
                    <td className="px-4 py-2.5 text-slate-400">{d.created_at?.slice(0, 10)}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={async () => {
                          await selectDataset(d.id);
                          navigate('/overview');
                        }}
                        className="text-indigo-600 hover:underline font-semibold"
                      >
                        Inspect &rarr;
                      </button>
                      <button
                        onClick={() => setPendingDelete(d.id)}
                        aria-label={`Delete ${d.name}`}
                        className="ml-3 text-slate-400 hover:text-red-600 font-semibold"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {actionError && <p role="alert" className="text-xs text-red-600">{actionError}</p>}
      <Modal isOpen={!!pendingDelete} onClose={() => setPendingDelete(null)} title="Delete this dataset?" maxWidth="sm">
        <p className="text-xs text-slate-600 dark:text-slate-300">
          The dataset, its stored file, its sessions, results and reports will be permanently removed. This cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={() => setPendingDelete(null)} className="px-3 py-1.5 rounded-lg text-xs bg-slate-100 dark:bg-slate-800">Cancel</button>
          <button onClick={confirmDelete} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-red-600 hover:bg-red-700">Delete</button>
        </div>
      </Modal>
    </div>
  );
};
