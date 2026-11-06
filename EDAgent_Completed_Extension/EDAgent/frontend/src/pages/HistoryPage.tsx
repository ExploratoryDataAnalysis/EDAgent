import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Download, Eye, MessageSquare, Pencil, Search, Trash2 } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { exportService, sessionService } from '../services/api';
import { AnalysisResult, SessionDetail, SessionSummary } from '../types';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Modal } from '../components/ui/Modal';
import { ResultView } from '../components/results/ResultView';

const when = (iso: string) => new Date(iso).toLocaleString();

/** Sessions and the analyses inside them: the audit trail of what was asked and computed. */
export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const { openSession, session: activeSession, activeDataset } = useDataset();
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [onlyActive, setOnlyActive] = useState(true);
  const [open, setOpen] = useState<Record<string, SessionDetail | 'loading'>>({});
  const [viewing, setViewing] = useState<AnalysisResult | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SessionSummary | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setSessions(await sessionService.list(onlyActive && activeDataset ? activeDataset.id : undefined));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load history');
    }
  }, [onlyActive, activeDataset?.id]);

  useEffect(() => { load(); }, [load]);

  const toggle = async (s: SessionSummary) => {
    if (open[s.id]) {
      setOpen(({ [s.id]: _drop, ...rest }) => rest);
      return;
    }
    setOpen((o) => ({ ...o, [s.id]: 'loading' }));
    try {
      const d = await sessionService.get(s.id);
      setOpen((o) => ({ ...o, [s.id]: d }));
    } catch (e) {
      setOpen(({ [s.id]: _drop, ...rest }) => rest);
      setError(e instanceof Error ? e.message : 'Could not load the session');
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await sessionService.remove(pendingDelete.id);
      if (activeSession?.id === pendingDelete.id) localStorage.removeItem('edagent_active_session_id');
      setPendingDelete(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
      setPendingDelete(null);
    }
  };

  const saveRename = async () => {
    if (!renaming || !renaming.title.trim()) return;
    try {
      await sessionService.rename(renaming.id, renaming.title.trim());
      setRenaming(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Rename failed');
    }
  };

  const shown = (sessions ?? []).filter((s) => `${s.title} ${s.dataset_name ?? ''}`.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Analysis history</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Every question and analysis, with the plan, data used and reproducible code. Open a session to continue it.</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center space-x-1.5 text-xs text-slate-600 dark:text-slate-300">
            <input type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} disabled={!activeDataset} />
            <span>Active dataset only</span>
          </label>
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search sessions" className="pl-8 pr-3 py-2 rounded-xl text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200" />
          </div>
        </div>
      </div>

      {error && <div role="alert" className="text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2">{error}</div>}
      {sessions === null && !error && <LoadingSpinner text="Loading history…" />}
      {sessions !== null && shown.length === 0 && (
        <EmptyState icon={<MessageSquare className="w-8 h-8" />} title="No sessions yet" description="Ask a question in the chat or run an analysis in the workspace and it will appear here." actionText="Open workspace" onAction={() => navigate('/workspace')} />
      )}

      <ul className="space-y-3">
        {shown.map((s) => {
          const detail = open[s.id];
          return (
            <li key={s.id} className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <div className="flex flex-wrap items-center gap-2 p-4">
                <button onClick={() => toggle(s)} aria-label={detail ? 'Collapse session' : 'Expand session'} className="text-slate-400 hover:text-slate-600">
                  {detail ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </button>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{s.title}</p>
                  <p className="text-[11px] text-slate-500">{s.dataset_name ?? 'dataset'} · {s.turn_count} {s.turn_count === 1 ? 'step' : 'steps'} · updated {when(s.updated_at)}</p>
                </div>
                {activeSession?.id === s.id && <Badge variant="primary" size="sm">Active</Badge>}
                <button onClick={async () => { await openSession(s.id); navigate('/chat'); }} className="px-2.5 py-1 rounded-lg text-[11px] font-semibold text-white bg-indigo-600 hover:bg-indigo-700">Open</button>
                <button onClick={() => setRenaming({ id: s.id, title: s.title })} aria-label="Rename" className="p-1.5 text-slate-400 hover:text-indigo-600"><Pencil className="w-3.5 h-3.5" /></button>
                <button onClick={() => exportService.sessionBundle(s.id).catch((e) => setError(e.message))} aria-label="Download all results" title="Download all results (.zip)" className="p-1.5 text-slate-400 hover:text-indigo-600"><Download className="w-3.5 h-3.5" /></button>
                <button onClick={() => setPendingDelete(s)} aria-label="Delete session" className="p-1.5 text-slate-400 hover:text-red-600"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>

              {detail === 'loading' && <div className="px-4 pb-4"><LoadingSpinner size="sm" text="Loading…" /></div>}
              {detail && detail !== 'loading' && (
                <ol className="border-t border-slate-100 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800">
                  {detail.turns.length === 0 && <li className="px-4 py-3 text-xs text-slate-400">Empty session.</li>}
                  {detail.turns.map((t) => (
                    <li key={t.request_id} className="px-4 py-3 flex flex-wrap items-center gap-2 text-xs">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-slate-800 dark:text-slate-200 truncate">{t.user_query}</p>
                        <p className="text-[11px] text-slate-500">
                          {when(t.created_at)} · {t.result ? `${t.result.operation.replace(/_/g, ' ')} on ${t.result.columns_used.join(', ') || 'all columns'} · ${t.result.records_used.toLocaleString()} rows` : t.kind.replace(/_/g, ' ')}
                        </p>
                      </div>
                      {t.result?.is_sampled && <Badge variant="warning" size="sm">Sampled</Badge>}
                      {t.result && (
                        <button onClick={() => setViewing(t.result!)} className="inline-flex items-center space-x-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50"><Eye className="w-3 h-3" /><span>View result</span></button>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </li>
          );
        })}
      </ul>

      <Modal isOpen={!!viewing} onClose={() => setViewing(null)} title={viewing ? viewing.operation.replace(/_/g, ' ') : ''} subtitle="Stored result" maxWidth="4xl">
        {viewing && <ResultView result={viewing} />}
      </Modal>

      <Modal isOpen={!!pendingDelete} onClose={() => setPendingDelete(null)} title="Delete this session?" maxWidth="sm">
        <p className="text-xs text-slate-600 dark:text-slate-300">“{pendingDelete?.title}” and its results and reports will be permanently removed. Your dataset is not affected.</p>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={() => setPendingDelete(null)} className="px-3 py-1.5 rounded-lg text-xs bg-slate-100 dark:bg-slate-800">Cancel</button>
          <button onClick={confirmDelete} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-red-600 hover:bg-red-700">Delete</button>
        </div>
      </Modal>

      <Modal isOpen={!!renaming} onClose={() => setRenaming(null)} title="Rename session" maxWidth="sm">
        <input autoFocus value={renaming?.title ?? ''} onChange={(e) => renaming && setRenaming({ ...renaming, title: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && saveRename()} maxLength={200}
          className="w-full px-3 py-2 rounded-lg text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700" />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={() => setRenaming(null)} className="px-3 py-1.5 rounded-lg text-xs bg-slate-100 dark:bg-slate-800">Cancel</button>
          <button onClick={saveRename} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700">Save</button>
        </div>
      </Modal>
    </div>
  );
};

export default HistoryPage;
