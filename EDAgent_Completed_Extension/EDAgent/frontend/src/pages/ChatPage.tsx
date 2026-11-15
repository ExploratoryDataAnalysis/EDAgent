import React, { useEffect, useRef, useState } from 'react';
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
  const { activeDataset, session, isLoading } = useDataset();

  if (isLoading) return <div className="p-10"><LoadingSpinner text="Loading dataset…" /></div>;
  if (!activeDataset) {
    return (
      <div className="max-w-3xl mx-auto p-10">
        <EmptyState icon={<Database className="w-8 h-8" />} title="No dataset selected" description="Upload a dataset or load a sample to start asking questions about it." actionText="Go to upload" onAction={() => navigate('/upload')} />
      </div>
    );
  }

  const sessionId = session?.dataset_id === activeDataset.id ? session.id : undefined;
  // Remount the transcript on every selection change. Old replies cannot update the
  // new view, even if the server finishes saving a turn after the browser moved on.
  return <Conversation key={`${activeDataset.id}:${sessionId ?? ''}`} sessionId={sessionId} />;
};

function Conversation({ sessionId }: { sessionId?: string }) {
  const { activeDataset, profile, session, newSession } = useDataset();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState('');
  const [starting, setStarting] = useState(false);
  const [ai, setAi] = useState<AIStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(Boolean(sessionId));
  const sendRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    chatService.status()
      .then((status) => { if (active) setAi(status); })
      .catch(() => { if (active) setError('Could not check AI availability. You can still use the Analysis Workspace.'); });
    if (sessionId) {
      sessionService.get(sessionId)
        .then((d) => { if (active) setMessages(d.turns.flatMap(fromTurn)); })
        .catch(() => { if (active) setError('Could not restore the conversation. You can start a new chat.'); })
        .finally(() => { if (active) setRestoring(false); });
    }
    return () => {
      active = false;
      sendRef.current?.abort();
    };
  }, [sessionId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages.length, pending]);

  const blocked = !sessionId || !ai?.configured || restoring || starting || Boolean(pending);
  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || !sessionId || blocked || sendRef.current) return;
    const request = new AbortController();
    sendRef.current = request;
    setInput('');
    setError(null);
    setPending(q);
    try {
      const res = await chatService.send(sessionId, q, request.signal);
      if (!request.signal.aborted && res.session_id === sessionId) {
        setMessages((m) => [...m, ...fromResponse(q, res)]);
      }
    } catch (e) {
      if (!request.signal.aborted) {
        setInput(q);
        setError(e instanceof Error ? e.message : 'The message could not be sent.');
      }
    } finally {
      if (sendRef.current === request) {
        sendRef.current = null;
        if (!request.signal.aborted) setPending('');
      }
    }
  }

  async function startConversation() {
    // Abort delivery immediately when New chat is chosen. This does not promise
    // cancellation upstream; any completed work still belongs to the old session.
    sendRef.current?.abort();
    sendRef.current = null;
    setPending('');
    setStarting(true);
    setError(null);
    try {
      await newSession();
    } catch {
      setError('Could not start a new chat. Try again or open the Analysis Workspace.');
    } finally {
      setStarting(false);
    }
  }

  const starters = (profile?.suggested_questions ?? profile?.suggestedQuestions ?? []).slice(0, 5);

  return (
    <div className="flex flex-col h-full max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-slate-200 dark:border-slate-800">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">{(sessionId && session?.title) || 'New conversation'}</p>
          <p className="text-[11px] text-slate-500 truncate">Asking about <b>{activeDataset?.name}</b></p>
        </div>
        <div className="flex flex-wrap justify-end items-center gap-3">
          <Link to="/workspace" className="text-xs underline font-semibold text-indigo-700 dark:text-indigo-300">Analysis Workspace</Link>
          <button
            onClick={startConversation}
            disabled={starting || !ai?.configured}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-50"
          >
            <MessageSquarePlus className="w-3.5 h-3.5" /><span>{sessionId ? 'New chat' : 'Start chat'}</span>
          </button>
        </div>
      </div>

      {ai && !ai.configured && (
        <div role="status" className="mx-4 sm:mx-6 mt-3 flex items-start space-x-2 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs px-3 py-2">
          <Bot className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            {ai.message || 'AI chat is disabled.'} You can still analyse this dataset in the Analysis Workspace.
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-5">
        {restoring && <LoadingSpinner text="Restoring conversation…" />}
        {!restoring && messages.length === 0 && (
          <div className="text-center py-10 space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">{!sessionId && ai?.configured ? 'Select Start chat to begin.' : 'Ask a question about your data. The analysis engine computes the results.'}</p>
            {!blocked && starters.length > 0 && (
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
            onSelectSuggestion={!blocked && i === messages.length - 1 ? send : undefined}
          />
        ))}
        {pending && <ChatMessageBubble message={{ id: 'pending', role: 'user', text: pending }} />}
        <div role="status">
          {pending ? (
            <div className="flex items-center space-x-2 text-xs text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /><span>Planning and running the analysis…</span></div>
          ) : starting ? <p className="text-xs">Starting conversation…</p> : (
            <span className="sr-only">{messages[messages.length - 1]?.text}</span>
          )}
        </div>
        {error && (
          <div role="alert" className="text-xs text-red-600 dark:text-red-400">
            <p>{error}</p>
            <Link to="/workspace" className="mt-1 inline-block font-semibold underline">Run manually in Analysis Workspace</Link>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="px-4 sm:px-6 py-3 border-t border-slate-200 dark:border-slate-800 flex items-end gap-2"
      >
        <textarea
          rows={1}
          aria-label="Question about your dataset"
          disabled={blocked}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Ask about your data… e.g. “Compare average salary by department”"
          maxLength={2000}
          className="flex-1 resize-none px-3 py-2.5 rounded-xl text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button type="submit" disabled={blocked || !input.trim()} aria-label="Send" className="p-3 rounded-xl text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

export default ChatPage;
