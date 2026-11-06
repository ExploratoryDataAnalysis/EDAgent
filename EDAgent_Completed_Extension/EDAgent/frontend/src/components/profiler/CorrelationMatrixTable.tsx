import React, { useState } from 'react';
import { Network, HelpCircle, AlertCircle, Sparkles } from 'lucide-react';
import { RelationshipAnalysis } from '../../types';

interface CorrelationMatrixTableProps {
  relationships?: RelationshipAnalysis;
}

export const CorrelationMatrixTable: React.FC<CorrelationMatrixTableProps> = ({ relationships }) => {
  const [method, setMethod] = useState<'pearson' | 'spearman'>('pearson');

  if (!relationships) return null;

  const corrObj = method === 'pearson' ? relationships.pearson : relationships.spearman;
  const columns = corrObj?.columns || [];
  const matrix = corrObj?.matrix || {};
  const associations = relationships.categorical_associations || [];
  const warnings = relationships.warnings || [];

  // Helper to get cell background color based on r value
  const getCellColor = (val: number | null | undefined, isDiagonal: boolean) => {
    if (isDiagonal) return 'bg-slate-100 dark:bg-slate-800 text-slate-400 font-bold';
    if (val === null || val === undefined) return 'bg-slate-50 dark:bg-slate-900 text-slate-400';
    if (val > 0.7) return 'bg-indigo-600 text-white font-bold';
    if (val > 0.4) return 'bg-indigo-100 dark:bg-indigo-950/80 text-indigo-800 dark:text-indigo-200 font-semibold';
    if (val > 0.1) return 'bg-indigo-50/60 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300';
    if (val < -0.7) return 'bg-rose-600 text-white font-bold';
    if (val < -0.4) return 'bg-rose-100 dark:bg-rose-950/80 text-rose-800 dark:text-rose-200 font-semibold';
    if (val < -0.1) return 'bg-rose-50/60 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300';
    return 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400';
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-6">
      {/* Header with Pearson / Spearman Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center space-x-2">
          <Network className="w-4 h-4 text-indigo-500" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Pairwise Relationships & Correlation Matrix
          </h3>
        </div>

        <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
          <button
            onClick={() => setMethod('pearson')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
              method === 'pearson'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs'
                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            Pearson (Linear)
          </button>
          <button
            onClick={() => setMethod('spearman')}
            disabled={!relationships.spearman}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
              method === 'spearman'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs'
                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 disabled:opacity-40'
            }`}
          >
            Spearman (Rank)
          </button>
        </div>
      </div>

      {/* Warnings if non-numeric columns were excluded */}
      {warnings.length > 0 && (
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-xs text-slate-600 dark:text-slate-400 space-y-1">
          {warnings.map((w, idx) => (
            <p key={idx} className="flex items-center space-x-1.5">
              <span className="text-indigo-500 font-bold">•</span>
              <span>{w}</span>
            </p>
          ))}
        </div>
      )}

      {/* Correlation Matrix Table */}
      {columns.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
          <table className="min-w-full text-xs text-center border-collapse">
            <thead className="bg-slate-50 dark:bg-slate-800 font-semibold text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-mono">Measure</th>
                {columns.map((col) => (
                  <th key={col} className="px-3 py-2 font-mono whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
              {columns.map((rowCol) => (
                <tr key={rowCol}>
                  <td className="px-3 py-2 font-semibold text-left text-slate-800 dark:text-slate-200 bg-slate-50/50 dark:bg-slate-800/40">
                    {rowCol}
                  </td>
                  {columns.map((colCol) => {
                    const isDiag = rowCol === colCol;
                    const val = matrix[rowCol]?.[colCol];
                    const colorClass = getCellColor(val, isDiag);

                    return (
                      <td
                        key={colCol}
                        className={`px-3 py-2 transition-colors ${colorClass}`}
                        title={`${rowCol} vs ${colCol}: ${val !== null && val !== undefined ? val : 'N/A'}`}
                      >
                        {val !== null && val !== undefined ? val.toFixed(3) : '-'}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-6 text-center text-slate-400 text-xs">
          No continuous numeric measures suitable for correlation calculation in this dataset.
        </div>
      )}

      {/* Categorical Associations (Cramér's V) */}
      {associations.length > 0 && (
        <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
          <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider flex items-center space-x-1.5">
            <span>Categorical Associations (Cramér's V)</span>
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {associations.map((assoc, idx) => (
              <div
                key={idx}
                className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs flex items-center justify-between"
              >
                <div>
                  <p className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                    {assoc.column_x} × {assoc.column_y}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    p-value: {assoc.p_value < 0.001 ? '< 0.001' : assoc.p_value.toFixed(4)}
                  </p>
                </div>
                <div className="text-right">
                  <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                    V = {assoc.cramers_v.toFixed(3)}
                  </span>
                  <p className="text-[10px] text-slate-400">
                    {assoc.cramers_v > 0.5 ? 'Strong' : assoc.cramers_v > 0.25 ? 'Moderate' : 'Weak'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CorrelationMatrixTable;
