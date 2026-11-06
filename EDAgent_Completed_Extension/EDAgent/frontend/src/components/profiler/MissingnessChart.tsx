import React from 'react';
import { PlotlyChart } from '../charts/PlotlyChart';
import { MissingnessReport } from '../../types';

interface MissingnessChartProps {
  missingness: MissingnessReport;
}

export const MissingnessChart: React.FC<MissingnessChartProps> = ({ missingness }) => {
  const chartData = missingness.missingness_chart_data || [];
  const patterns = missingness.missingness_patterns || [];

  // Filter columns with missing values or display top columns
  const cols = chartData.map((d) => d.column).reverse();
  const missingPcts = chartData.map((d) => d.missing_percentage).reverse();
  const missingCounts = chartData.map((d) => d.missing_count).reverse();

  const plotlyData: Plotly.Data[] = [
    {
      type: 'bar',
      x: missingPcts,
      y: cols,
      orientation: 'h',
      marker: {
        color: missingPcts.map((p) =>
          p > 40 ? '#ef4444' : p > 10 ? '#f59e0b' : p > 0 ? '#6366f1' : '#94a3b8'
        ),
        line: { width: 0 },
      },
      text: missingPcts.map((p, idx) => `${p}% (${missingCounts[idx]} missing)`),
      textposition: 'auto',
      hoverinfo: 'text+y',
    },
  ];

  const layout: Partial<Plotly.Layout> = {
    title: {
      text: 'Missingness Percentage by Column',
      font: { size: 13, family: 'Inter, sans-serif' },
    },
    xaxis: {
      title: { text: 'Missing (%)' },
      range: [0, Math.max(10, Math.max(...missingPcts, 0) * 1.15)],
      gridcolor: '#e2e8f0',
    },
    yaxis: {
      automargin: true,
    },
    margin: { l: 120, r: 20, t: 40, b: 40 },
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Missing Values Distribution
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Total Missing Cells: <strong className="text-slate-900 dark:text-slate-100 font-mono">{missingness.missing_cells || missingness.missingCells || 0}</strong> ({missingness.overall_missing_percentage || missingness.overallMissingPercentage || 0}%)
          </p>
        </div>
      </div>

      <div className="h-[280px]">
        <PlotlyChart data={plotlyData} layout={layout} />
      </div>

      {patterns.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Top Co-Missingness Combinations
          </h4>
          <div className="space-y-1.5">
            {patterns.map((pat, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs py-1.5 px-3 rounded-lg bg-slate-50 dark:bg-slate-800/60"
              >
                <div className="flex items-center space-x-1.5 truncate">
                  <span className="text-slate-400 font-mono">#{idx + 1}</span>
                  {pat.missing_columns.map((c) => (
                    <span
                      key={c}
                      className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 font-mono text-[11px]"
                    >
                      {c}
                    </span>
                  ))}
                </div>
                <span className="font-mono text-slate-500 dark:text-slate-400 font-medium shrink-0 ml-2">
                  {pat.row_count} rows ({pat.percentage}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
