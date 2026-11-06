import React from 'react';
import { Sparkles, User, CheckCircle2, AlertCircle, HelpCircle, Ban, Bot } from 'lucide-react';
import { AnalysisResult, ChatKind, StructuredAnalysisPlan } from '../../types';
import { ResultView } from '../results/ResultView';

export interface UiMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  kind?: ChatKind;
  plan?: StructuredAnalysisPlan | null;
  result?: AnalysisResult | null;
  /** 'llm' = wording written by the language model; 'template' = deterministic fallback text. */
  source?: 'llm' | 'template' | null;
  suggestions?: string[];
}

interface Props {
  message: UiMessage;
  onSelectSuggestion?: (prompt: string) => void;
}

const KIND_META: Record<ChatKind, { label: string; icon: React.ReactNode; tone: string }> = {
  analysis: { label: 'Verified analysis', icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />, tone: 'text-emerald-700 dark:text-emerald-300' },
  clarification: { label: 'Needs clarification', icon: <HelpCircle className="w-3.5 h-3.5 text-indigo-500" />, tone: 'text-indigo-700 dark:text-indigo-300' },
  cannot_answer: { label: 'Not supported', icon: <Ban className="w-3.5 h-3.5 text-amber-500" />, tone: 'text-amber-700 dark:text-amber-300' },
  ai_unavailable: { label: 'AI not configured', icon: <Bot className="w-3.5 h-3.5 text-amber-500" />, tone: 'text-amber-700 dark:text-amber-300' },
  error: { label: 'Could not complete', icon: <AlertCircle className="w-3.5 h-3.5 text-red-500" />, tone: 'text-red-700 dark:text-red-300' },
};

/** One chat message. Assistant messages with a result embed the full result view (charts, tables, exports). */
export const ChatMessageBubble: React.FC<Props> = ({ message, onSelectSuggestion }) => {
  const isAgent = message.role === 'assistant';
  const meta = message.kind ? KIND_META[message.kind] : null;

  return (
    <div className={`flex items-start gap-3 ${isAgent ? '' : 'flex-row-reverse'}`}>
      <div
        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${
          isAgent ? 'bg-gradient-to-tr from-indigo-600 to-cyan-500 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200'
        }`}
      >
        {isAgent ? <Sparkles className="w-4 h-4" /> : <User className="w-4 h-4" />}
      </div>

      <div className={`flex flex-col min-w-0 ${isAgent ? 'items-start w-full max-w-3xl' : 'items-end max-w-[85%]'} space-y-2`}>
        <div
          className={`rounded-2xl p-4 text-xs leading-relaxed shadow-sm w-full ${
            isAgent
              ? 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200'
              : 'bg-indigo-600 text-white rounded-tr-none w-auto'
          }`}
        >
          {isAgent && meta && (
            <div className={`flex items-center gap-1.5 mb-2 text-[11px] font-semibold ${meta.tone}`}>
              {meta.icon}
              <span>{meta.label}</span>
              {message.kind === 'analysis' && message.source && (
                <span className="ml-1 px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 font-normal" title={message.source === 'llm' ? 'The wording was written by the AI model; every number was checked against the computed result.' : 'Generated from the computed result without the AI model.'}>
                  {message.source === 'llm' ? 'AI-written explanation' : 'Computed summary'}
                </span>
              )}
            </div>
          )}

          {/* Rendered as text, never HTML: model output is untrusted. */}
          <p className="whitespace-pre-wrap break-words">{message.text}</p>

          {message.plan && (
            <details className="mt-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/60 px-3 py-2">
              <summary className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 cursor-pointer">Analysis plan used</summary>
              <pre className="mt-2 text-[10px] overflow-auto max-h-48 text-slate-500">{JSON.stringify(message.plan, null, 2)}</pre>
            </details>
          )}

          {message.result && (
            <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
              <ResultView result={message.result} />
            </div>
          )}
        </div>

        {isAgent && message.suggestions && message.suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.suggestions.map((s) => (
              <button
                key={s}
                onClick={() => onSelectSuggestion?.(s)}
                className="px-2.5 py-1 rounded-full text-[11px] border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 bg-indigo-50/60 dark:bg-indigo-950/30 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessageBubble;
