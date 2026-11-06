import React from 'react';
import { AlertTriangle, AlertCircle, Info, ShieldCheck } from 'lucide-react';
import { QualityWarning } from '../../types';
import { Badge } from '../ui/Badge';

interface QualityWarningsPanelProps {
  warnings: QualityWarning[];
}

export const QualityWarningsPanel: React.FC<QualityWarningsPanelProps> = ({ warnings }) => {
  if (!warnings || warnings.length === 0) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 flex items-center space-x-4">
        <div className="p-3 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
          <ShieldCheck className="w-6 h-6" />
        </div>
        <div>
          <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            No Critical Quality Anomalies Detected
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Dataset passes standard tests for constant columns, infinite numbers, and invalid dates.
          </p>
        </div>
      </div>
    );
  }

  const highCount = warnings.filter((w) => w.severity === 'high').length;
  const mediumCount = warnings.filter((w) => w.severity === 'medium').length;
  const lowCount = warnings.filter((w) => w.severity === 'low').length;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      {/* Header with severity badge counts */}
      <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Data Quality & Anomaly Checks
          </h3>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
            {warnings.length} {warnings.length === 1 ? 'Notice' : 'Notices'}
          </span>
        </div>

        <div className="flex items-center space-x-2">
          {highCount > 0 && <Badge severity="high">{highCount} High</Badge>}
          {mediumCount > 0 && <Badge severity="medium">{mediumCount} Medium</Badge>}
          {lowCount > 0 && <Badge severity="low">{lowCount} Low</Badge>}
        </div>
      </div>

      {/* Warning Items List */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-72 overflow-y-auto">
        {warnings.map((w, idx) => {
          const Icon =
            w.severity === 'high'
              ? AlertCircle
              : w.severity === 'medium'
              ? AlertTriangle
              : Info;

          const iconColor =
            w.severity === 'high'
              ? 'text-rose-500 bg-rose-50 dark:bg-rose-950/40'
              : w.severity === 'medium'
              ? 'text-amber-500 bg-amber-50 dark:bg-amber-950/40'
              : 'text-blue-500 bg-blue-50 dark:bg-blue-950/40';

          return (
            <div
              key={idx}
              className="p-4 flex items-start space-x-3.5 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
            >
              <div className={`p-2 rounded-xl shrink-0 ${iconColor}`}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  {w.column && (
                    <span className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                      {w.column}
                    </span>
                  )}
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400 capitalize">
                    {w.check_type || w.checkType}
                  </span>
                  <Badge severity={w.severity}>{w.severity}</Badge>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                  {w.message}
                </p>
              </div>
              {(w.affected_count !== undefined && w.affected_count !== null) ||
              (w.affectedCount !== undefined && w.affectedCount !== null) ? (
                <span className="text-[11px] font-mono font-medium text-slate-400 dark:text-slate-500 whitespace-nowrap">
                  {w.affected_count ?? w.affectedCount} rows
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};
