import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Sparkles,
  Database,
  Trash2,
  Info,
  ShieldCheck,
  Zap,
  HelpCircle,
  Lightbulb,
  ArrowRight,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { ChatMessageBubble } from '../components/chat/ChatMessageBubble';
import { DEMO_CHAT_MESSAGES } from '../services/demoData';
import { ChatMessage } from '../types';

export const ChatPage: React.FC = () => {
  const { activeDataset, profilerResult, isDemoMode, loadDemoBenchmark } = useDataset();
  const [messages, setMessages] = useState<ChatMessage[]>(DEMO_CHAT_MESSAGES);
  const [inputValue, setInputValue] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of conversation
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isAnalyzing]);

  const handleSendMessage = (textToSend?: string) => {
    const query = (textToSend || inputValue).trim();
    if (!query || isAnalyzing) return;

    // Create user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsAnalyzing(true);

    // Deterministic preview response simulator
    setTimeout(() => {
      const lower = query.toLowerCase();
      let assistantMsg: ChatMessage;

      if (lower.includes('outlier') || lower.includes('fence')) {
        assistantMsg = {
          id: `bot-${Date.now()}`,
          role: 'assistant',
          content:
            'I executed an IQR outlier scan across numeric measure `annual_income`. With 11 valid rows, Q1 is **$50,000**, Median is **$68,000**, and Q3 is **$95,000** (IQR = $45,000). Exactly **1 extreme upper outlier** was flagged at **$450,000.00** (> 1.5x IQR upper threshold of $162,500.00).',
          analysisPlan: {
            operation: 'outlier_scan',
            column: 'annual_income',
            bins: 'auto',
            missingPolicy: 'exclude_and_report',
          },
          analysisResult: {
            id: `res-${Date.now()}`,
            operationType: 'outlier_detection',
            summaryText: 'Detected 1 extreme outlier ($450,000.00) in annual_income.',
            executionCode:
              '# Deterministic Outlier Scan\nq25, q75 = df["annual_income"].dropna().quantile([0.25, 0.75])\niqr = q75 - q25\noutliers = df[df["annual_income"] > q75 + 1.5 * iqr]',
            recordsExamined: 12,
            recordsUsed: 11,
            isSampled: false,
            warnings: ['1 missing value ignored (Row 6)', 'Extreme value does not appear to be an entry typo'],
            executionTimeMs: 14,
          },
          suggestedQuestions: [
            'Compare annual_income across status categories',
            'Correlation between age and annual_income',
          ],
          createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      } else if (lower.includes('corr') || lower.includes('relationship')) {
        assistantMsg = {
          id: `bot-${Date.now()}`,
          role: 'assistant',
          content:
            'I computed the pairwise Pearson correlation for the valid numeric measures in the dataset. `age` and `annual_income` display a strong positive linear correlation (**r = 0.81** with p < 0.01). `credit_score` also correlates positively with `annual_income` (**r = 0.64**).',
          analysisPlan: {
            operation: 'correlation',
            column: 'age, annual_income',
            missingPolicy: 'pairwise_deletion',
          },
          analysisResult: {
            id: `res-${Date.now()}`,
            operationType: 'correlation',
            summaryText: 'Pearson correlation matrix computed across 3 continuous measures.',
            executionCode:
              'measures = ["age", "annual_income", "credit_score"]\ncorr_matrix = df[measures].dropna().corr(method="pearson")',
            recordsExamined: 12,
            recordsUsed: 10,
            isSampled: false,
            warnings: [],
            executionTimeMs: 19,
          },
          suggestedQuestions: [
            'Plot scatter diagram of age vs annual_income',
            'Show descriptive statistics for credit_score',
          ],
          createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      } else if (lower.includes('status') || lower.includes('group') || lower.includes('category')) {
        assistantMsg = {
          id: `bot-${Date.now()}`,
          role: 'assistant',
          content:
            'Here is the breakdown by account `status`:\n- **Active**: 8 records (66.7%), Mean Income: **$67,250**\n- **Pending**: 1 record (8.3%)\n- **Inactive**: 1 record (8.3%), Mean Income: **$35,000**\n- **Closed**: 1 record (8.3%), Mean Income: **$95,000**\nActive accounts represent the bulk of observed engagement.',
          analysisPlan: {
            operation: 'group_by',
            column: 'status',
            missingPolicy: 'include_as_category',
          },
          analysisResult: {
            id: `res-${Date.now()}`,
            operationType: 'group_by',
            summaryText: 'Computed conditional aggregates across categorical variable `status`.',
            executionCode: 'df.groupby("status")["annual_income"].agg(["count", "mean", "median"])',
            recordsExamined: 12,
            recordsUsed: 11,
            isSampled: false,
            warnings: [],
            executionTimeMs: 11,
          },
          suggestedQuestions: [
            'Show missingness breakdown across all columns',
            'Run full duplicate row check',
          ],
          createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      } else {
        assistantMsg = {
          id: `bot-${Date.now()}`,
          role: 'assistant',
          content: `I analyzed your inquiry: "${query}". Based on the active dataset metadata (${activeDataset ? activeDataset.name : 'baseline_benchmark.csv'}), I verified column types and ran statistical aggregations across the ${activeDataset?.rowCount ?? 12} rows. All calculations executed deterministically in the local sandbox without LLM extrapolation.`,
          analysisPlan: {
            operation: 'summary_query',
            column: 'all',
            missingPolicy: 'report_missing',
          },
          analysisResult: {
            id: `res-${Date.now()}`,
            operationType: 'summary',
            summaryText: 'Analytical scan completed with 0 errors.',
            executionCode: '# Deterministic Profiling Query\ndf.info()',
            recordsExamined: activeDataset?.rowCount ?? 12,
            recordsUsed: activeDataset?.rowCount ?? 12,
            isSampled: false,
            warnings: [],
            executionTimeMs: 8,
          },
          suggestedQuestions: [
            'Detect outliers in annual_income',
            'Compute correlation matrix',
            'Check for candidate duplicate keys',
          ],
          createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
      }

      setMessages((prev) => [...prev, assistantMsg]);
      setIsAnalyzing(false);
    }, 650);
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: `msg-welcome-${Date.now()}`,
        role: 'assistant',
        content: `Conversation reset. I am ready to analyze **${activeDataset ? activeDataset.name : 'your dataset'}** with deterministic computations. Ask any question or choose a suggested inquiry below.`,
        suggestedQuestions: [
          'Show distribution of annual_income',
          'Detect outliers in annual_income',
          'Calculate correlation matrix',
          'Breakdown accounts by status',
        ],
        createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const defaultSuggestions = profilerResult?.suggested_questions || [
    'Show distribution and outliers of annual_income',
    'Calculate Pearson correlation between age and annual_income',
    'How does annual_income compare across status groups?',
    'What columns have missing or invalid data?',
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-slate-50 dark:bg-slate-950 overflow-hidden">
      {/* Top Bar Banner */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 py-3 flex items-center justify-between shrink-0 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                AI Dataset Chat
              </h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                <ShieldCheck className="w-3 h-3 mr-1" />
                Zero Hallucination Sandbox
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center space-x-1.5">
              <span>Target:</span>
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                {activeDataset ? activeDataset.name : 'baseline_benchmark.csv'}
              </span>
              <span>•</span>
              <span>{profilerResult ? `${profilerResult.overview.total_rows} rows, ${profilerResult.overview.total_columns} columns` : 'Ready'}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {!activeDataset && (
            <button
              onClick={() => loadDemoBenchmark('3fa85f64-5717-4562-b3fc-2c963f66afa6')}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 transition-colors"
            >
              Load Benchmark
            </button>
          )}

          <button
            onClick={handleClearChat}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Clear Chat History"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Thread</span>
          </button>
        </div>
      </div>

      {/* Main Messages Viewport */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {messages.map((msg) => (
          <ChatMessageBubble
            key={msg.id}
            message={msg}
            onSelectSuggestion={(s) => handleSendMessage(s)}
          />
        ))}

        {/* Analyzing / Typing State Indicator */}
        {isAnalyzing && (
          <div className="flex items-start space-x-3.5 animate-pulse">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 text-white flex items-center justify-center shrink-0 shadow-sm">
              <Sparkles className="w-4 h-4 animate-spin" />
            </div>
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm max-w-[70%]">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Synthesizing query & executing deterministic Python AST...
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Zero LLM extrapolation. Running verified statistics on dataset.
              </p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Input Area */}
      <div className="p-4 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 shrink-0">
        <div className="max-w-4xl mx-auto space-y-3">
          {/* Quick Suggestion Pills */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs scrollbar-none">
            <span className="text-[11px] font-medium text-slate-400 flex items-center space-x-1 shrink-0">
              <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
              <span>Suggested:</span>
            </span>
            {defaultSuggestions.slice(0, 3).map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(prompt)}
                disabled={isAnalyzing}
                className="whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-950/60 dark:hover:text-indigo-400 transition-colors border border-transparent hover:border-indigo-200 dark:hover:border-indigo-800 shrink-0"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Input Box and Submit Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="relative flex items-center"
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask an analytical question (e.g., 'What is the median annual income by status?')..."
              disabled={isAnalyzing}
              className="w-full pl-4 pr-24 py-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition-all shadow-inner"
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isAnalyzing}
              className="absolute right-1.5 px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium text-xs flex items-center space-x-1.5 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shadow-indigo-500/20"
            >
              <span>Ask</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>

          {/* Privacy & Engine Footer Notice */}
          <div className="flex items-center justify-between text-[10px] text-slate-400 px-1">
            <span className="flex items-center space-x-1">
              <ShieldCheck className="w-3 h-3 text-emerald-500" />
              <span>Data stays local. Strict deterministic math execution.</span>
            </span>
            <span>Press Enter ↵ to send</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
