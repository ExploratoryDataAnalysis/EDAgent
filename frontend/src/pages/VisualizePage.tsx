import React, { useState, useMemo, useEffect } from 'react';
import {
  BarChart2,
  Sliders,
  Code2,
  Copy,
  Check,
  Table,
  Sparkles,
  Info,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import { Badge } from '../components/ui/Badge';

type ChartType = 'histogram' | 'boxplot' | 'scatter' | 'bar' | 'line' | 'heatmap';

export const VisualizePage: React.FC = () => {
  const { activeDataset, profilerResult, previewData } = useDataset();

  // Chart configuration state
  const [chartType, setChartType] = useState<ChartType>('histogram');
  const [xAxisCol, setXAxisCol] = useState<string>('');
  const [yAxisCol, setYAxisCol] = useState<string>('');
  const [colorCol, setColorCol] = useState<string>('');
  const [binCount, setBinCount] = useState<number>(10);
  const [showOutliers, setShowOutliers] = useState<boolean>(true);
  const [logScale, setLogScale] = useState<boolean>(false);
  const [copiedCode, setCopiedCode] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'canvas' | 'stats' | 'code'>('canvas');

  // Derive available columns from profiler or preview
  const columns = useMemo(() => {
    if (profilerResult?.columns && profilerResult.columns.length > 0) {
      return profilerResult.columns.map((c) => ({
        name: c.name,
        role: c.semantic_role || c.semanticRole || 'measure',
        dtype: c.storage_dtype || c.storageDtype || 'string',
      }));
    }
    if (previewData?.column_names && previewData.column_names.length > 0) {
      return previewData.column_names.map((name) => ({
        name,
        role: 'measure',
        dtype: previewData.inferred_types[name] || 'string',
      }));
    }
    return [];
  }, [profilerResult, previewData]);

  const numericCols = useMemo(() => {
    return columns.filter(
      (c) =>
        c.role === 'measure' ||
        c.dtype.toLowerCase().includes('int') ||
        c.dtype.toLowerCase().includes('float') ||
        c.dtype.toLowerCase().includes('num')
    );
  }, [columns]);

  const categoryCols = useMemo(() => {
    return columns.filter(
      (c) =>
        c.role === 'category' ||
        c.role === 'boolean' ||
        c.role === 'text' ||
        c.dtype.toLowerCase() === 'string'
    );
  }, [columns]);

  const dateCols = useMemo(() => {
    return columns.filter(
      (c) =>
        c.role === 'datetime' ||
        c.dtype.toLowerCase().includes('date') ||
        c.dtype.toLowerCase().includes('time')
    );
  }, [columns]);

  // Sync selected columns when columns change
  useEffect(() => {
    if (columns.length > 0) {
      if (!xAxisCol || !columns.some((c) => c.name === xAxisCol)) {
        const defaultX = numericCols[0]?.name || columns[0]?.name;
        setXAxisCol(defaultX);
      }
      if (!yAxisCol || !numericCols.some((c) => c.name === yAxisCol)) {
        const defaultY = numericCols[1]?.name || numericCols[0]?.name || columns[0]?.name;
        setYAxisCol(defaultY);
      }
      if (!colorCol || !categoryCols.some((c) => c.name === colorCol)) {
        const defaultColor = categoryCols[0]?.name || columns[0]?.name;
        setColorCol(defaultColor);
      }
    }
  }, [columns, numericCols, categoryCols, xAxisCol, yAxisCol, colorCol]);

  // Quick preset handlers
  const handleApplyPreset = (preset: 'first_hist' | 'scatter_measures' | 'first_box' | 'category_bar' | 'corr_matrix') => {
    if (preset === 'first_hist') {
      setChartType('histogram');
      if (numericCols[0]) setXAxisCol(numericCols[0].name);
    } else if (preset === 'scatter_measures') {
      setChartType('scatter');
      if (numericCols[0]) setXAxisCol(numericCols[0].name);
      if (numericCols[1]) setYAxisCol(numericCols[1].name);
      if (categoryCols[0]) setColorCol(categoryCols[0].name);
    } else if (preset === 'first_box') {
      setChartType('boxplot');
      if (numericCols[0]) setYAxisCol(numericCols[0].name);
    } else if (preset === 'category_bar') {
      setChartType('bar');
      if (categoryCols[0]) setXAxisCol(categoryCols[0].name);
    } else if (preset === 'corr_matrix') {
      setChartType('heatmap');
    }
  };

  // Compile all rows from preview for point-based charts
  const allPreviewRows = useMemo(() => {
    const head = previewData?.head_records || [];
    const sample = previewData?.sample_records || [];
    const tail = previewData?.tail_records || [];
    return [...head, ...sample, ...tail];
  }, [previewData]);

  // Generate Plotly figure data and layout dynamically using actual backend data
  const plotFigure = useMemo<{ data: any[]; layout: any }>(() => {
    // 1. Histogram
    if (chartType === 'histogram') {
      // Find actual backend histogram
      const histItem = profilerResult?.distributions?.histograms?.find(
        (h) => h.column === xAxisCol
      );
      if (histItem && histItem.bins && histItem.bins.length > 0) {
        return {
          data: [
            {
              type: 'bar',
              x: histItem.bins.map((b) => `${b.bin_start.toFixed(1)} - ${b.bin_end.toFixed(1)}`),
              y: histItem.bins.map((b) => b.count),
              text: histItem.bins.map((b) => `${b.count} (${b.percentage}%)`),
              textposition: 'auto',
              marker: {
                color: histItem.bins.map((_, idx, arr) =>
                  idx === arr.length - 1 && arr.length > 3 ? '#f43f5e' : '#6366f1'
                ),
              },
              name: xAxisCol,
            },
          ],
          layout: {
            title: { text: `Histogram Distribution: ${xAxisCol}`, font: { size: 14 } },
            xaxis: { title: { text: `${xAxisCol} (Bins)` }, tickangle: -25 },
            yaxis: { title: { text: 'Frequency Count' }, type: logScale ? 'log' : 'linear' },
            bargap: 0.15,
          },
        };
      }

      // Fallback: check numeric_histograms map
      const legacyHist = profilerResult?.distributions?.numeric_histograms?.[xAxisCol];
      if (legacyHist) {
        return {
          data: [
            {
              type: 'bar',
              x: legacyHist.bin_labels,
              y: legacyHist.bin_counts,
              marker: {
                color: legacyHist.bin_labels.map((lbl: string) =>
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

      // Compute from raw preview values if profiler distribution not available
      const rawVals = allPreviewRows
        .map((r) => Number(r[xAxisCol]))
        .filter((v) => !isNaN(v) && v !== null);
      if (rawVals.length > 0) {
        return {
          data: [
            {
              type: 'histogram',
              x: rawVals,
              nbinsx: binCount,
              marker: { color: '#6366f1' },
              name: xAxisCol,
            },
          ],
          layout: {
            title: { text: `Histogram of ${xAxisCol} (from sample records)`, font: { size: 14 } },
            xaxis: { title: { text: xAxisCol } },
            yaxis: { title: { text: 'Count' }, type: logScale ? 'log' : 'linear' },
          },
        };
      }

      return {
        data: [{ type: 'bar', x: ['No Data'], y: [0] }],
        layout: { title: { text: `No numeric distribution found for ${xAxisCol}` } },
      };
    }

    // 2. Boxplot
    if (chartType === 'boxplot') {
      const targetCol = yAxisCol || xAxisCol;
      const boxItem = profilerResult?.distributions?.boxplots?.find((b) => b.column === targetCol);
      const rawVals = allPreviewRows
        .map((r) => Number(r[targetCol]))
        .filter((v) => !isNaN(v) && v !== null);

      if (rawVals.length > 0) {
        return {
          data: [
            {
              type: 'box',
              y: rawVals,
              name: targetCol,
              boxpoints: showOutliers ? 'all' : 'outliers',
              jitter: 0.3,
              pointpos: -1.8,
              marker: { color: '#6366f1', outliercolor: '#f43f5e' },
            },
          ],
          layout: {
            title: { text: `Boxplot & Outlier Spread: ${targetCol}`, font: { size: 14 } },
            yaxis: { title: { text: targetCol }, type: logScale ? 'log' : 'linear' },
          },
        };
      }

      if (boxItem) {
        return {
          data: [
            {
              type: 'box',
              name: targetCol,
              q1: [boxItem.q25],
              median: [boxItem.median],
              q3: [boxItem.q75],
              lowerfence: [boxItem.lower_fence],
              upperfence: [boxItem.upper_fence],
              y: boxItem.outliers_sample.length > 0 ? boxItem.outliers_sample : [boxItem.median],
              boxpoints: 'outliers',
              marker: { color: '#6366f1', outliercolor: '#f43f5e' },
            },
          ],
          layout: {
            title: { text: `Boxplot (1.5x IQR): ${targetCol}`, font: { size: 14 } },
            yaxis: { title: { text: targetCol }, type: logScale ? 'log' : 'linear' },
          },
        };
      }

      return {
        data: [{ type: 'box', y: [0], name: targetCol }],
        layout: { title: { text: `No numeric data available for ${targetCol}` } },
      };
    }

    // 3. Scatter Plot
    if (chartType === 'scatter') {
      const validPoints = allPreviewRows
        .filter((r) => r[xAxisCol] !== undefined && r[yAxisCol] !== undefined)
        .map((r) => ({
          x: Number(r[xAxisCol]),
          y: Number(r[yAxisCol]),
          text: colorCol ? String(r[colorCol] ?? '') : '',
        }))
        .filter((p) => !isNaN(p.x) && !isNaN(p.y));

      if (validPoints.length > 0) {
        return {
          data: [
            {
              type: 'scatter',
              mode: 'markers',
              x: validPoints.map((p) => p.x),
              y: validPoints.map((p) => p.y),
              text: validPoints.map((p) => p.text),
              marker: {
                size: 10,
                color: validPoints.map((p) => p.x),
                colorscale: 'Viridis',
                showscale: true,
                colorbar: { title: { text: xAxisCol } },
              },
            },
          ],
          layout: {
            title: { text: `${yAxisCol} vs. ${xAxisCol}`, font: { size: 14 } },
            xaxis: { title: { text: xAxisCol } },
            yaxis: { title: { text: yAxisCol }, type: logScale ? 'log' : 'linear' },
          },
        };
      }

      return {
        data: [{ type: 'scatter', x: [0], y: [0] }],
        layout: { title: { text: `No paired values between ${xAxisCol} and ${yAxisCol}` } },
      };
    }

    // 4. Categorical Bar Chart
    if (chartType === 'bar') {
      const catItem = (profilerResult?.distributions?.categorical_frequencies as any[])?.find(
        (c: any) => c.column === xAxisCol
      );
      if (catItem && catItem.categories && catItem.categories.length > 0) {
        return {
          data: [
            {
              type: 'bar',
              x: catItem.categories.map((c: any) => c.value),
              y: catItem.categories.map((c: any) => c.count),
              text: catItem.categories.map((c: any) => `${c.count} (${c.percentage}%)`),
              textposition: 'auto',
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

      // Check categorical_summary in column profile
      const colProfile = profilerResult?.columns?.find((c) => c.name === xAxisCol);
      const topVals = colProfile?.categorical_summary?.top_values || [];
      if (topVals.length > 0) {
        return {
          data: [
            {
              type: 'bar',
              x: topVals.map((v) => v.value),
              y: topVals.map((v) => v.count),
              text: topVals.map((v) => `${v.count} (${v.percentage}%)`),
              textposition: 'auto',
              marker: { color: '#8b5cf6' },
            },
          ],
          layout: {
            title: { text: `Top Values: ${xAxisCol}`, font: { size: 14 } },
            xaxis: { title: { text: xAxisCol } },
            yaxis: { title: { text: 'Count' } },
          },
        };
      }

      return {
        data: [{ type: 'bar', x: ['No Data'], y: [0] }],
        layout: { title: { text: `No categorical distribution for ${xAxisCol}` } },
      };
    }

    // 5. Line / Date Distribution
    if (chartType === 'line') {
      const dateItem =
        profilerResult?.distributions?.date_distributions?.find((d) => d.column === xAxisCol) ||
        profilerResult?.distributions?.date_distributions?.[0];

      if (dateItem && dateItem.buckets && dateItem.buckets.length > 0) {
        return {
          data: [
            {
              type: 'scatter',
              mode: 'lines+markers',
              x: dateItem.buckets.map((b) => b.period),
              y: dateItem.buckets.map((b) => b.count),
              line: { color: '#06b6d4', width: 2.5 },
              marker: { size: 7, color: '#0891b2' },
            },
          ],
          layout: {
            title: {
              text: `Temporal Distribution: ${dateItem.column} (per ${dateItem.unit})`,
              font: { size: 14 },
            },
            xaxis: { title: { text: 'Date / Period' } },
            yaxis: { title: { text: 'Observation Count' } },
          },
        };
      }

      return {
        data: [{ type: 'scatter', x: ['No Dates'], y: [0] }],
        layout: { title: { text: 'No parsed date/time distribution available in this dataset.' } },
      };
    }

    // 6. Heatmap / Correlation Matrix
    const pearson = profilerResult?.relationships?.pearson;
    if (pearson && pearson.columns.length > 0) {
      const zValues = pearson.columns.map((rowCol) =>
        pearson.columns.map((colCol) => pearson.matrix[rowCol]?.[colCol] ?? null)
      );

      return {
        data: [
          {
            type: 'heatmap',
            x: pearson.columns,
            y: pearson.columns,
            z: zValues,
            colorscale: 'Blues',
            zmin: -1,
            zmax: 1,
            text: zValues.map((row) => row.map((v) => (v !== null ? v.toFixed(3) : '-'))),
            texttemplate: '%{text}',
            textfont: { size: 11 },
          },
        ],
        layout: {
          title: { text: 'Pairwise Pearson Correlation Matrix', font: { size: 14 } },
        },
      };
    }

    return {
      data: [{ type: 'heatmap', x: ['None'], y: ['None'], z: [[0]] }],
      layout: { title: { text: 'No continuous numeric columns available for correlation.' } },
    };
  }, [
    chartType,
    xAxisCol,
    yAxisCol,
    colorCol,
    binCount,
    showOutliers,
    logScale,
    profilerResult,
    allPreviewRows,
  ]);

  // Active column stats for Summary Statistics tab
  const activeColStats = useMemo(() => {
    const targetColName = chartType === 'boxplot' ? (yAxisCol || xAxisCol) : xAxisCol;
    const colProf = profilerResult?.columns?.find((c) => c.name === targetColName);
    const boxItem = profilerResult?.distributions?.boxplots?.find((b) => b.column === targetColName);
    return { colProf, boxItem, targetColName };
  }, [profilerResult, chartType, xAxisCol, yAxisCol]);

  // Python code generator
  const generatedCode = useMemo(() => {
    const dsName = activeDataset?.original_filename || activeDataset?.name || 'dataset.csv';
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
    marginal="box"
)
fig.update_layout(template="plotly_white")
fig.show()`;
    }
    if (chartType === 'boxplot') {
      return `import pandas as pd
import plotly.express as px

df = pd.read_csv("${dsName}")

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

fig = px.scatter(
    df,
    x="${xAxisCol}",
    y="${yAxisCol}",
    ${colorCol ? `color="${colorCol}",` : ''}
    title="${yAxisCol} vs ${xAxisCol}"
)
fig.update_layout(template="plotly_white")
fig.show()`;
    }
    if (chartType === 'bar') {
      return `import pandas as pd
import plotly.express as px

df = pd.read_csv("${dsName}")

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
corr = df.select_dtypes(include=["number"]).corr(method="pearson")

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
            onClick={() => handleApplyPreset('first_hist')}
            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
          >
            Measure Histogram
          </button>
          <button
            onClick={() => handleApplyPreset('scatter_measures')}
            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
          >
            Scatter Plot
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
                { type: 'line', label: 'Date Trend' },
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
          {(chartType === 'scatter' || chartType === 'boxplot') && (
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

          {/* Group / Color (for Scatter) */}
          {chartType === 'scatter' && categoryCols.length > 0 && (
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

            {/* Tab 2: Real Summary Stats */}
            {activeTab === 'stats' && (
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Calculated Profiler Statistics for {activeColStats.targetColName}
                  </h3>
                  {activeColStats.colProf && (
                    <Badge role={activeColStats.colProf.semantic_role as any}>
                      {activeColStats.colProf.semantic_role?.toUpperCase()}
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">Valid Non-Null</p>
                    <p className="text-base font-bold text-slate-900 dark:text-white mt-0.5">
                      {activeColStats.colProf?.non_null_count ?? 0}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-1">
                      {activeColStats.colProf?.missing_count ?? 0} missing ({activeColStats.colProf?.missing_percentage ?? 0}%)
                    </p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">Median / Mode</p>
                    <p className="text-base font-bold text-slate-900 dark:text-white mt-0.5">
                      {activeColStats.colProf?.numeric_summary?.median?.toLocaleString() ??
                        activeColStats.colProf?.categorical_summary?.most_frequent_value ??
                        '-'}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-1">
                      {activeColStats.colProf?.numeric_summary ? 'Central tendency' : 'Most frequent'}
                    </p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">IQR Spread / Distinct</p>
                    <p className="text-base font-bold text-slate-900 dark:text-white mt-0.5">
                      {activeColStats.colProf?.numeric_summary?.iqr?.toLocaleString() ??
                        activeColStats.colProf?.distinct_count?.toLocaleString() ??
                        '-'}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-1">
                      {activeColStats.colProf?.numeric_summary
                        ? `Q1: ${activeColStats.colProf.numeric_summary.q25?.toLocaleString()} • Q3: ${activeColStats.colProf.numeric_summary.q75?.toLocaleString()}`
                        : 'Distinct categories'}
                    </p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">Outliers / Range</p>
                    <p className="text-base font-bold text-rose-600 dark:text-rose-400 mt-0.5">
                      {activeColStats.boxItem?.outlier_count !== undefined
                        ? `${activeColStats.boxItem.outlier_count} detected`
                        : `${activeColStats.colProf?.numeric_summary?.min ?? 0} to ${activeColStats.colProf?.numeric_summary?.max ?? 0}`}
                    </p>
                    <p className="text-[10px] text-rose-500 mt-1">
                      {activeColStats.boxItem ? '> 1.5x IQR threshold' : 'Observed domain range'}
                    </p>
                  </div>
                </div>

                {/* Additional descriptive stats if numeric measure */}
                {activeColStats.colProf?.numeric_summary && (
                  <div className="pt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                      <span className="text-slate-400">Mean:</span>{' '}
                      <strong className="font-mono text-slate-800 dark:text-slate-200">
                        {activeColStats.colProf.numeric_summary.mean?.toFixed(2) ?? '-'}
                      </strong>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                      <span className="text-slate-400">Std Dev:</span>{' '}
                      <strong className="font-mono text-slate-800 dark:text-slate-200">
                        {activeColStats.colProf.numeric_summary.std?.toFixed(2) ?? '-'}
                      </strong>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                      <span className="text-slate-400">Skewness:</span>{' '}
                      <strong className="font-mono text-slate-800 dark:text-slate-200">
                        {activeColStats.colProf.numeric_summary.skewness?.toFixed(3) ?? '-'}
                      </strong>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700">
                      <span className="text-slate-400">Kurtosis:</span>{' '}
                      <strong className="font-mono text-slate-800 dark:text-slate-200">
                        {activeColStats.colProf.numeric_summary.kurtosis?.toFixed(3) ?? '-'}
                      </strong>
                    </div>
                  </div>
                )}
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
