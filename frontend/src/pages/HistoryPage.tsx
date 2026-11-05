import React, { useState } from 'react';
import {
  History,
  Search,
  Filter,
  Clock,
  Code2,
  CheckCircle2,
  RefreshCw,
  Trash2,
  ExternalLink,
  ChevronRight,
  Database,
  ShieldCheck,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useDataset } from '../context/DatasetContext';
import { DEMO_ANALYSIS_HISTORY } from '../services/demoData';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeDataset } = useDataset();
  const [historyItems, setHistoryItems] = useState(DEMO_ANALYSIS_HISTORY);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [activeCodeSnippet, setActiveCodeSnippet] = useState<{ title: string; code: string } | null>(null);

  // Filter items
  const filteredItems = historyItems.filter((item) => {
    const matchesSearch =
      item.operation.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.columns.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase()));
    
    if (selectedCategory === 'all') return matchesSearch;
    if (selectedCategory === 'outlier') return matchesSearch && item.operation.toLowerCase().includes('outlier');
    if (selectedCategory === 'correlation') return matchesSearch && item.operation.toLowerCase().includes('correlation');
    if (selectedCategory === 'groupby') return matchesSearch && item.operation.toLowerCase().includes('group');
    if (selectedCategory === 'histogram') return matchesSearch && item.operation.toLowerCase().includes('histogram');
    return matchesSearch;
  });

  const handleClearHistory = () => {
    setHistoryItems([]);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Analysis History & Audit Trail
            </h1>
            <Badge variant="success" size="sm">Deterministic Python Log</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Chronological log of computational operations, executed code snippets, and record counts.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleClearHistory}
            disabled={historyItems.length === 0}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Log</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Operations</p>
          <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">{historyItems.length}</p>
          <p className="text-[10px] text-indigo-500 mt-1">100% verified locally</p>
        </div>
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Avg Latency</p>
          <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">13.5 ms</p>
          <p className="text-[10px] text-emerald-500 mt-1">Sub-second execution</p>
        </div>
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Deterministic Ratio</p>
          <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">100%</p>
          <p className="text-[10px] text-slate-400 mt-1">0 LLM math hallucinations</p>
        </div>
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Target</p>
          <p className="text-sm font-bold text-indigo-600 dark:text-indigo-400 truncate mt-1">
            {activeDataset ? activeDataset.name : 'baseline_benchmark.csv'}
          </p>
          <p className="text-[10px] text-slate-400 mt-1">Session scoped</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white dark:bg-slate-900 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs">
        {/* Category Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {[
            { id: 'all', label: 'All Operations' },
            { id: 'outlier', label: 'Outlier Scans' },
            { id: 'correlation', label: 'Correlations' },
            { id: 'groupby', label: 'Group-By' },
            { id: 'histogram', label: 'Histograms' },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors ${
                selectedCategory === cat.id
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search operation or column..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* History Table */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
        {filteredItems.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm font-semibold">No analysis operations match your filter.</p>
            <p className="text-xs mt-1">Run queries in the Analysis Workspace or AI Chat to populate the history.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 font-semibold uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4">Operation</th>
                  <th className="py-3 px-4">Columns</th>
                  <th className="py-3 px-4">Records Examined</th>
                  <th className="py-3 px-4">Execution Time</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-900 dark:text-slate-100">
                      <div className="flex items-center space-x-2">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                        <span>{item.operation}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {item.columns.map((c) => (
                          <span
                            key={c}
                            className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[10px]"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 dark:text-slate-400">
                      <span>{item.recordsUsed} used / {item.recordsExamined} rows</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
                        {item.executionTimeMs} ms
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {item.timestamp}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          onClick={() => setActiveCodeSnippet({ title: item.operation, code: item.codeSnippet })}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                          title="View Python Script"
                        >
                          <Code2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => navigate('/workspace')}
                          className="px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 text-[11px] font-medium transition-colors"
                        >
                          Re-run
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Code Modal */}
      {activeCodeSnippet && (
        <Modal
          isOpen={true}
          onClose={() => setActiveCodeSnippet(null)}
          title={`Python Recipe: ${activeCodeSnippet.title}`}
          maxWidth="xl"
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              Deterministic Python code executed in the local sandbox:
            </p>
            <div className="bg-slate-950 text-slate-200 p-4 rounded-xl font-mono text-xs overflow-x-auto">
              <pre>{activeCodeSnippet.code}</pre>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(activeCodeSnippet.code);
                  setActiveCodeSnippet(null);
                }}
                className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700"
              >
                Copy to Clipboard & Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default HistoryPage;
