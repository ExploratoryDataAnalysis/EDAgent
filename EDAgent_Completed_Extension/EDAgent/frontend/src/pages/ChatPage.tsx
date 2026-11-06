import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bot, Database, Loader2, MessageSquarePlus, Send } from 'lucide-react';
import { useDataset } from '../context/DatasetContext';
import { chatService, sessionService } from '../services/api';
import { AIStatus, ChatResponse, ChatTurn } from '../types';
import { ChatMessageBubble, UiMessage } from '../components/chat/ChatMessageBubble';
import { EmptyState } from '../components/ui/EmptyState';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

/** Turns a stored turn into the two chat bubbles it represents. */
function fromTurn(t: ChatTurn): UiMessage[] {
  return [
    { id: `${t.request_id}-q`, role: 'user', text: t.user_query },
    {
      id: `${t.request_id}-a`, role: 'assistant', kind: t.kind,
      text: t.assistant_message || (t.status === 'FAILED' ? 'This question could not be completed.' : ''),
      plan: t.plan, result: t.result, source: t.explanation_source,
    },
  ];
}

function fromResponse(query: string, r: ChatResponse): UiMessage[] {
  const id = r.request_id || String(Date.now());
  return [
    { id: `${id}-q`, role: 'user', text: query },
    {
      id: `${id}-a`, role: 'assistant', kind: r.kind, text: r.reply_text, plan: r.analysis_plan,
      result: r.analysis_result, source: r.explanation_source, suggestions: r.suggested_questions,
    },
  ];
}

export const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeDataset, profile, session, ensureSession, newSession, isLoading } = useDataset();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [ai, setAi] = useState<AIStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { chatService.status().then(setAi).catch(() => setAi(null)); }, []);

  // Restore the conversation whenever the active session changes (also after a page reload).
  useEffect(() => {
    let cancelled = false;
    if (!session) { setMessages([]); return; }
    setRestoring(true);
    sessionService.get(session.id)
      .then((d) => { if (!cancelled) setMessages(d.turns.flatMap(fromTurn)); })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : 'Could not restore the conversation'))
      .finally(() => !cancelled && setRestoring(false));
    return () => { cancelled = true; };
  }, [session?.id]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages.length, sending]);

  const send = useCallback(async (text?: string) => {
    const q = (text ?? input).trim();
    if (!q || sending) return;
    setInput('');
    setError(null);
    setSending(true);
    // Show the question immediately; the answer replaces the pending state.
    const pendingId = `pending-${Date.now()}`;
    setMessages((m) => [...m, { id: pendingId, role: 'user', text: q }]);
    try {
      const sid = await ensureSession();
      const res = await chatService.send(sid, q);
      setMessages((m) => [...m.filter((x) => x.id !== pendingId), ...fromResponse(q, res)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The message could not be sent.');
    } finally {
      setSending(false);
    }
  }, [input, sending, ensureSession]);

  if (isLoading && !activeDataset) return <div className="p-10"><LoadingSpinner text="Loading dataset…" /></div>;
  if (!activeDataset) {
    return (
      <div className="max-w-3xl mx-auto p-10">
        <EmptyState icon={<Database className="w-8 h-8" />} title="No dataset selected" description="Upload a dataset or load a sample to start asking questions about it." actionText="Go to upload" onAction={() => navigate('/upload')} />
      </div>
    );
  }

  const starters = (profile?.suggested_questions ?? profile?.suggestedQuestions ?? []).slice(0, 5);

  return (
    <div className="flex flex-col h-full max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-slate-200 dark:border-slate-800">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">{session?.title || 'New conversation'}</p>
          <p className="text-[11px] text-slate-500 truncate">Asking about <b>{activeDataset.name}</b></p>
        </div>
        <button
          onClick={async () => { setMessages([]); setError(null); await newSession(); }}
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
        >
          <MessageSquarePlus className="w-3.5 h-3.5" /><span>New chat</span>
        </button>
      </div>

      {ai && !ai.configured && (
        <div role="status" className="mx-4 sm:mx-6 mt-3 flex items-start space-x-2 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs px-3 py-2">
          <Bot className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            {ai.message || 'No AI provider is configured on the server, so questions in plain English cannot be planned.'} You can still run every
            analysis from the <Link to="/workspace" className="underline font-semibold">Analysis Workspace</Link>.
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-5">
        {restoring && <LoadingSpinner text="Restoring conversation…" />}
        {!restoring && messages.length === 0 && (
          <div className="text-center py-10 space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">Ask a question about your data. Numbers always come from the analysis engine, never from the AI.</p>
            {starters.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {starters.map((s) => (
                  <button key={s} onClick={() => send(s)} className="px-3 py-1.5 rounded-full text-xs border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 bg-indigo-50/60 dark:bg-indigo-950/30 hover:bg-indigo-100">
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {messages.map((m, i) => (
          <ChatMessageBubble
            key={m.id}
            message={m}
            // Only the latest answer offers follow-up chips; older ones stay quiet.
            onSelectSuggestion={i === messages.length - 1 ? send : undefined}
          />
        ))}
        {sending && (
          <div className="flex items-center space-x-2 text-xs text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /><span>Planning and running the analysis…</span></div>
        )}
        {error && <p role="alert" className="text-xs text-red-600 dark:text-red-400">{error}</p>}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="px-4 sm:px-6 py-3 border-t border-slate-200 dark:border-slate-800 flex items-end gap-2"
      >
        <textarea
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Ask about your data… e.g. “Compare average salary by department”"
          maxLength={2000}
          className="flex-1 resize-none px-3 py-2.5 rounded-xl text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button type="submit" disabled={sending || !input.trim()} aria-label="Send" className="p-3 rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};

export default ChatPage;
