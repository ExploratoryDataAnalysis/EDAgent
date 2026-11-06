import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, Download, FileText, Loader2, Trash2 } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { jobService, reportService, sessionService } from '../services/api';
import { ReportResponse, ReportSection, SessionDetail, SessionSummary } from '../types';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';

const SECTIONS: { id: ReportSection; label: string }[] = [
  { id: 'cover', label: '1. Cover & dataset identity' },
  { id: 'executive_summary', label: '2. Executive summary' },
  { id: 'dimensions_inventory', label: '3. Dimensions & inventory' },
  { id: 'types_roles', label: '4. Types & roles' },
  { id: 'descriptive_stats', label: '5. Descriptive statistics' },
  { id: 'missing_values', label: '6. Missing values' },
  { id: 'duplicates', label: '7. Duplicates' },
  { id: 'quality_findings', label: '8. Quality findings' },
  { id: 'univariate', label: '9. Univariate analysis' },
  { id: 'bivariate_multivariate', label: '10. Bivariate & multivariate' },
  { id: 'correlations', label: '11. Correlations' },
  { id: 'time_analysis', label: '12. Time analysis' },
  { id: 'user_analyses', label: '13. Your analyses' },
  { id: 'charts_tables', label: '14. Charts & tables' },
  { id: 'interpretation_limitations', label: '15. Interpretation & limitations' },
  { id: 'reproducibility', label: '16. Reproducibility' },
];

const label = 'block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1';
const field = 'w-full px-3 py-2 rounded-lg text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200';

export const ReportBuilderPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeDataset, session } = useDataset();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [title, setTitle] = useState('');
  const [format, setFormat] = useState<'pdf' | 'html'>('pdf');
  const [concise, setConcise] = useState(false);
  const [sections, setSections] = useState<Set<ReportSection>>(new Set(SECTIONS.map((s) => s.id)));
  const [picked, setPicked] = useState<Set<string> | null>(null); // null = all analyses
  const [reports, setReports] = useState<ReportResponse[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshReports = useCallback(async () => {
    if (!activeDataset) return;
    try {
      const all = await reportService.list();
      const ids = new Set(sessions.map((s) => s.id));
      setReports(sessions.length ? all.filter((r) => ids.has(r.session_id)) : all);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load reports');
    }
  }, [activeDataset?.id, sessions]);

  // Sessions of the active dataset; default to the active one.
  useEffect(() => {
    if (!activeDataset) return;
    sessionService.list(activeDataset.id).then((list) => {
      setSessions(list);
      setSessionId((cur) => cur || session?.id || list[0]?.id || '');
    }).catch((e) => setError(e instanceof Error ? e.message : 'Could not load sessions'));
    setTitle(`EDA report: ${activeDataset.name}`);
  }, [activeDataset?.id, session?.id]);

  useEffect(() => { refreshReports(); }, [refreshReports]);

  useEffect(() => {
    setPicked(null);
    setDetail(null);
    if (sessionId) sessionService.get(sessionId).then(setDetail).catch(() => setDetail(null));
  }, [sessionId]);

  const toggleSection = (id: ReportSection) =>
    setSections((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const analyses = (detail?.turns ?? []).filter((t) => t.result);

  const togglePicked = (rid: string) => {
    const all = new Set(analyses.map((t) => t.result!.id));
    const cur = picked ?? all;
    const next = new Set(cur);
    next.has(rid) ? next.delete(rid) : next.add(rid);
    setPicked(next);
  };

  const generate = async () => {
    if (!sessionId || sections.size === 0) return;
    setBusy(true);
    setError(null);
    setStatus('Queued…');
    try {
      const rep = await reportService.generate({
        session_id: sessionId, title: title.trim() || 'EDA report', format, concise_mode: concise,
        included_sections: SECTIONS.map((s) => s.id).filter((id) => sections.has(id)),
        included_result_ids: picked ? Array.from(picked) : null,
      });
      if (rep.job_id) {
        const job = await jobService.waitFor(rep.job_id, (j) => setStatus(`${j.status_message} (${Math.round(j.progress_percentage)}%)`));
        if (job.status !== 'SUCCESS') throw new Error(job.error_details || 'Report generation failed.');
      }
      setStatus('Report ready.');
      await refreshReports();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Report generation failed.');
      setStatus(null);
    } finally {
      setBusy(false);
    }
  };

  if (!activeDataset) {
    return <div className="max-w-3xl mx-auto p-10"><EmptyState icon={<Database className="w-8 h-8" />} title="No dataset selected" description="Select a dataset to build a report." actionText="Go to upload" onAction={() => navigate('/upload')} /></div>;
  }

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-[1fr_22rem] gap-6">
      <div className="space-y-5">
        <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 space-y-4">
          <h1 className="text-lg font-bold text-slate-900 dark:text-white">Report builder</h1>
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2"><label className={label}>Title</label><input className={field} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} /></div>
            <div>
              <label className={label}>Session (source of your analyses)</label>
              <select className={field} value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
                {sessions.length === 0 && <option value="">No sessions yet</option>}
                {sessions.map((s) => <option key={s.id} value={s.id}>{s.title} ({s.turn_count})</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className={label}>Format</label><select className={field} value={format} onChange={(e) => setFormat(e.target.value as 'pdf' | 'html')}><option value="pdf">PDF</option><option value="html">HTML</option></select></div>
              <div><label className={label}>Length</label><select className={field} value={concise ? 'c' : 'd'} onChange={(e) => setConcise(e.target.value === 'c')}><option value="d">Detailed</option><option value="c">Concise</option></select></div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Sections</h2>
            <div className="text-[11px] space-x-3">
              <button className="text-indigo-600" onClick={() => setSections(new Set(SECTIONS.map((s) => s.id)))}>All</button>
              <button className="text-indigo-600" onClick={() => setSections(new Set())}>None</button>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-x-4 gap-y-1.5">
            {SECTIONS.map((s) => (
              <label key={s.id} className="flex items-center space-x-2 text-xs text-slate-700 dark:text-slate-300">
                <input type="checkbox" checked={sections.has(s.id)} onChange={() => toggleSection(s.id)} /><span>{s.label}</span>
              </label>
            ))}
          </div>
        </section>

        {analyses.length > 0 && (
          <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white mb-1">Analyses to include</h2>
            <p className="text-[11px] text-slate-500 mb-3">AI-written explanations are labelled in the report and kept separate from computed findings.</p>
            <ul className="space-y-1.5 max-h-56 overflow-auto">
              {analyses.map((t) => (
                <li key={t.result!.id}>
                  <label className="flex items-center space-x-2 text-xs text-slate-700 dark:text-slate-300">
                    <input type="checkbox" checked={picked ? picked.has(t.result!.id) : true} onChange={() => togglePicked(t.result!.id)} />
                    <span className="truncate">{t.user_query} <span className="text-slate-400">— {t.result!.operation.replace(/_/g, ' ')}</span></span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="flex items-center gap-3">
          <button onClick={generate} disabled={busy || !sessionId || sections.size === 0}
            className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 shadow-lg shadow-indigo-600/25">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}<span>{busy ? 'Generating…' : 'Generate report'}</span>
          </button>
          {status && <span role="status" className="text-xs text-slate-500">{status}</span>}
        </div>
        {!sessionId && <p className="text-xs text-amber-700 dark:text-amber-300">Run at least one analysis (Workspace or Chat) to create a session, then build a report from it.</p>}
        {error && <div role="alert" className="text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2">{error}</div>}
      </div>

      <aside className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 h-fit">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white mb-3">Generated reports</h2>
        {reports.length === 0 && <p className="text-xs text-slate-400">None yet.</p>}
        <ul className="space-y-2">
          {reports.map((r) => (
            <li key={r.report_id} className="rounded-xl border border-slate-200 dark:border-slate-800 p-2.5">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">{r.title}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge size="sm" variant={r.status === 'SUCCESS' ? 'success' : r.status === 'FAILURE' ? 'danger' : 'warning'}>{r.status.toLowerCase()}</Badge>
                <span className="text-[10px] uppercase text-slate-400">{r.format}</span>
                <span className="text-[10px] text-slate-400">{new Date(r.created_at).toLocaleString()}</span>
              </div>
              {r.error_message && <p className="text-[11px] text-red-600 mt-1">{r.error_message}</p>}
              <div className="mt-2 flex gap-2">
                {r.status === 'SUCCESS' && (
                  <button onClick={() => reportService.download(r.report_id, `${r.title}.${r.format}`).catch((e) => setError(e.message))} className="inline-flex items-center space-x-1 px-2 py-1 rounded-lg text-[11px] font-semibold text-white bg-indigo-600 hover:bg-indigo-700"><Download className="w-3 h-3" /><span>Download</span></button>
                )}
                <button onClick={async () => { try { await reportService.remove(r.report_id); await refreshReports(); } catch (e) { setError(e instanceof Error ? e.message : 'Delete failed'); } }} aria-label="Delete report" className="p-1 text-slate-400 hover:text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
};

export default ReportBuilderPage;
