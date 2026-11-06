import React from 'react';

/** Formats a cell for display without altering the underlying value. */
export function formatCell(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return String(v);
    if (Number.isInteger(v)) return v.toLocaleString();
    return Math.abs(v) >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(Number(v.toPrecision(5)));
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

interface DataTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  maxHeight?: string;
  caption?: string;
}

/** Compact scrollable table with a sticky header. Values are rendered as text (never as HTML). */
export const DataTable: React.FC<DataTableProps> = ({ columns, rows, maxHeight = '22rem', caption }) => (
  <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-auto" style={{ maxHeight }}>
    <table className="min-w-full text-xs">
      {caption && <caption className="sr-only">{caption}</caption>}
      <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
        <tr>
          {columns.map((c) => (
            <th key={c} className="px-3 py-2 text-left font-semibold whitespace-nowrap border-b border-slate-200 dark:border-slate-700">
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
        {rows.length === 0 && (
          <tr>
            <td colSpan={Math.max(columns.length, 1)} className="px-3 py-6 text-center text-slate-400">
              No rows
            </td>
          </tr>
        )}
        {rows.map((r, i) => (
          <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
            {columns.map((c) => (
              <td key={c} className="px-3 py-1.5 whitespace-nowrap max-w-[22rem] truncate" title={formatCell(r[c])}>
                {formatCell(r[c])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default DataTable;
