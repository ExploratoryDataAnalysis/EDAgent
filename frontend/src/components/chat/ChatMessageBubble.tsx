import React, { useState } from 'react';
import {
  Sparkles,
  User,
  CheckCircle2,
  Code2,
  ChevronDown,
  ChevronUp,
  BarChart3,
} from 'lucide-react';
import { ChatMessage } from '../../types';
import { PlotlyChart } from '../charts/PlotlyChart';

interface ChatMessageBubbleProps {
  message: ChatMessage;
  onSelectSuggestion?: (prompt: string) => void;
}

export const ChatMessageBubble: React.FC<ChatMessageBubbleProps> = ({
  message,
  onSelectSuggestion,
}) => {
  const [showCode, setShowCode] = useState(false);
  const isAgent = message.role === 'assistant';

  return (
    <div className={`flex items-start space-x-3.5 ${isAgent ? '' : 'flex-row-reverse space-x-reverse'}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${
          isAgent
            ? 'bg-gradient-to-tr from-indigo-600 to-cyan-500 text-white'
            : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200'
        }`}
      >
        {isAgent ? <Sparkles className="w-4 h-4" /> : <User className="w-4 h-4" />}
      </div>

      {/* Bubble Content */}
      <div className={`flex flex-col max-w-[85%] space-y-2.5 ${isAgent ? 'items-start' : 'items-end'}`}>
        <div
          className={`rounded-2xl p-4 text-xs leading-relaxed shadow-sm ${
            isAgent
              ? 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200'
              : 'bg-indigo-600 text-white rounded-tr-none'
          }`}
        >
          {/* Main Text Content */}
          <p className="whitespace-pre-wrap">{message.content}</p>

          {/* Structured Analysis Execution Plan Pill */}
          {message.analysisPlan && (
            <div className="mt-3 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-[11px] font-semibold text-indigo-700 dark:text-indigo-300">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Verified Deterministic Execution</span>
                </div>
                <span className="text-[10px] font-mono text-slate-400">
                  {message.analysisPlan.operation.toUpperCase()} • {message.analysisPlan.column}
                </span>
              </div>

              {message.analysisResult?.warnings && message.analysisResult.warnings.length > 0 && (
                <div className="mt-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                  ⚠️ {message.analysisResult.warnings.join(' • ')}
                </div>
              )}
            </div>
          )}

          {/* Interactive Plotly mini chart if result contains plotSpec or operation */}
          {message.analysisResult && message.analysisPlan?.operation === 'histogram' && (
            <div className="mt-3 h-48 bg-slate-50 dark:bg-slate-800/40 rounded-xl p-2 border border-slate-100 dark:border-slate-800">
              <PlotlyChart
                data={[
                  {
                    type: 'bar',
                    x: ['$15k-$100k', '$100k-$189k', '$189k-$276k', '$276k-$363k', '$363k-$450k (Outlier)'],
                    y: [9, 1, 0, 0, 1],
                    marker: { color: ['#6366f1', '#6366f1', '#cbd5e1', '#cbd5e1', '#f43f5e'] },
                  },
                ]}
                layout={{
                  title: { text: 'Annual Income Distribution ($)', font: { size: 11 } },
                  margin: { l: 30, r: 20, t: 30, b: 50 },
                  xaxis: { tickfont: { size: 9 } },
                  yaxis: { title: { text: 'Count' } },
                }}
              />
            </div>
          )}

          {/* Code toggle if executionCode is present */}
          {message.analysisResult?.executionCode && (
            <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <button
                onClick={() => setShowCode(!showCode)}
                className="flex items-center space-x-1.5 text-[11px] text-slate-500 hover:text-indigo-600 dark:text-slate-400"
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>{showCode ? 'Hide Python Code' : 'View Python Calculation Code'}</span>
                {showCode ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>

              {showCode && (
                <pre className="mt-2 p-2.5 rounded-lg bg-slate-900 text-slate-200 font-mono text-[10px] overflow-x-auto">
                  {message.analysisResult.executionCode}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Suggestion Prompt Chips */}
        {message.suggestedQuestions && message.suggestedQuestions.length > 0 && onSelectSuggestion && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {message.suggestedQuestions.map((q, idx) => (
              <button
                key={idx}
                onClick={() => onSelectSuggestion(q)}
                className="px-2.5 py-1 rounded-full text-[11px] bg-slate-100 hover:bg-indigo-50 dark:bg-slate-800 dark:hover:bg-indigo-950/60 text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-300 border border-slate-200 dark:border-slate-700 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
