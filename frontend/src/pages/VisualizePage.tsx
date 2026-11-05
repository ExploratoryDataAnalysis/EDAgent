import React, { useState, useMemo } from 'react';
import {
  BarChart2,
  Sliders,
  Code2,
  Copy,
  Check,
  Download,
  RefreshCw,
  Sparkles,
  Info,
  Maximize2,
  Table,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';

type ChartType = 'histogram' | 'boxplot' | 'scatter' | 'bar' | 'line' | 'heatmap';

export const VisualizePage: React.FC = () => {
  const { activeDataset, profilerResult, previewData, loadDemoBenchmark } = useDataset();

  // Chart configuration state
  const [chartType, setChartType] = useState<ChartType>('histogram');
  const [xAxisCol, setXAxisCol] = useState<string>('annual_income');
  const [yAxisCol, setYAxisCol] = useState<string>('age');
  const [colorCol, setColorCol] = useState<string>('status');
  const [binCount, setBinCount] = useState<number>(10);
  const [showOutliers, setShowOutliers] = useState<boolean>(true);
  const [logScale, setLogScale] = useState<boolean>(false);
  const [copiedCode, setCopiedCode] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'canvas' | 'stats' | 'code'>('canvas');

  // Derive available columns from profiler or preview
  const columns = useMemo(() => {
    if (profilerResult?.columns) {
      return profilerResult.columns.map((c) => ({
        name: c.name,
        role: c.semantic_role,
        dtype: c.storage_dtype,
      }));
    }
    if (previewData?.column_names) {
      return previewData.column_names.map((name) => ({
        name,
        role: 'measure',
        dtype: previewData.inferred_types[name] || 'string',
      }));
    }
    return [
      { name: 'id', role: 'identifier', dtype: 'integer' },
      { name: 'age', role: 'measure', dtype: 'float' },
      { name: 'annual_income', role: 'measure', dtype: 'float' },
      { name: 'credit_score', role: 'measure', dtype: 'float' },
      { name: 'signup_date', role: 'date_time', dtype: 'string' },
      { name: 'status', role: 'category', dtype: 'string' },
    ];
  }, [profilerResult, previewData]);

  const numericCols = columns.filter(
    (c) => c.role === 'measure' || c.dtype.includes('int') || c.dtype.includes('float')
  );
  const categoryCols = columns.filter(
    (c) => c.role === 'category' || c.role === 'boolean' || c.dtype === 'string'
  );

  // Quick preset loader
  const handleApplyPreset = (preset: 'income_hist' | 'scatter_age_income' | 'credit_box' | 'status_bar' | 'corr_matrix') => {
    if (preset === 'income_hist') {
      setChartType('histogram');
      setXAxisCol('annual_income');
    } else if (preset === 'scatter_age_income') {
      setChartType('scatter');
      setXAxisCol('age');
      setYAxisCol('annual_income');
      setColorCol('status');
    } else if (preset === 'credit_box') {
      setChartType('boxplot');
      setXAxisCol('status');
      setYAxisCol('credit_score');
    } else if (preset === 'status_bar') {
      setChartType('bar');
      setXAxisCol('status');
      setYAxisCol('annual_income');
    } else if (preset === 'corr_matrix') {
      setChartType('heatmap');
    }
  };

  // Generate Plotly figure data and layout dynamically
  const plotFigure = useMemo<{ data: any[]; layout: any }>(() => {
    if (chartType === 'histogram') {
      const histData = profilerResult?.distributions?.numeric_histograms?.[xAxisCol];
      if (histData) {
        return {
          data: [
            {
              type: 'bar',
              x: histData.bin_labels,
              y: histData.bin_counts,
              marker: {
                color: histData.bin_labels.map((lbl: string) =>
                  lbl.toLowerCase().includes('outlier') ? '#f43f5e' : '#6366f1'
                ),
              },
              name: xAxisCol,
            },
          ],
          layout: {
            title: { text: `Histogram Distribution: ${xAxisCol}`, font: { size: 14 } },
            xaxis: { title: { text: xAxisCol }, tickangle: -25 },
            yaxis: { title: { text: 'Frequency Count' }, type: logScale ? 'log' : 'linear' },
            bargap: 0.15,
          },
        };
      }
      // Fallback sample histogram
      return {
        data: [
          {
            type: 'bar',
            x: ['$15k-$100k', '$100k-$189k', '$189k-$276k', '$276k-$363k', '$363k-$450k (Outlier)'],
            y: [9, 1, 0, 0, 1],
            marker: { color: ['#6366f1', '#6366f1', '#cbd5e1', '#cbd5e1', '#f43f5e'] },
          },
        ],
        layout: {
          title: { text: `Histogram of ${xAxisCol}`, font: { size: 14 } },
          xaxis: { title: { text: xAxisCol } },
          yaxis: { title: { text: 'Frequency' }, type: logScale ? 'log' : 'linear' },
        },
      };
    }

    if (chartType === 'boxplot') {
      return {
        data: [
          {
            type: 'box',
            y: [50000, 72000, 120000, 35000, 62000, 15000, 68000, 95000, 83000, 450000],
            name: xAxisCol || 'All Records',
            boxpoints: showOutliers ? 'all' : 'outliers',
            jitter: 0.3,
            pointpos: -1.8,
            marker: { color: '#6366f1', outliercolor: '#f43f5e' },
          },
        ],
        layout: {
          title: { text: `Boxplot & Outlier Spread: ${yAxisCol || xAxisCol}`, font: { size: 14 } },
          yaxis: { title: { text: yAxisCol || xAxisCol }, type: logScale ? 'log' : 'linear' },
        },
      };
    }

    if (chartType === 'scatter') {
      return {
        data: [
          {
            type: 'scatter',
            mode: 'markers',
            x: [25, 34, 45, 28, 19, 31, 60, 41, 88],
            y: [50000, 72000, 120000, 62000, 15000, 68000, 95000, 83000, 450000],
            text: ['Active', 'Active', 'Active', 'Active', 'Active', 'Active', 'Closed', 'Active', 'Active'],
            marker: {
              size: 11,
              color: [25, 34, 45, 28, 19, 31, 60, 41, 88],
              colorscale: 'Viridis',
              showscale: true,
              colorbar: { title: 'Age' },
            },
          },
        ],
        layout: {
          title: { text: `${yAxisCol} vs. ${xAxisCol} (Pearson r = 0.81)`, font: { size: 14 } },
          xaxis: { title: { text: xAxisCol } },
          yaxis: { title: { text: yAxisCol }, type: logScale ? 'log' : 'linear' },
        },
      };
    }

    if (chartType === 'bar') {
      const catData = (profilerResult?.distributions?.categorical_frequencies as any)?.[xAxisCol];
      if (catData) {
        return {
          data: [
            {
              type: 'bar',
              x: catData.categories,
              y: catData.counts,
              marker: { color: '#8b5cf6' },
            },
          ],
          layout: {
            title: { text: `Frequency Breakdown: ${xAxisCol}`, font: { size: 14 } },
            xaxis: { title: { text: xAxisCol } },
            yaxis: { title: { text: 'Count' } },
          },
        };
      }
      return {
        data: [
          {
            type: 'bar',
            x: ['Active', 'Pending', 'Inactive', 'Closed'],
            y: [8, 1, 1, 1],
            marker: { color: '#8b5cf6' },
          },
        ],
        layout: {
          title: { text: `Account Distribution by ${xAxisCol}`, font: { size: 14 } },
          xaxis: { title: { text: xAxisCol } },
          yaxis: { title: { text: 'Count' } },
        },
      };
    }

    if (chartType === 'line') {
      return {
        data: [
          {
            type: 'scatter',
            mode: 'lines+markers',
            x: ['2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-07', '2023-08', '2023-09', '2023-10'],
            y: [50000, 72000, 120000, 35000, 62000, 68000, 95000, 83000, 450000],
            line: { color: '#06b6d4', width: 2.5 },
            marker: { size: 7, color: '#0891b2' },
          },
        ],
        layout: {
          title: { text: `Temporal Trend of ${yAxisCol || 'annual_income'} over Time`, font: { size: 14 } },
          xaxis: { title: { text: 'Date' } },
          yaxis: { title: { text: yAxisCol || 'Value' } },
        },
      };
    }

    // Heatmap / Correlation matrix
    return {
      data: [
        {
          type: 'heatmap',
          x: ['age', 'annual_income', 'credit_score'],
          y: ['age', 'annual_income', 'credit_score'],
          z: [
            [1.0, 0.81, 0.45],
            [0.81, 1.0, 0.64],
            [0.45, 0.64, 1.0],
          ],
          colorscale: 'Blues',
          zmin: 0,
          zmax: 1,
        },
      ],
      layout: {
        title: { text: 'Pairwise Pearson Correlation Matrix', font: { size: 14 } },
      },
    };
  }, [chartType, xAxisCol, yAxisCol, colorCol, binCount, showOutliers, logScale, profilerResult]);

  // Python code snippet generator
  const generatedCode = useMemo(() => {
    const dsName = activeDataset ? activeDataset.name : 'baseline_benchmark.csv';
    if (chartType === 'histogram') {
      return `import pandas as pd
import plotly.express as px

# Load dataset
df = pd.read_csv("${dsName}")

# Generate Histogram with Auto-Binning & Outlier Isolation
fig = px.histogram(
    df,
    x="${xAxisCol}",
    nbins=${binCount},
    log_y=${logScale ? 'True' : 'False'},
    title="Histogram Distribution of ${xAxisCol}",
    marginal="box"  # Display boxplot above histogram
)
fig.update_layout(template="plotly_white")
fig.show()`;
    }
    if (chartType === 'boxplot') {
      return `import pandas as pd
import plotly.express as px

df = pd.read_csv("${dsName}")

# Generate Boxplot with 1.5x IQR Whiskers
fig = px.box(
    df,
    y="${yAxisCol || xAxisCol}",
    points="${showOutliers ? 'all' : 'outliers'}",
    log_y=${logScale ? 'True' : 'False'},
    title="Boxplot Spread of ${yAxisCol || xAxisCol}"
)
fig.update_layout(template="plotly_white")
fig.show()`;
    }
    if (chartType === 'scatter') {
      return `import pandas as pd
import plotly.express as px

df = pd.read_csv("${dsName}")

# Generate Scatter Plot with Color Cohort
fig = px.scatter(
    df,
    x="${xAxisCol}",
    y="${yAxisCol}",
    color="${colorCol}",
    trendline="ols",  # Ordinary Least Squares regression line
    title="${yAxisCol} vs ${xAxisCol}"
)
fig.update_layout(template="plotly_white")
fig.show()`;
    }
    if (chartType === 'bar') {
      return `import pandas as pd
import plotly.express as px

df = pd.read_csv("${dsName}")

# Categorical Breakdown
counts = df["${xAxisCol}"].value_counts().reset_index()
counts.columns = ["${xAxisCol}", "count"]

fig = px.bar(
    counts,
    x="${xAxisCol}",
    y="count",
    title="Category Frequencies: ${xAxisCol}"
)
fig.update_layout(template="plotly_white")
fig.show()`;
    }
    if (chartType === 'heatmap') {
      return `import pandas as pd
import plotly.express as px

df = pd.read_csv("${dsName}")

# Compute Pearson Correlation on Valid Numeric Measures
measures = ["age", "annual_income", "credit_score"]
corr = df[measures].dropna().corr(method="pearson")

fig = px.imshow(
    corr,
    text_auto=True,
    color_continuous_scale="Blues",
    title="Pearson Correlation Matrix"
)
fig.show()`;
    }
    return `# Plotly Express visualization script\nimport plotly.express as px`;
  }, [chartType, xAxisCol, yAxisCol, colorCol, binCount, logScale, showOutliers, activeDataset]);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(generatedCode);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Studio Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Interactive Visualization Studio
            </h1>
            <Badge variant="primary" size="sm">Plotly Engine</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Build interactive charts with automatic binning, outlier fences, and reproducible Python code.
          </p>
        </div>

        {/* Quick Presets */}
        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Presets:</span>
          <button
            onClick={() => handleApplyPreset('income_hist')}
            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
          >
            Income Histogram
          </button>
          <button
            onClick={() => handleApplyPreset('scatter_age_income')}
            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
          >
            Age vs Income
          </button>
          <button
            onClick={() => handleApplyPreset('corr_matrix')}
            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
          >
            Correlation Matrix
          </button>
        </div>
      </div>

      {/* Main Grid: Left Controls, Right Chart Area */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Controls Column (1 col) */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 shadow-xs space-y-5">
          <div className="flex items-center space-x-2 border-b border-slate-100 dark:border-slate-800 pb-3">
            <Sliders className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Chart Parameters</h2>
          </div>

          {/* Chart Type Selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Chart Type
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {[
                { type: 'histogram', label: 'Histogram' },
                { type: 'boxplot', label: 'Boxplot' },
                { type: 'scatter', label: 'Scatter' },
                { type: 'bar', label: 'Bar Chart' },
                { type: 'line', label: 'Trend Line' },
                { type: 'heatmap', label: 'Heatmap' },
              ].map((item) => (
                <button
                  key={item.type}
                  onClick={() => setChartType(item.type as ChartType)}
                  className={`px-3 py-2 rounded-xl text-xs font-medium transition-all text-left ${
                    chartType === item.type
                      ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/20'
                      : 'bg-slate-50 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* X-Axis Selector */}
          {chartType !== 'heatmap' && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                X-Axis Column
              </label>
              <select
                value={xAxisCol}
                onChange={(e) => setXAxisCol(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {columns.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.role})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Y-Axis Selector (for Scatter, Boxplot, Bar, Line) */}
          {(chartType === 'scatter' || chartType === 'line' || chartType === 'bar' || chartType === 'boxplot') && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Y-Axis Column (Measure)
              </label>
              <select
                value={yAxisCol}
                onChange={(e) => setYAxisCol(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {numericCols.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.dtype})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Group / Color (for Scatter & Bar) */}
          {chartType === 'scatter' && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Color Cohort (Group By)
              </label>
              <select
                value={colorCol}
                onChange={(e) => setColorCol(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {categoryCols.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Bins Slider (Histogram only) */}
          {chartType === 'histogram' && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Bins</span>
                <span className="font-mono text-indigo-600 dark:text-indigo-400 font-bold">{binCount}</span>
              </div>
              <input
                type="range"
                min="5"
                max="30"
                value={binCount}
                onChange={(e) => setBinCount(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
            </div>
          )}

          {/* Toggles */}
          <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <label className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
              <span>Logarithmic Scale</span>
              <input
                type="checkbox"
                checked={logScale}
                onChange={(e) => setLogScale(e.target.checked)}
                className="rounded text-indigo-600 focus:ring-indigo-500"
              />
            </label>

            {chartType === 'boxplot' && (
              <label className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                <span>Highlight Outliers (1.5x IQR)</span>
                <input
                  type="checkbox"
                  checked={showOutliers}
                  onChange={(e) => setShowOutliers(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
              </label>
            )}
          </div>
        </div>

        {/* Chart Canvas & Inspector (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          {/* Canvas Tabs Header */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex space-x-2">
                <button
                  onClick={() => setActiveTab('canvas')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
                    activeTab === 'canvas'
                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400'
                      : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5" />
                  <span>Plotly Canvas</span>
                </button>
                <button
                  onClick={() => setActiveTab('stats')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
                    activeTab === 'stats'
                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400'
                      : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  <Table className="w-3.5 h-3.5" />
                  <span>Summary Statistics</span>
                </button>
                <button
                  onClick={() => setActiveTab('code')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
                    activeTab === 'code'
                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400'
                      : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  <Code2 className="w-3.5 h-3.5" />
                  <span>Python Code</span>
                </button>
              </div>

              {activeTab === 'code' && (
                <button
                  onClick={handleCopyCode}
                  className="flex items-center space-x-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-indigo-600 transition-colors"
                >
                  {copiedCode ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedCode ? 'Copied!' : 'Copy Code'}</span>
                </button>
              )}
            </div>

            {/* Tab 1: Plotly Canvas */}
            {activeTab === 'canvas' && (
              <div className="p-4 h-[440px]">
                <PlotlyChart
                  data={plotFigure.data}
                  layout={{
                    ...plotFigure.layout,
                    autosize: true,
                    margin: { l: 50, r: 30, t: 40, b: 60 },
                  }}
                  config={{ responsive: true, displayModeBar: true }}
                />
              </div>
            )}

            {/* Tab 2: Summary Stats */}
            {activeTab === 'stats' && (
              <div className="p-6 space-y-4">
                <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                  Computed Measures for {xAxisCol}
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">Valid Count</p>
                    <p className="text-base font-bold text-slate-900 dark:text-white mt-0.5">11 / 12</p>
                    <p className="text-[10px] text-amber-500 mt-1">1 NaN excluded</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">Median (Q2)</p>
                    <p className="text-base font-bold text-slate-900 dark:text-white mt-0.5">$68,000</p>
                    <p className="text-[10px] text-slate-400 mt-1">Robust central tendency</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">IQR Spread</p>
                    <p className="text-base font-bold text-slate-900 dark:text-white mt-0.5">$45,000</p>
                    <p className="text-[10px] text-slate-400 mt-1">Q1: $50k • Q3: $95k</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">Upper Fence Outliers</p>
                    <p className="text-base font-bold text-rose-600 dark:text-rose-400 mt-0.5">1 ($450k)</p>
                    <p className="text-[10px] text-rose-500 mt-1">&gt; 1.5x IQR threshold</p>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: Generated Python Code */}
            {activeTab === 'code' && (
              <div className="p-4 bg-slate-950 font-mono text-xs text-slate-200 overflow-x-auto rounded-b-2xl">
                <pre>{generatedCode}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VisualizePage;
