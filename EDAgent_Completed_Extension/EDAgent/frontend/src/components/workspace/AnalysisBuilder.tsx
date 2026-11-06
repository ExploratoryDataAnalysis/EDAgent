import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Play } from 'lucide-react';
import { FilterGroup, StructuredAnalysisPlan, ToolParam, ToolSpec } from '../../types';
import { analysisService } from '../../services/api';
import { useDataset } from '../../context/DatasetContext';
import { columnsFor } from './columnKinds';
import { FilterEditor } from './FilterEditor';

const field =
  'w-full px-2.5 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500';
const label = 'block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1';

// The catalogue is static for a given server build, so fetch it once per page load.
let catalogueCache: Promise<ToolSpec[]> | null = null;
export const loadCatalogue = () => (catalogueCache ??= analysisService.catalogue().catch((e) => { catalogueCache = null; throw e; }));

const FAMILY_LABELS: Record<string, string> = {
  descriptive: 'Descriptive', distribution: 'Distributions', relationship: 'Relationships', comparison: 'Comparisons',
  time: 'Time', chart: 'Charts', hypothesis: 'Hypothesis tests', ml: 'Machine learning', filter: 'Filtering',
};

interface Props {
  /** Runs the plan; the caller shows progress and the result. */
  onRun: (plan: StructuredAnalysisPlan, label: string) => unknown;
  running?: boolean;
  /** Pre-fills the form (e.g. from a suggestion). Changing the object re-initialises the form. */
  initialPlan?: StructuredAnalysisPlan | null;
  /** Restrict the operation list (e.g. chart-only studio). */
  only?: string[];
  /** Operation selected on first render. */
  defaultOperation?: string;
}

/** Form generated from the backend tool catalogue, so every supported operation is reachable. */
export const AnalysisBuilder: React.FC<Props> = ({ onRun, running, initialPlan, only, defaultOperation }) => {
  const { profile } = useDataset();
  const [catalogue, setCatalogue] = useState<ToolSpec[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [plan, setPlan] = useState<StructuredAnalysisPlan>({ operation: defaultOperation ?? only?.[0] ?? 'descriptive_stats' });

  useEffect(() => {
    loadCatalogue().then(setCatalogue).catch((e) => setLoadError(e instanceof Error ? e.message : 'Could not load the tool catalogue'));
  }, []);

  useEffect(() => {
    if (initialPlan) setPlan({ ...initialPlan });
  }, [initialPlan]);

  const spec = useMemo(() => catalogue.find((c) => c.operation === plan.operation), [catalogue, plan.operation]);
  const allColumns = profile?.columns ?? [];
  const set = (patch: Partial<StructuredAnalysisPlan>) => setPlan((p) => ({ ...p, ...patch }));
  const setParam = (name: string, value: unknown) =>
    setPlan((p) => {
      const parameters = { ...(p.parameters ?? {}) };
      if (value === '' || value === undefined) delete parameters[name];
      else parameters[name] = value;
      return { ...p, parameters };
    });

  const grouped = useMemo(() => {
    const g: Record<string, ToolSpec[]> = {};
    catalogue.filter((c) => !only || only.includes(c.operation)).forEach((c) => (g[c.family] ||= []).push(c));
    return g;
  }, [catalogue, only]);

  const changeOperation = (operation: string) =>
    // Keep filters/scope but reset column choices, which rarely carry over between operations.
    setPlan((p) => ({ operation, filters: p.filters, scope: p.scope, sample_size: p.sample_size, parameters: {} }));

  const toggle = (key: 'target_columns' | 'group_by', name: string, max: number) =>
    setPlan((p) => {
      const cur = p[key] ?? [];
      const next = cur.includes(name) ? cur.filter((c) => c !== name) : [...cur, name].slice(-max);
      return { ...p, [key]: next };
    });

  const problems: string[] = [];
  if (spec) {
    if (spec.column?.required && !plan.column) problems.push(`Choose ${spec.column.label}.`);
    if (spec.target_columns && (plan.target_columns?.length ?? 0) < spec.target_columns.min) problems.push(`Choose at least ${spec.target_columns.min} column(s) to analyse.`);
    if (spec.group_by && (plan.group_by?.length ?? 0) < spec.group_by.min) problems.push(`Choose at least ${spec.group_by.min} grouping column(s).`);
    if (spec.date_column && !plan.date_column) problems.push('Choose a date column.');
  }

  const renderParam = (p: ToolParam) => {
    const v = plan.parameters?.[p.name];
    const help = <p className="text-[10px] text-slate-400 mt-0.5">{p.description}</p>;
    let input: React.ReactNode;
    if (p.choices?.length) {
      input = (
        <select className={field} value={String(v ?? '')} onChange={(e) => setParam(p.name, e.target.value)}>
          <option value="">(default)</option>
          {p.choices.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      );
    } else if (p.type === 'bool') {
      input = (
        <select className={field} value={v === undefined ? '' : String(v)} onChange={(e) => setParam(p.name, e.target.value === '' ? '' : e.target.value === 'true')}>
          <option value="">(default)</option><option value="true">yes</option><option value="false">no</option>
        </select>
      );
    } else if (p.type === 'float' || p.type === 'int') {
      input = (
        <input className={field} type="number" step={p.type === 'int' ? 1 : 'any'} min={p.min ?? undefined} max={p.max ?? undefined}
          value={v === undefined ? '' : String(v)} onChange={(e) => setParam(p.name, e.target.value === '' ? '' : Number(e.target.value))} />
      );
    } else if (p.type === 'int_or_auto') {
      input = <input className={field} placeholder="auto or 2-12" value={String(v ?? '')} onChange={(e) => setParam(p.name, /^\d+$/.test(e.target.value) ? Number(e.target.value) : e.target.value)} />;
    } else if (p.type === 'list') {
      input = <input className={field} placeholder="comma separated" value={Array.isArray(v) ? v.join(', ') : ''} onChange={(e) => setParam(p.name, e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />;
    } else if (p.name.endsWith('_by')) {
      input = (
        <select className={field} value={String(v ?? '')} onChange={(e) => setParam(p.name, e.target.value)}>
          <option value="">(none)</option>
          {allColumns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>
      );
    } else {
      input = <input className={field} value={String(v ?? '')} onChange={(e) => setParam(p.name, e.target.value)} />;
    }
    return (
      <div key={p.name}>
        <label className={label}>{p.name.replace(/_/g, ' ')}</label>
        {input}{help}
      </div>
    );
  };

  const chips = (key: 'target_columns' | 'group_by', kind: string, max: number) => (
    <div className="flex flex-wrap gap-1.5 max-h-32 overflow-auto">
      {columnsFor(profile, kind).map((c) => {
        const on = (plan[key] ?? []).includes(c.name);
        return (
          <button type="button" key={c.name} onClick={() => toggle(key, c.name, max)} aria-pressed={on}
            className={`px-2 py-1 rounded-lg text-[11px] border transition-colors ${on ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-300 dark:border-slate-700 hover:border-indigo-400'}`}>
            {c.name}
          </button>
        );
      })}
    </div>
  );

  if (loadError) return <p role="alert" className="text-xs text-red-600">{loadError}</p>;
  if (!profile) return <p className="text-xs text-slate-500">Select a dataset to build an analysis.</p>;

  const run = () => {
    // Drop empty optional fields so the backend applies its own defaults.
    const clean: StructuredAnalysisPlan = { ...plan };
    if (!clean.target_columns?.length) delete clean.target_columns;
    if (!clean.group_by?.length) delete clean.group_by;
    if (!clean.parameters || !Object.keys(clean.parameters).length) delete clean.parameters;
    if (clean.scope !== 'sample') { delete clean.sample_size; delete clean.scope; }
    onRun(clean, `${spec?.operation ?? plan.operation}`);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className={label}>Analysis</label>
        <select className={field} value={plan.operation} onChange={(e) => changeOperation(e.target.value)}>
          {Object.entries(grouped).map(([fam, items]) => (
            <optgroup key={fam} label={FAMILY_LABELS[fam] ?? fam}>
              {items.map((c) => <option key={c.operation} value={c.operation}>{c.operation.replace(/_/g, ' ')}</option>)}
            </optgroup>
          ))}
        </select>
        {spec && <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">{spec.description}{spec.cost === 'modelling' ? ' (modelling — may take longer, runs on a sample if the data is large)' : ''}</p>}
      </div>

      {spec?.column && (
        <div>
          <label className={label}>{spec.column.label}{spec.column.required ? ' *' : ''}</label>
          <select className={field} value={plan.column ?? ''} onChange={(e) => set({ column: e.target.value || null })}>
            <option value="">{spec.column.required ? 'Select…' : '(none)'}</option>
            {columnsFor(profile, spec.column.kind).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </div>
      )}

      {spec?.target_columns && (
        <div>
          <label className={label}>Columns ({spec.target_columns.kind}){spec.target_columns.min ? ` — pick ${spec.target_columns.min === spec.target_columns.max ? spec.target_columns.min : `${spec.target_columns.min}+`}` : ' — leave empty for all'}</label>
          {chips('target_columns', spec.target_columns.kind, spec.target_columns.max)}
        </div>
      )}

      {spec?.group_by && (
        <div>
          <label className={label}>Group by ({spec.group_by.kind}){spec.group_by.min ? ' *' : ''}</label>
          {chips('group_by', spec.group_by.kind, spec.group_by.max)}
        </div>
      )}

      {spec?.date_column && (
        <div>
          <label className={label}>Date column *</label>
          <select className={field} value={plan.date_column ?? ''} onChange={(e) => set({ date_column: e.target.value || null })}>
            <option value="">Select…</option>
            {columnsFor(profile, 'datetime').map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {spec?.uses_aggregation && (
          <div>
            <label className={label}>Aggregation</label>
            <select className={field} value={plan.aggregation ?? 'mean'} onChange={(e) => set({ aggregation: e.target.value })}>
              {['mean', 'sum', 'median', 'count', 'min', 'max', 'std', 'nunique'].map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>
        )}
        {spec?.uses_interval && (
          <div>
            <label className={label}>Interval</label>
            <select className={field} value={plan.interval ?? 'month'} onChange={(e) => set({ interval: e.target.value as StructuredAnalysisPlan['interval'] })}>
              {['day', 'week', 'month', 'quarter', 'year'].map((a) => <option key={a}>{a}</option>)}
            </select>
          </div>
        )}
        {spec?.uses_bins && (
          <div>
            <label className={label}>Bins</label>
            <input className={field} type="number" min={2} max={200} placeholder="auto" value={plan.bins ?? ''} onChange={(e) => set({ bins: e.target.value ? Number(e.target.value) : null as unknown as undefined })} />
          </div>
        )}
        {spec?.uses_top_n && (
          <div>
            <label className={label}>Show top N</label>
            <input className={field} type="number" min={1} max={1000} placeholder="all" value={plan.top_n ?? ''} onChange={(e) => set({ top_n: e.target.value ? Number(e.target.value) : null })} />
          </div>
        )}
        {spec?.methods && (
          <div>
            <label className={label}>Method</label>
            <select className={field} value={plan.method ?? ''} onChange={(e) => set({ method: e.target.value || null })}>
              <option value="">(default)</option>
              {spec.methods.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
        )}
      </div>

      {spec && spec.parameters.length > 0 && <div className="grid grid-cols-2 gap-3">{spec.parameters.map(renderParam)}</div>}

      {spec?.needs_filters !== false && (
        <FilterEditor columns={allColumns} value={(plan.filters as FilterGroup | null) ?? null} onChange={(g) => set({ filters: g })} />
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={label}>Data scope</label>
          <select className={field} value={plan.scope ?? 'full_dataset'} onChange={(e) => set({ scope: e.target.value as 'full_dataset' | 'sample' })}>
            <option value="full_dataset">Full dataset</option>
            <option value="sample">Random sample (labelled)</option>
          </select>
        </div>
        {plan.scope === 'sample' && (
          <div>
            <label className={label}>Sample size</label>
            <input className={field} type="number" min={100} value={plan.sample_size ?? 10000} onChange={(e) => set({ sample_size: Number(e.target.value) })} />
          </div>
        )}
      </div>

      {problems.length > 0 && <ul className="text-[11px] text-amber-700 dark:text-amber-300 list-disc pl-4">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}

      <button type="button" onClick={run} disabled={running || problems.length > 0 || !spec}
        className="w-full inline-flex items-center justify-center space-x-2 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 shadow-md transition-all">
        {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
        <span>{running ? 'Running…' : 'Run analysis'}</span>
      </button>
    </div>
  );
};

export default AnalysisBuilder;
