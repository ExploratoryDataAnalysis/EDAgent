import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Database,
  Layers,
  FileText,
  AlertTriangle,
  Copy,
  Clock,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Key,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { MetricCard } from '../components/ui/MetricCard';
import { Badge } from '../components/ui/Badge';
import { QualityWarningsPanel } from '../components/profiler/QualityWarningsPanel';
import { MissingnessChart } from '../components/profiler/MissingnessChart';
import { ColumnInventoryTable } from '../components/profiler/ColumnInventoryTable';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { profile, activeDataset, isLoading } = useDataset();

  if (isLoading) {
    return <LoadingSpinner text="Computing deterministic statistical profile..." className="h-96" />;
  }

  if (!profile) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-16 text-center space-y-4">
        <Database className="w-12 h-12 text-slate-300 mx-auto" />
        <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
          No Profile Loaded
        </h3>
        <p className="text-xs text-slate-500">
          Upload a dataset or select a sample benchmark to inspect automated EDA profiling.
        </p>
      </div>
    );
  }

  const overview = profile.overview;
  const missingness = profile.missingness;
  const duplicates = profile.duplicates;
  const warnings = profile.quality_warnings || profile.qualityWarnings || [];
  const suggestions = profile.suggested_analyses || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Top Header Card */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center space-x-2.5">
            <h2 className="text-xl font-black text-slate-900 dark:text-slate-100 tracking-tight">
              {overview.dataset_name || overview.datasetName || activeDataset?.name}
            </h2>
            {overview.selected_sheet && (
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                Sheet: {overview.selected_sheet}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Deterministic baseline profile computed in{' '}
            <strong className="text-slate-700 dark:text-slate-300 font-mono">
              {overview.profiling_duration_seconds || overview.load_time_seconds || 0.015}s
            </strong>{' '}
            • Zero AI hallucination
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate('/workspace')}
            className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-all"
          >
            <span>Open in Workspace</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Primary KPI Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <MetricCard
          title="Total Rows"
          value={(overview.total_rows ?? overview.totalRows ?? 0).toLocaleString()}
          subtitle="Observations"
          icon={<Database className="w-4 h-4 text-indigo-500" />}
        />
        <MetricCard
          title="Total Columns"
          value={overview.total_columns ?? overview.totalColumns ?? 0}
          subtitle="Features"
          icon={<Layers className="w-4 h-4 text-purple-500" />}
        />
        <MetricCard
          title="Missing Cells"
          value={`${missingness.overall_missing_percentage ?? missingness.overallMissingPercentage ?? 0}%`}
          subtitle={`${missingness.missing_cells ?? missingness.missingCells ?? 0} cells`}
          icon={<AlertTriangle className="w-4 h-4 text-amber-500" />}
          badge={
            (missingness.overall_missing_percentage || 0) > 10 ? (
              <Badge severity="medium">Review</Badge>
            ) : (
              <Badge variant="success">Clean</Badge>
            )
          }
        />
        <MetricCard
          title="Exact Duplicates"
          value={duplicates.exact_duplicate_rows_count ?? duplicates.exactDuplicateRowsCount ?? 0}
          subtitle={`${duplicates.exact_duplicate_percentage ?? duplicates.exactDuplicatePercentage ?? 0}%`}
          icon={<Copy className="w-4 h-4 text-cyan-500" />}
        />
        <MetricCard
          title="Memory Footprint"
          value={`${Math.round((overview.memory_estimate_bytes || 2048) / 1024)} KB`}
          subtitle="In-Memory Estimate"
          icon={<Clock className="w-4 h-4 text-emerald-500" />}
        />
        <MetricCard
          title="Quality Notices"
          value={warnings.length}
          subtitle="Automated checks"
          icon={<TrendingUp className="w-4 h-4 text-rose-500" />}
          badge={warnings.length > 0 ? <Badge severity="low">Active</Badge> : <Badge variant="success">Passed</Badge>}
        />
      </div>

      {/* Quality Warnings Panel */}
      <QualityWarningsPanel warnings={warnings} />

      {/* Missingness & Duplicates Analysis Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Missingness Chart */}
        <MissingnessChart missingness={missingness} />

        {/* Duplicate Analysis & Candidate Keys */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <Copy className="w-4 h-4 text-indigo-500" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Exact Duplicate Rows & Key Integrity
                </h3>
              </div>
              <span className="text-xs font-mono font-semibold text-slate-500">
                {duplicates.exact_duplicate_rows_count ?? duplicates.exactDuplicateRowsCount ?? 0} duplicate row(s)
              </span>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <p className="text-slate-600 dark:text-slate-400">
                Exact duplicate row detection checks for identical row tuples across all features. Repeated IDs or similar-looking records with differing feature values are preserved as distinct rows.
              </p>

              {duplicates.candidate_duplicate_keys && duplicates.candidate_duplicate_keys.length > 0 && (
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 space-y-1.5">
                  <div className="flex items-center space-x-1.5 text-indigo-600 dark:text-indigo-400 font-semibold">
                    <Key className="w-3.5 h-3.5" />
                    <span>Candidate Primary Keys (100% Unique & Non-Null)</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {duplicates.candidate_duplicate_keys.map((k) => (
                      <span
                        key={k}
                        className="px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 font-mono font-bold text-slate-800 dark:text-slate-200"
                      >
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Sample Duplicate Preview if any */}
              {duplicates.duplicate_rows_sample && duplicates.duplicate_rows_sample.length > 0 && (
                <div className="mt-3">
                  <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                    Duplicate Row Example
                  </h4>
                  <pre className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-mono text-[11px] overflow-x-auto">
                    {JSON.stringify(duplicates.duplicate_rows_sample[0].row, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400">
            Rule compliance: Never automatically deletes duplicate rows without explicit user instruction.
          </div>
        </div>
      </div>

      {/* Suggested Analyses (Deterministic Recommendations) */}
      {suggestions.length > 0 && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4">
          <div className="flex items-center space-x-2.5">
            <Sparkles className="w-5 h-5 text-indigo-500" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Deterministic Suggested Analyses
            </h3>
            <span className="text-[11px] text-slate-400">
              Synthesized from observed missingness, outliers, and role associations
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {suggestions.map((s, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-indigo-600 bg-slate-50/50 dark:bg-slate-800/30 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      {s.title}
                    </span>
                    <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded uppercase bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
                      {s.operation}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                    {s.description}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-2 italic">
                    Rationale: {s.rationale}
                  </p>
                </div>

                <div className="mt-4 pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <div className="flex items-center space-x-1">
                    {s.columns.map((c) => (
                      <span key={c} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                        {c}
                      </span>
                    ))}
                  </div>
                  <button
                    onClick={() => navigate('/workspace')}
                    className="inline-flex items-center space-x-1 text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline"
                  >
                    <span>Execute</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Column Inventory Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Column Inventory & Inferred Semantic Roles
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Click any column to inspect full descriptive statistics, quartiles, or categorical frequency tables.
            </p>
          </div>
        </div>

        <ColumnInventoryTable columns={profile.columns} />
      </div>
    </div>
  );
};
