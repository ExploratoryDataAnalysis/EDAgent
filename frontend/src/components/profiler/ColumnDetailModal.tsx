import React from 'react';
import { Modal } from '../ui/Modal';
import { Badge } from '../ui/Badge';
import { ColumnProfile } from '../../types';
import { PlotlyChart } from '../charts/PlotlyChart';

interface ColumnDetailModalProps {
  column: ColumnProfile | null;
  onClose: () => void;
}

export const ColumnDetailModal: React.FC<ColumnDetailModalProps> = ({ column, onClose }) => {
  if (!column) return null;

  const num = column.numeric_summary || column.numericSummary;
  const cat = column.categorical_summary || column.categoricalSummary;
  const dt = column.date_summary || column.dateSummary;
  const role = column.semantic_role || column.semanticRole || 'unknown';

  return (
    <Modal
      isOpen={!!column}
      onClose={onClose}
      title={column.name}
      subtitle={`Storage: ${column.storage_dtype || column.storageDtype} • Semantic Type: ${column.inferred_type || column.inferredType}`}
      maxWidth="2xl"
    >
      <div className="space-y-6">
        {/* Role & Confidence Pill Row */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl">
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-500 dark:text-slate-400">Inferred Role:</span>
            <Badge role={role}>{role.toUpperCase()}</Badge>
            <span className="text-xs font-mono text-slate-500">
              Confidence: {Math.round((column.role_confidence || column.roleConfidence || 1) * 100)}%
            </span>
          </div>

          <div className="text-xs text-slate-500 dark:text-slate-400">
            Distinct: <strong className="text-slate-800 dark:text-slate-200">{column.distinct_count || column.distinctCount}</strong> ({column.is_unique || column.isUnique ? '100% Unique' : 'Non-unique'})
          </div>
        </div>

        {/* Role Rationale if present */}
        {column.role_uncertainty_reason && (
          <div className="text-xs p-3 rounded-lg bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/40 text-indigo-800 dark:text-indigo-300">
            <strong>Role Inference Note:</strong> {column.role_uncertainty_reason}
          </div>
        )}

        {/* Numeric Details */}
        {num && (
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Descriptive Statistics
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Mean</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.mean?.toLocaleString() ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Std Dev</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.std?.toLocaleString() ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Median</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.median?.toLocaleString() ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">IQR</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.iqr?.toLocaleString() ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Min</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.min?.toLocaleString() ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Max</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.max?.toLocaleString() ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Skewness</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.skewness ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Kurtosis</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{num.kurtosis ?? '-'}</p>
              </div>
            </div>

            {/* Special Values Flags */}
            <div className="mt-3 flex items-center space-x-4 text-xs text-slate-500">
              <span>Zero count: <strong className="text-slate-700 dark:text-slate-300 font-mono">{num.zeros_count || num.zerosCount || 0}</strong> ({num.zeros_percentage || num.zerosPercentage || 0}%)</span>
              <span>Infinite count: <strong className="text-slate-700 dark:text-slate-300 font-mono">{num.infinite_count || num.infiniteCount || 0}</strong></span>
              <span>NaN count: <strong className="text-slate-700 dark:text-slate-300 font-mono">{num.nan_count || num.nanCount || 0}</strong></span>
            </div>
          </div>
        )}

        {/* Categorical Details */}
        {cat && cat.top_values && cat.top_values.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Most Frequent Categories
            </h4>
            <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
              <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-slate-500">Category Value</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-500">Count</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-500">Percentage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {cat.top_values.map((v, i) => (
                    <tr key={i}>
                      <td className="px-3 py-1.5 font-mono text-slate-800 dark:text-slate-200">{v.value}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{v.count}</td>
                      <td className="px-3 py-1.5 text-right font-mono font-medium text-indigo-600 dark:text-indigo-400">{v.percentage}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Date Details */}
        {dt && (
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Datetime Span & Parsing
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Earliest Date</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{dt.min_date?.slice(0, 10) ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Latest Date</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{dt.max_date?.slice(0, 10) ?? '-'}</p>
              </div>
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
                <span className="text-slate-400">Span (Days)</span>
                <p className="font-mono font-bold text-slate-800 dark:text-slate-100 mt-0.5">{dt.date_range_days ?? '-'}</p>
              </div>
            </div>
          </div>
        )}

        {/* Sample Values */}
        {column.sample_values && column.sample_values.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Sample Values
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {column.sample_values.map((s, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 font-mono text-xs text-slate-700 dark:text-slate-300"
                >
                  {String(s)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
