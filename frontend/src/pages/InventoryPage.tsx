import React, { useState } from 'react';
import { Table2, Database, Eye, Layers } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { ColumnInventoryTable } from '../components/profiler/ColumnInventoryTable';
import { Tabs } from '../components/ui/Tabs';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

export const InventoryPage: React.FC = () => {
  const { profile, preview, isLoading } = useDataset();
  const [activeTab, setActiveTab] = useState<'head' | 'tail' | 'sample'>('head');

  if (isLoading) {
    return <LoadingSpinner text="Loading column inventory..." className="h-96" />;
  }

  if (!profile) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-16 text-center space-y-4">
        <Table2 className="w-12 h-12 text-slate-300 mx-auto" />
        <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
          No Dataset Selected
        </h3>
        <p className="text-xs text-slate-500">
          Load a sample benchmark or upload a dataset to view its column inventory and data preview.
        </p>
      </div>
    );
  }

  const columns = profile.columns;
  const measuresCount = columns.filter((c) => (c.semantic_role || c.semanticRole) === 'measure').length;
  const categoriesCount = columns.filter((c) => (c.semantic_role || c.semanticRole) === 'category').length;
  const idCount = columns.filter((c) => (c.semantic_role || c.semanticRole) === 'identifier').length;
  const dateCount = columns.filter((c) => (c.semantic_role || c.semanticRole) === 'datetime').length;

  const records =
    activeTab === 'head'
      ? preview?.head_records || []
      : activeTab === 'tail'
      ? preview?.tail_records || []
      : preview?.sample_records || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Top Header Card with Feature Summary Pills */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div>
          <h2 className="text-xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
            Column Inventory & Feature Schema
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Storage data types, inferred semantic roles, uniqueness rates, and safe sample values.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            {measuresCount} Measures
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
            {categoriesCount} Categories
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            {idCount} Identifiers
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            {dateCount} Datetime
          </span>
        </div>
      </div>

      {/* Main Interactive Inventory Table */}
      <ColumnInventoryTable columns={columns} />

      {/* Raw Tabular Ingestion Preview */}
      {preview && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center space-x-2">
              <Eye className="w-4 h-4 text-indigo-500" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Dataset Record Preview ({preview.total_rows} Total Rows)
              </h3>
            </div>

            <Tabs
              variant="pills"
              activeTab={activeTab}
              onChange={(id) => setActiveTab(id as any)}
              tabs={[
                { id: 'head', label: 'First 10 Rows (Head)', badge: preview.head_records.length },
                { id: 'tail', label: 'Last 10 Rows (Tail)', badge: preview.tail_records.length },
                { id: 'sample', label: 'Random Sample Reservoir', badge: preview.sample_records.length },
              ]}
            />
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800 max-h-96">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800 text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800 font-semibold text-slate-500 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-mono">#</th>
                  {preview.column_names.map((col) => (
                    <th key={col} className="px-3 py-2 text-left font-mono whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {records.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="px-3 py-2 font-mono text-slate-400">{idx + 1}</td>
                    {preview.column_names.map((col) => (
                      <td key={col} className="px-3 py-2 font-mono text-slate-800 dark:text-slate-200 whitespace-nowrap">
                        {String(r[col] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
