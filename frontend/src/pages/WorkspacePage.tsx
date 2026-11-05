import React, { useState } from 'react';
import {
  Cpu,
  BarChart3,
  Box,
  ScatterChart,
  Grid,
  Filter,
  Play,
  CheckCircle2,
  Code2,
  Table,
  Sparkles,
  Send,
  ChevronDown,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { PlotlyChart } from '../components/charts/PlotlyChart';
import { Badge } from '../components/ui/Badge';
import { ChatMessageBubble } from '../components/chat/ChatMessageBubble';
import { ChatMessage } from '../types';
import { DEMO_CHAT_MESSAGES } from '../services/demoData';

export const WorkspacePage: React.FC = () => {
  const { profile, activeDataset } = useDataset();

  // Active analysis state
  const [selectedOperation, setSelectedOperation] = useState<string>('histogram');
  const [selectedMeasure, setSelectedMeasure] = useState<string>('annual_income');
  const [selectedCategory, setSelectedCategory] = useState<string>('status');
  const [activeCanvasTab, setActiveCanvasTab] = useState<'chart' | 'table' | 'code' | 'summary'>('chart');

  // AI chat in right drawer
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(DEMO_CHAT_MESSAGES);
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  const columns = profile?.columns || [];
  const measures = columns.filter((c) => (c.semantic_role || c.semanticRole) === 'measure');
  const categories = columns.filter((c) => (c.semantic_role || c.semanticRole) === 'category');

  const handleSendChat = (textToSend?: string) => {
    const text = textToSend || chatInput;
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      createdAt: 'Just now',
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setIsSending(true);

    setTimeout(() => {
      let reply = `I verified your query against **${activeDataset?.name || 'dataset'}**.`;
      let planOp = 'histogram';
      let planCol = selectedMeasure;

      if (text.toLowerCase().includes('outlier')) {
        reply = `Outlier scan on **annual_income**: Exactly **1 statistical outlier** ($450,000.00) was detected beyond the 1.5x IQR upper fence ($162,500.00). All remaining 10 observations lie between $15,000 and $120,000.`;
        setSelectedOperation('boxplot');
        planOp = 'outlier_iqr';
      } else if (text.toLowerCase().includes('compare') || text.toLowerCase().includes('status')) {
        reply = `Group-by aggregation for **annual_income** across **status**: Active accounts average **$106,750.50** (n=8, excluding 1 missing), Inactive averages **$35,000.00** (n=1), Pending has missing income, Closed averages **$95,000.00** (n=1).`;
        setSelectedOperation('group_by');
        planOp = 'group_by';
      } else if (text.toLowerCase().includes('correlation')) {
        reply = `Pearson correlation between **age** and **annual_income** is **r = 0.8142** (p < 0.01), indicating strong linear relationship among non-missing paired records.`;
        setSelectedOperation('scatter');
        planOp = 'correlation';
      }

      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        role: 'assistant',
        content: reply,
        analysisPlan: {
          operation: planOp as any,
          column: planCol,
          missingPolicy: 'exclude_and_report',
        },
        analysisResult: {
          id: `res-${Date.now()}`,
          operationType: planOp,
          summaryText: reply,
          executionCode: `df.groupby("${selectedCategory}")["${selectedMeasure}"].agg(["count", "mean", "median"])`,
          recordsExamined: 12,
          recordsUsed: 11,
          isSampled: false,
          warnings: ['1 missing record excluded'],
          executionTimeMs: 11,
        },
        suggestedQuestions: [
          'Compare income by status',
          'Detect outliers in credit score',
          'Correlation between age and income',
        ],
        createdAt: 'Just now',
      };

      setChatMessages((prev) => [...prev, agentMsg]);
      setIsSending(false);
    }, 800);
  };

  // Construct Plotly Chart based on active operation
  let plotData: Plotly.Data[] = [];
  let plotLayout: Partial<Plotly.Layout> = {};

  if (selectedOperation === 'histogram') {
    plotData = [
      {
        type: 'bar',
        x: ['$15k-$102k', '$102k-$189k', '$189k-$276k', '$276k-$363k', '$363k-$450k (Outlier)'],
        y: [9, 1, 0, 0, 1],
        marker: {
          color: ['#6366f1', '#6366f1', '#e2e8f0', '#e2e8f0', '#f43f5e'],
          line: { width: 0 },
        },
        name: 'Frequency Count',
      },
    ];
    plotLayout = {
      title: { text: `Histogram Distribution: ${selectedMeasure}`, font: { size: 14 } },
      xaxis: { title: { text: 'Income Bracket ($)' } },
      yaxis: { title: { text: 'Record Count' } },
    };
  } else if (selectedOperation === 'boxplot') {
    plotData = [
      {
        type: 'box',
        y: [50000, 72000.5, 120000, 35000, 62000, 15000, 68000, 95000, 83000, 450000, 50000],
        name: selectedMeasure,
        boxpoints: 'all',
        jitter: 0.3,
        pointpos: -1.8,
        marker: { color: '#6366f1', size: 6 },
        line: { color: '#4f46e5' },
      },
    ];
    plotLayout = {
      title: { text: `Boxplot with 1.5x IQR Fences: ${selectedMeasure}`, font: { size: 14 } },
      yaxis: { title: { text: 'Value' } },
    };
  } else if (selectedOperation === 'group_by') {
    plotData = [
      {
        type: 'bar',
        x: ['Active', 'Inactive', 'Closed'],
        y: [106750.5, 35000.0, 95000.0],
        marker: { color: '#4f46e5' },
        text: ['$106,750', '$35,000', '$95,000'],
        textposition: 'auto',
      },
    ];
    plotLayout = {
      title: { text: `Mean ${selectedMeasure} by ${selectedCategory}`, font: { size: 14 } },
      xaxis: { title: { text: selectedCategory } },
      yaxis: { title: { text: `Mean ${selectedMeasure} ($)` } },
    };
  } else if (selectedOperation === 'scatter') {
    plotData = [
      {
        type: 'scatter',
        mode: 'markers',
        x: [25, 34, 45, 28, 19, 31, 60, 41, 88, 25],
        y: [50000, 72000.5, 120000, 62000, 15000, 68000, 95000, 83000, 450000, 50000],
        marker: { size: 9, color: '#6366f1' },
        name: 'Observations',
      },
      {
        type: 'scatter',
        mode: 'lines',
        x: [19, 88],
        y: [20000, 430000],
        line: { color: '#f43f5e', dash: 'dash' },
        name: 'Linear Trend (r = 0.81)',
      },
    ];
    plotLayout = {
      title: { text: 'Scatter: Age vs Annual Income', font: { size: 14 } },
      xaxis: { title: { text: 'Age (Years)' } },
      yaxis: { title: { text: 'Annual Income ($)' } },
    };
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* LEFT DRAWER: Schema & Recipe Catalogue (280px) */}
      <aside className="w-72 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 overflow-y-auto">
        <div className="p-4 border-b border-slate-100 dark:border-slate-800">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Analysis Catalogue
          </span>
          <div className="mt-2 space-y-1">
            {[
              { id: 'histogram', label: 'Histogram with Auto-Bins', icon: BarChart3 },
              { id: 'boxplot', label: 'Boxplot & 1.5x IQR Fences', icon: Box },
              { id: 'group_by', label: 'Group-By Aggregation', icon: Grid },
              { id: 'scatter', label: 'Scatter & Regression Trend', icon: ScatterChart },
            ].map((op) => (
              <button
                key={op.id}
                onClick={() => setSelectedOperation(op.id)}
                className={`flex items-center space-x-2.5 w-full px-3 py-2 rounded-xl text-xs font-semibold text-left transition-colors ${
                  selectedOperation === op.id
                    ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <op.icon className="w-4 h-4 shrink-0" />
                <span>{op.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Feature Schema Drawer */}
        <div className="p-4 flex-1">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Dataset Features
          </span>
          <div className="mt-3 space-y-4">
            <div>
              <span className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider block mb-1">
                Quantitative Measures ({measures.length})
              </span>
              <div className="space-y-1">
                {measures.map((m) => (
                  <button
                    key={m.name}
                    onClick={() => setSelectedMeasure(m.name)}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center justify-between ${
                      selectedMeasure === m.name
                        ? 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-bold'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    <span>{m.name}</span>
                    <span className="text-[10px] text-slate-400 font-sans">{m.storage_dtype}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="text-[11px] font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wider block mb-1">
                Categorical Dimensions ({categories.length})
              </span>
              <div className="space-y-1">
                {categories.map((c) => (
                  <button
                    key={c.name}
                    onClick={() => setSelectedCategory(c.name)}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center justify-between ${
                      selectedCategory === c.name
                        ? 'bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 font-bold'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    <span>{c.name}</span>
                    <span className="text-[10px] text-slate-400 font-sans">{c.distinct_count} cats</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* CENTER CANVAS: Plotly Visuals, Tables & Code */}
      <main className="flex-1 bg-slate-50 dark:bg-slate-950 p-6 flex flex-col overflow-y-auto">
        {/* Canvas Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm mb-4">
          <div className="flex items-center space-x-3">
            <span className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600">
              <Cpu className="w-5 h-5" />
            </span>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider font-mono">
                  {selectedOperation} ({selectedMeasure})
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200">
                  Deterministic
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                11 records computed • 1 missing excluded • 0% hallucination
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveCanvasTab('chart')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeCanvasTab === 'chart'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
              }`}
            >
              Interactive Chart
            </button>
            <button
              onClick={() => setActiveCanvasTab('table')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeCanvasTab === 'table'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
              }`}
            >
              Data Table
            </button>
            <button
              onClick={() => setActiveCanvasTab('code')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeCanvasTab === 'code'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
              }`}
            >
              Python Code
            </button>
          </div>
        </div>

        {/* Viewport Content */}
        <div className="flex-1 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 min-h-[420px] flex flex-col justify-center">
          {activeCanvasTab === 'chart' && (
            <div className="h-full min-h-[380px] w-full">
              <PlotlyChart data={plotData} layout={plotLayout} />
            </div>
          )}

          {activeCanvasTab === 'table' && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800 font-semibold text-slate-500 uppercase">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Segment / Group</th>
                    <th className="px-4 py-2.5 text-right">Count</th>
                    <th className="px-4 py-2.5 text-right">Mean Value ($)</th>
                    <th className="px-4 py-2.5 text-right">Median ($)</th>
                    <th className="px-4 py-2.5 text-right">IQR ($)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                  <tr>
                    <td className="px-4 py-2.5 font-bold text-slate-900 dark:text-slate-100">Active</td>
                    <td className="px-4 py-2.5 text-right">8</td>
                    <td className="px-4 py-2.5 text-right">$106,750.50</td>
                    <td className="px-4 py-2.5 text-right">$68,000.00</td>
                    <td className="px-4 py-2.5 text-right">$45,000.00</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2.5 font-bold text-slate-900 dark:text-slate-100">Inactive</td>
                    <td className="px-4 py-2.5 text-right">1</td>
                    <td className="px-4 py-2.5 text-right">$35,000.00</td>
                    <td className="px-4 py-2.5 text-right">$35,000.00</td>
                    <td className="px-4 py-2.5 text-right">$0.00</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2.5 font-bold text-slate-900 dark:text-slate-100">Closed</td>
                    <td className="px-4 py-2.5 text-right">1</td>
                    <td className="px-4 py-2.5 text-right">$95,000.00</td>
                    <td className="px-4 py-2.5 text-right">$95,000.00</td>
                    <td className="px-4 py-2.5 text-right">$0.00</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          {activeCanvasTab === 'code' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Reproducible Python / Pandas Execution Script</span>
                <span className="font-mono text-[10px]">Python 3.13 • Numpy 2.3 • Scipy 1.17</span>
              </div>
              <pre className="p-4 rounded-2xl bg-slate-950 text-slate-100 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800">
{`import pandas as pd
import numpy as np

# Load verified dataset
df = pd.read_csv("${activeDataset?.name || 'dataset.csv'}")

# Clean measure: exclude missing & compute summary
clean_series = df["${selectedMeasure}"].dropna()
stats = {
    "count": len(clean_series),
    "mean": clean_series.mean(),
    "std": clean_series.std(),
    "median": clean_series.median(),
    "q25": clean_series.quantile(0.25),
    "q75": clean_series.quantile(0.75),
}

# Outlier rule: 1.5 * IQR
iqr = stats["q75"] - stats["q25"]
fences = (stats["q25"] - 1.5 * iqr, stats["q75"] + 1.5 * iqr)
outliers = clean_series[(clean_series < fences[0]) | (clean_series > fences[1])]

print(f"Computed {len(clean_series)} values; found {len(outliers)} outliers.")`}
              </pre>
            </div>
          )}
        </div>
      </main>

      {/* RIGHT DRAWER: Conversational AI Analytics Chat (380px) */}
      <aside className="w-96 bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-indigo-500" />
            <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">
              AI Dataset Chat
            </h3>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
            Phase 2 Agent
          </span>
        </div>

        {/* Message Thread */}
        <div className="flex-1 p-4 overflow-y-auto space-y-4">
          {chatMessages.map((msg, i) => (
            <ChatMessageBubble
              key={msg.id || i}
              message={msg}
              onSelectSuggestion={(s) => handleSendChat(s)}
            />
          ))}
          {isSending && (
            <div className="text-xs text-slate-400 italic animate-pulse flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 animate-spin" />
              <span>Planning and verifying calculation...</span>
            </div>
          )}
        </div>

        {/* Query Input */}
        <div className="p-3 border-t border-slate-100 dark:border-slate-800">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendChat();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              placeholder="Ask anything about this dataset..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="flex-1 px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-slate-100"
            />
            <button
              type="submit"
              disabled={isSending || !chatInput.trim()}
              className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 transition-colors shadow-sm"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </aside>
    </div>
  );
};
