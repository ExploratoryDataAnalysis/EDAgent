import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Archive, Database, Download, FileJson, FileSpreadsheet } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { exportService, sessionService } from '../services/api';
import { AnalysisResult, SessionDetail, SessionSummary } from '../types';
import { EmptyState } from '../components/ui/EmptyState';

const btn = 'inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 hover:text-indigo-700 transition-colors disabled:opacity-50';

/** Every file the app can produce, in one place. All downloads are real files from the backend. */
export const ExportCentrePage: React.FC = () => {
  const navigate = useNavigate();
  const { activeDataset, session } = useDataset();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!activeDataset) return;
    sessionService.list(activeDataset.id)
      .then((l) => { setSessions(l); setSessionId((c) => c || session?.id || l[0]?.id || ''); })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load sessions'));
  }, [activeDataset?.id, session?.id]);

  useEffect(() => {
    setDetail(null);
    if (sessionId) sessionService.get(sessionId).then(setDetail).catch((e) => setError(e instanceof Error ? e.message : 'Could not load session'));
  }, [sessionId]);

  /** Wraps a download so failures show up in the UI and double clicks are ignored. */
  const dl = async (key: string, fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(key);
    setError(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : 'Download failed'); } finally { setBusy(null); }
  };

  if (!activeDataset) {
    return <div className="max-w-3xl mx-auto p-10"><EmptyState icon={<Database className="w-8 h-8" />} title="No dataset selected" description="Select a dataset to export its profile and results." actionText="Go to upload" onAction={() => navigate('/upload')} /></div>;
  }

  const results: AnalysisResult[] = (detail?.turns ?? []).flatMap((t) => (t.result ? [t.result] : []));

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <h1 className="text-lg font-bold text-slate-900 dark:text-white">Export centre</h1>
      {error && <div role="alert" className="text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2">{error}</div>}

      <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Dataset profile</h2>
        <p className="text-xs text-slate-500 mt-1 mb-3">The computed profile of <b>{activeDataset.name}</b>: overview, column inventory, missing values, duplicates, quality warnings and correlations. Your original data is never modified.</p>
        <div className="flex flex-wrap gap-2">
          <button className={btn} disabled={!!busy} onClick={() => dl('p-x', () => exportService.profile(activeDataset.id, 'xlsx'))}><FileSpreadsheet className="w-3.5 h-3.5" /><span>Profile (.xlsx)</span></button>
          <button className={btn} disabled={!!busy} onClick={() => dl('p-j', () => exportService.profile(activeDataset.id, 'json'))}><FileJson className="w-3.5 h-3.5" /><span>Profile (.json)</span></button>
        </div>
      </section>

      <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">Analysis results</h2>
          <div className="flex items-center gap-2">
            <select aria-label="Session" value={sessionId} onChange={(e) => setSessionId(e.target.value)} className="px-3 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700">
              {sessions.length === 0 && <option value="">No sessions yet</option>}
              {sessions.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
            <button className={btn} disabled={!sessionId || !!busy} onClick={() => dl('s', () => exportService.sessionBundle(sessionId))}><Archive className="w-3.5 h-3.5" /><span>Whole session (.zip)</span></button>
          </div>
        </div>

        {sessionId && detail && results.length === 0 && <p className="text-xs text-slate-400">This session has no completed analyses yet. Run one in the <Link to="/workspace" className="underline">workspace</Link> or chat.</p>}

        <ul className="space-y-3">
          {results.map((r) => (
            <li key={r.id} className="rounded-xl border border-slate-200 dark:border-slate-800 p-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{r.operation.replace(/_/g, ' ')} <span className="font-normal text-slate-400">— {r.columns_used.join(', ') || 'all columns'}</span></p>
                <div className="flex flex-wrap gap-1.5">
                  <button className={btn} disabled={!!busy} onClick={() => dl(`m-${r.id}`, () => exportService.metadata(r.id))}><FileJson className="w-3 h-3" /><span>Metadata</span></button>
                  <button className={btn} disabled={!!busy} onClick={() => dl(`py-${r.id}`, () => exportService.code(r.id, 'py'))}><Download className="w-3 h-3" /><span>.py</span></button>
                  <button className={btn} disabled={!!busy} onClick={() => dl(`nb-${r.id}`, () => exportService.code(r.id, 'ipynb'))}><Download className="w-3 h-3" /><span>.ipynb</span></button>
                  <button className={btn} disabled={!!busy} onClick={() => dl(`b-${r.id}`, () => exportService.resultBundle(r.id))}><Archive className="w-3 h-3" /><span>Bundle</span></button>
                </div>
              </div>
              {r.charts.map((c) => (
                <div key={c.id} className="flex flex-wrap items-center gap-2 text-[11px] text-slate-600 dark:text-slate-300">
                  <span className="w-48 truncate" title={c.title}>Chart: {c.title}</span>
                  {(['png', 'svg', 'html'] as const).map((f) => <button key={f} className={btn} disabled={!!busy} onClick={() => dl(`c-${c.id}-${f}`, () => exportService.chart(r.id, c.id, f))}>{f.toUpperCase()}</button>)}
                </div>
              ))}
              {r.tables.map((t, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2 text-[11px] text-slate-600 dark:text-slate-300">
                  <span className="w-48 truncate" title={t.name}>Table: {t.name}</span>
                  {(['csv', 'xlsx'] as const).map((f) => <button key={f} className={btn} disabled={!!busy} onClick={() => dl(`t-${r.id}-${i}-${f}`, () => exportService.table(r.id, i, f))}>{f.toUpperCase()}</button>)}
                </div>
              ))}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Reports</h2>
        <p className="text-xs text-slate-500 mt-1 mb-3">PDF and HTML reports are generated in the report builder.</p>
        <Link to="/reports" className={btn}><span>Open report builder</span></Link>
      </section>
    </div>
  );
};

export default ExportCentrePage;
