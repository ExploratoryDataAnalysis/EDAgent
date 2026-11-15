import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Database } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { useAuth } from '../context/AuthContext';
import { Modal } from '../components/ui/Modal';
import { CountySampleLink } from './SamplePage';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
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
      <header className="space-y-4">
        <h1 className="text-3xl font-bold">Dataset analyser</h1>
        <p>Choose a dataset, run a manual analysis and export the results.</p>
        <nav className="flex flex-wrap gap-4 text-sm font-medium text-indigo-700 dark:text-indigo-300">
          <Link className="underline" to="/upload">Upload tabular dataset</Link>
          <Link className="underline" to="/workspace">Open analysis workspace</Link>
          <Link className="underline" to="/analyser/sample/teaching">Open the invented teaching dataset</Link>
          <CountySampleLink />
          <Link className="underline" to="/">Back to the investigation</Link>
        </nav>
      </header>

      {/* Sample datasets (served by the backend) */}
      {!user?.guest && <div>
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
      </div>}

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
