import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, Lightbulb, Loader2, Pencil, Play } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { analysisService } from '../services/api';
import { StructuredAnalysisPlan, SuggestedAnalysisPlan } from '../types';
import { AnalysisBuilder } from '../components/workspace/AnalysisBuilder';
import { ResultView } from '../components/results/ResultView';
import { EmptyState } from '../components/ui/EmptyState';
import { useRunAnalysis } from '../hooks/useRunAnalysis';

/** Manual analysis workspace: suggested analyses, a catalogue-driven builder, and the result canvas. */
export const WorkspacePage: React.FC = () => {
  const navigate = useNavigate();
  const { activeDataset, profile } = useDataset();
  const { run, running, progress, error, result } = useRunAnalysis();
  const [suggestions, setSuggestions] = useState<SuggestedAnalysisPlan[]>([]);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [draft, setDraft] = useState<StructuredAnalysisPlan | null>(null);

  useEffect(() => {
    setSuggestions([]);
    setSuggestError(null);
    if (!activeDataset) return;
    analysisService.suggestions(activeDataset.id).then(setSuggestions).catch((e) => setSuggestError(e instanceof Error ? e.message : 'Could not load suggestions'));
  }, [activeDataset?.id]);

  if (!activeDataset || !profile) {
    return (
      <div className="max-w-3xl mx-auto p-10">
        <EmptyState icon={<Database className="w-8 h-8" />} title="No dataset selected" description="Upload a dataset or load a sample to run analyses." actionText="Go to upload" onAction={() => navigate('/upload')} />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 grid grid-cols-1 lg:grid-cols-[22rem_1fr] gap-6">
      <div className="space-y-6">
        <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 space-y-3">
          <h2 className="flex items-center space-x-2 text-sm font-bold text-slate-900 dark:text-white"><Lightbulb className="w-4 h-4 text-amber-500" /><span>Suggested analyses</span></h2>
          {suggestError && <p className="text-xs text-red-600">{suggestError}</p>}
          {!suggestError && suggestions.length === 0 && <p className="text-xs text-slate-400">No suggestions for this dataset.</p>}
          <ul className="space-y-2 max-h-72 overflow-auto">
            {suggestions.map((s, i) => (
              <li key={i} className="rounded-xl border border-slate-200 dark:border-slate-800 p-2.5">
                <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{s.title}</p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">{s.description}</p>
                <div className="mt-2 flex gap-2">
                  <button disabled={running} onClick={() => run(s.plan, s.title)} className="inline-flex items-center space-x-1 px-2 py-1 rounded-lg text-[11px] font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"><Play className="w-3 h-3" /><span>Run</span></button>
                  <button onClick={() => setDraft(s.plan)} className="inline-flex items-center space-x-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200"><Pencil className="w-3 h-3" /><span>Edit</span></button>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white mb-3">Build an analysis</h2>
          <AnalysisBuilder onRun={(p, l) => run(p, l)} running={running} initialPlan={draft} />
        </section>
      </div>

      <section className="min-w-0 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 sm:p-6 min-h-[24rem]">
        {running && (
          <div className="flex items-center space-x-2 text-xs text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /><span>{progress || 'Running analysis…'}</span></div>
        )}
        {error && <div role="alert" className="mb-4 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2">{error}</div>}
        {!running && !result && !error && (
          <p className="text-sm text-slate-400 text-center mt-20">Run a suggested analysis or build your own. Results appear here with their charts, tables, methodology and exports.</p>
        )}
        {result && !running && <ResultView result={result} />}
      </section>
    </div>
  );
};

export default WorkspacePage;
