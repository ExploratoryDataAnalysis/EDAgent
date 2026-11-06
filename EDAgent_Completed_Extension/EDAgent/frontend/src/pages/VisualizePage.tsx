import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import { Tabs } from '../components/ui/Tabs';
import { EmptyState } from '../components/ui/EmptyState';
import { AnalysisBuilder } from '../components/workspace/AnalysisBuilder';
import { ResultView } from '../components/results/ResultView';
import { useRunAnalysis } from '../hooks/useRunAnalysis';
import { ColumnProfile } from '../types';
import { kindOf } from '../components/workspace/columnKinds';

const CHART_OPS = ['histogram', 'boxplot', 'violin_plot', 'scatter_plot', 'frequency', 'time_trend', 'date_distribution', 'correlation', 'crosstab', 'group_by', 'custom_chart'];
const BRAND = '#4f46e5';
const select = 'px-3 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200';

/** Distribution of one column, drawn from the values the profiler already computed on the full data. */
const ProfileDistribution: React.FC<{ column: ColumnProfile; hist?: any; box?: any; freq?: any; dates?: any }> = ({ column, hist, box, freq, dates }) => {
  const kind = kindOf(column);
  if (kind === 'numeric' && hist) {
    const bins = hist.bins as { bin_start: number; bin_end: number; count: number }[];
    const x = bins.map((b) => (b.bin_start + b.bin_end) / 2);
    return (
      <div className="space-y-3">
        <PlotlyChart
          data={[{ type: 'bar', x, y: bins.map((b) => b.count), marker: { color: BRAND }, hovertemplate: bins.map((b) => `${b.bin_start.toPrecision(4)} – ${b.bin_end.toPrecision(4)}<br>count %{y}<extra></extra>`) }]}
          layout={{ title: { text: `Distribution of ${column.name}`, font: { size: 13 } }, xaxis: { title: { text: column.name } }, yaxis: { title: { text: 'Rows' } }, bargap: 0.02 }}
          style={{ width: '100%', height: '340px' }}
        />
        {box && (
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Median {Number(box.median).toPrecision(5)} · IQR {Number(box.q25).toPrecision(5)} – {Number(box.q75).toPrecision(5)} · fences {Number(box.lower_fence).toPrecision(5)} – {Number(box.upper_fence).toPrecision(5)} ·{' '}
            <b>{box.outlier_count.toLocaleString()}</b> value(s) outside the fences.
          </p>
        )}
      </div>
    );
  }
  if (kind === 'categorical' && freq) {
    const cats = freq.categories as { value: string; count: number }[];
    return (
      <PlotlyChart
        data={[{ type: 'bar', orientation: 'h', y: cats.map((c) => c.value).reverse(), x: cats.map((c) => c.count).reverse(), marker: { color: BRAND } }]}
        layout={{ title: { text: `Most frequent values of ${column.name}`, font: { size: 13 } }, xaxis: { title: { text: 'Rows' } }, margin: { l: 140, r: 30, t: 40, b: 50 } }}
        style={{ width: '100%', height: `${Math.max(300, cats.length * 26 + 100)}px` }}
      />
    );
  }
  if (kind === 'datetime' && dates) {
    const b = dates.buckets as { period: string; count: number }[];
    return (
      <PlotlyChart
        data={[{ type: 'bar', x: b.map((d) => d.period), y: b.map((d) => d.count), marker: { color: BRAND } }]}
        layout={{ title: { text: `${column.name} by ${dates.unit}`, font: { size: 13 } }, yaxis: { title: { text: 'Rows' } } }}
        style={{ width: '100%', height: '340px' }}
      />
    );
  }
  return <p className="text-xs text-slate-400">The profiler did not compute a distribution for this column.</p>;
};

/** Visualisations: profile distributions, a correlation heatmap, and a backend-driven chart studio. */
export const VisualizePage: React.FC = () => {
  const navigate = useNavigate();
  const { activeDataset, profile } = useDataset();
  const [tab, setTab] = useState<'dist' | 'corr' | 'studio'>('dist');
  const [col, setCol] = useState<string>('');
  const { run, running, progress, error, result } = useRunAnalysis();

  const columns = profile?.columns ?? [];
  const selected = columns.find((c) => c.name === (col || columns.find((x) => kindOf(x) !== 'categorical' || (x.distinct_count ?? 0) < 60)?.name)) ?? columns[0];
  const d = profile?.distributions;
  const freqList: any[] = Array.isArray(d?.categorical_frequencies) ? d!.categorical_frequencies : [];

  const heat = useMemo(() => {
    const m = profile?.correlation_matrix ?? profile?.correlationMatrix;
    if (!m) return null;
    const keys = Object.keys(m);
    return { keys, z: keys.map((r) => keys.map((c) => m[r]?.[c] ?? null)) };
  }, [profile]);

  if (!activeDataset || !profile) {
    return <div className="max-w-3xl mx-auto p-10"><EmptyState icon={<Database className="w-8 h-8" />} title="No dataset selected" description="Select a dataset to explore its distributions and build charts." actionText="Go to upload" onAction={() => navigate('/upload')} /></div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
      <Tabs variant="pills" activeTab={tab} onChange={(id) => setTab(id as typeof tab)} tabs={[{ id: 'dist', label: 'Distributions' }, { id: 'corr', label: 'Correlations' }, { id: 'studio', label: 'Chart studio' }]} />

      {tab === 'dist' && selected && (
        <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 space-y-3">
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-300" htmlFor="viz-col">Column</label>
            <select id="viz-col" className={select} value={selected.name} onChange={(e) => setCol(e.target.value)}>
              {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <span className="text-[11px] text-slate-400">computed by the profiler on the full dataset</span>
          </div>
          <ProfileDistribution
            column={selected}
            hist={d?.histograms?.find((h) => h.column === selected.name)}
            box={d?.boxplots?.find((b) => b.column === selected.name)}
            freq={freqList.find((f) => f.column === selected.name)}
            dates={d?.date_distributions?.find((x) => x.column === selected.name)}
          />
        </section>
      )}

      {tab === 'corr' && (
        <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
          {heat && heat.keys.length > 1 ? (
            <PlotlyChart
              data={[{ type: 'heatmap', x: heat.keys, y: heat.keys, z: heat.z, zmin: -1, zmax: 1, colorscale: 'RdBu', reversescale: true, hovertemplate: '%{y} × %{x}<br>r = %{z:.3f}<extra></extra>' }]}
              layout={{ title: { text: 'Pearson correlation (numeric columns)', font: { size: 13 } }, margin: { l: 120, r: 30, t: 40, b: 120 } }}
              style={{ width: '100%', height: `${Math.max(380, heat.keys.length * 36 + 160)}px` }}
            />
          ) : (
            <p className="text-xs text-slate-400">At least two numeric columns are needed for a correlation matrix. Use the Chart studio for other relationships.</p>
          )}
        </section>
      )}

      {tab === 'studio' && (
        <div className="grid grid-cols-1 lg:grid-cols-[22rem_1fr] gap-6">
          <section className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
            <AnalysisBuilder only={CHART_OPS} defaultOperation="histogram" onRun={(p, l) => run(p, l)} running={running} />
          </section>
          <section className="min-w-0 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 sm:p-6 min-h-[22rem]">
            {running && <p className="text-xs text-slate-500">{progress || 'Building chart…'}</p>}
            {error && <div role="alert" className="mb-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2">{error}</div>}
            {!running && !result && !error && <p className="text-sm text-slate-400 text-center mt-16">Pick a chart type and columns. Every chart is computed by the analysis engine and can be exported as PNG, SVG or HTML.</p>}
            {result && !running && <ResultView result={result} />}
          </section>
        </div>
      )}
    </div>
  );
};

export default VisualizePage;
