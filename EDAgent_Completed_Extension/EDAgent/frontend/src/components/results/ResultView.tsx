import React, { useState } from 'react';
import { AlertTriangle, Code2, Download, FileJson, Info, Package } from 'lucide-react';
import { AnalysisResult } from '../../types';
import { PlotlyChart } from '../charts/PlotlyChart';
import { Badge } from '../ui/Badge';
import { DataTable, formatCell } from './DataTable';
import { exportService } from '../../services/api';

const btn =
  'inline-flex items-center space-x-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 hover:text-indigo-700 transition-colors';

/** Runs a download and reports failure instead of throwing into the void. */
function useDownload() {
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<void>) => {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    }
  };
  return { error, run };
}

interface Props {
  result: AnalysisResult;
  /** Hide the heading (when the caller already shows one). */
  hideHeader?: boolean;
  /** Hide export buttons (for previews). */
  hideExports?: boolean;
}

/**
 * Renders one structured analysis result: headline numbers, charts, tables, warnings,
 * methodology and reproducible code. Every number shown here came from the backend engine.
 */
export const ResultView: React.FC<Props> = ({ result, hideHeader, hideExports }) => {
  const { error, run } = useDownload();
  const [showCode, setShowCode] = useState(false);

  const scalarMetrics = Object.entries(result.metrics || {}).filter(([, v]) => v === null || ['number', 'string', 'boolean'].includes(typeof v));
  const complexMetrics = Object.entries(result.metrics || {}).filter(([, v]) => v !== null && typeof v === 'object');

  return (
    <div className="space-y-4">
      {!hideHeader && (
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">{result.operation.replace(/_/g, ' ')}</h3>
          {result.is_sampled && (
            <Badge variant="warning" size="sm" title={`Computed on a ${result.sampling_method || 'random'} sample`}>
              Sampled{result.sample_size ? ` (${result.sample_size.toLocaleString()} rows)` : ''}
            </Badge>
          )}
          {result.is_approximate && <Badge variant="warning" size="sm">Approximate</Badge>}
          {result.execution.cache_hit && <Badge variant="outline" size="sm">Cached</Badge>}
        </div>
      )}

      {result.summary_text && <p className="text-sm text-slate-700 dark:text-slate-300">{result.summary_text}</p>}

      {scalarMetrics.length > 0 && (
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {scalarMetrics.map(([k, v]) => (
            <div key={k} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-400 truncate" title={k}>{k.replace(/_/g, ' ')}</dt>
              <dd className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate" title={formatCell(v)}>{formatCell(v)}</dd>
            </div>
          ))}
        </dl>
      )}

      {complexMetrics.map(([k, v]) => (
        <details key={k} className="rounded-xl border border-slate-200 dark:border-slate-800 px-3 py-2">
          <summary className="text-xs font-semibold text-slate-600 dark:text-slate-300 cursor-pointer">{k.replace(/_/g, ' ')}</summary>
          <pre className="mt-2 text-[11px] overflow-auto max-h-64 text-slate-600 dark:text-slate-400">{JSON.stringify(v, null, 2)}</pre>
        </details>
      ))}

      {result.charts.map((c) => (
        <div key={c.id} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
            <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-200">{c.title}</h4>
            {!hideExports && (
              <div className="flex gap-1">
                {(['png', 'svg', 'html'] as const).map((f) => (
                  <button key={f} className={btn} onClick={() => run(() => exportService.chart(result.id, c.id, f))}>
                    <Download className="w-3 h-3" /><span>{f.toUpperCase()}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <PlotlyChart data={c.spec.data} layout={c.spec.layout} className="w-full min-h-[320px]" style={{ width: '100%', height: '360px' }} />
        </div>
      ))}

      {result.tables.map((t, i) => (
        <div key={`${t.name}-${i}`} className="space-y-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-200">
              {t.name}{' '}
              <span className="font-normal text-slate-400">
                {t.truncated ? `(showing ${t.rows.length.toLocaleString()} of ${t.total_rows.toLocaleString()} rows)` : `(${t.total_rows.toLocaleString()} rows)`}
              </span>
            </h4>
            {!hideExports && (
              <div className="flex gap-1">
                <button className={btn} onClick={() => run(() => exportService.table(result.id, i, 'csv'))}><Download className="w-3 h-3" /><span>CSV</span></button>
                <button className={btn} onClick={() => run(() => exportService.table(result.id, i, 'xlsx'))}><Download className="w-3 h-3" /><span>XLSX</span></button>
              </div>
            )}
          </div>
          <DataTable columns={t.columns} rows={t.rows} caption={t.name} />
        </div>
      ))}

      {result.warnings.length > 0 && (
        <ul className="space-y-1" aria-label="Warnings">
          {result.warnings.map((w, i) => (
            <li key={i} className="flex items-start space-x-2 text-xs rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /><span>{w}</span>
            </li>
          ))}
        </ul>
      )}

      <details className="rounded-xl border border-slate-200 dark:border-slate-800 px-3 py-2">
        <summary className="text-xs font-semibold text-slate-600 dark:text-slate-300 cursor-pointer flex items-center inline-flex space-x-1">
          <Info className="w-3.5 h-3.5" /><span>Methodology &amp; data used</span>
        </summary>
        <div className="mt-2 space-y-2 text-xs text-slate-600 dark:text-slate-400">
          <p>{result.methodology}</p>
          <p>
            Rows examined: <b>{result.records_examined.toLocaleString()}</b> · used: <b>{result.records_used.toLocaleString()}</b> · excluded:{' '}
            <b>{result.records_excluded.toLocaleString()}</b>. Missing values: {result.missing_value_handling}.
          </p>
          {result.exclusions.length > 0 && (
            <ul className="list-disc pl-5">
              {result.exclusions.map((e, i) => (
                <li key={i}>{e.count.toLocaleString()} rows — {e.reason}{e.column ? ` (${e.column})` : ''}</li>
              ))}
            </ul>
          )}
          <p>Columns: {result.columns_used.join(', ') || '—'} · engine {result.execution.engine} · {result.execution.time_ms} ms · seed {result.execution.seed}</p>
        </div>
      </details>

      {result.interpretation && (
        <div className="text-xs rounded-lg bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900 text-slate-700 dark:text-slate-300 px-3 py-2">
          <b>Interpretation:</b> {result.interpretation}
        </div>
      )}

      {!hideExports && (
        <div className="flex flex-wrap items-center gap-1.5">
          <button className={btn} onClick={() => setShowCode((s) => !s)}><Code2 className="w-3 h-3" /><span>{showCode ? 'Hide code' : 'Show code'}</span></button>
          <button className={btn} onClick={() => run(() => exportService.metadata(result.id))}><FileJson className="w-3 h-3" /><span>Metadata</span></button>
          <button className={btn} onClick={() => run(() => exportService.code(result.id, 'py'))}><Download className="w-3 h-3" /><span>.py</span></button>
          <button className={btn} onClick={() => run(() => exportService.code(result.id, 'ipynb'))}><Download className="w-3 h-3" /><span>.ipynb</span></button>
          <button className={btn} onClick={() => run(() => exportService.resultBundle(result.id))}><Package className="w-3 h-3" /><span>Everything (.zip)</span></button>
        </div>
      )}
      {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
      {showCode && (
        <pre className="text-[11px] rounded-xl bg-slate-900 text-slate-100 p-3 overflow-auto max-h-80">{result.execution.code}</pre>
      )}
    </div>
  );
};

export default ResultView;
