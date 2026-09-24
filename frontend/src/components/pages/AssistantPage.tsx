import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { AuthProvider, useAuth } from '../../services/auth';
import { aiApi } from '../../services/api';
import type { AIChatMessage, AIConversationItem, AIToolCall } from '../../types';

const SUGGESTIONS = [
  'Which hateful comments did we receive in the last month?',
  'Find hateful comments about immigrants',
  'Summarize the current comment statistics',
  'Analyze toxicity patterns across clusters',
  'Classify this text: "You should all be deported"',
];

const TOOL_LABELS: Record<string, string> = {
  filter_comments: 'Filtered comments',
  semantic_search_comments: 'Searched comments',
  classify_text: 'Classified text',
  get_dashboard_stats: 'Pulled dashboard stats',
};

const toolLabel = (tool: string) => TOOL_LABELS[tool] ?? `Called ${tool}`;

const suggestionTool = (s: string) =>
  s.startsWith('Find')
    ? 'semantic_search_comments'
    : s.startsWith('Which')
      ? 'filter_comments'
      : s.startsWith('Summarize') || s.startsWith('Analyze')
        ? 'get_dashboard_stats'
        : 'classify_text';

interface ChatSession {
  sessionId: string;
  title: string;
  updatedAt: string;
}

const storageKey = (userId: string) => `cc-assistant-chat:${userId}`;

const sessionTitle = (items: AIConversationItem[]): string => {
  // Items arrive newest-first; the chronologically first user message is last.
  const users = items.filter((i) => i.role === 'user');
  const source = users.length > 0 ? users[users.length - 1].content : (items[items.length - 1]?.content ?? '');
  const title = source.replace(/\s+/g, ' ').trim();
  return title.length > 0 ? (title.length > 60 ? `${title.slice(0, 60)}…` : title) : 'Untitled chat';
};

const conversationToMessages = (items: AIConversationItem[]): AIChatMessage[] =>
  items
    .filter((i) => i.role === 'user' || i.role === 'assistant')
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .map((i) =>
      i.role === 'user'
        ? { role: 'user', content: i.content }
        : {
            role: 'assistant' as const,
            content: i.content,
            tool_calls:
              i.tool_used && i.tool_used !== 'none'
                ? [{ tool: i.tool_used, input: i.tool_input, output: i.tool_output }]
                : [],
            model: i.response_model,
            tokens: i.response_tokens,
            latency_ms: i.latency_ms,
          }
    );

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

const Markdown = ({ content }: { content: string }) => (
  <div className="space-y-3 break-words leading-relaxed">
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
        h1: ({ children }) => <h1 className="text-xl font-semibold mt-4 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-semibold mt-4 first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-semibold mt-4 first:mt-0">{children}</h3>,
        ul: ({ children }) => <ul className="list-disc pl-6 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-6 space-y-1">{children}</ol>,
        a: ({ children, href }) => (
          <a href={href} target="_blank" rel="noreferrer" className="underline hover:text-mistral-red">
            {children}
          </a>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-mistral-border-strong pl-4 text-mistral-muted">
            {children}
          </blockquote>
        ),
        hr: () => <hr className="border-mistral-border" />,
        table: ({ children }) => (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-mistral-border rounded-sm">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-mistral-border bg-mistral-band px-3 py-1.5 text-left">{children}</th>
        ),
        td: ({ children }) => <td className="border border-mistral-border px-3 py-1.5">{children}</td>,
        code: ({ children, className }) => {
          const isBlock = /language-/.test(className || '') || String(children).includes('\n');
          if (isBlock) {
            return (
              <code className="block p-3 bg-mistral-inset rounded-sm text-xs overflow-x-auto font-mono">
                {children}
              </code>
            );
          }
          return (
            <code className="px-1 py-0.5 bg-mistral-inset rounded-sm text-xs font-mono">{children}</code>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);

const ToolTrace = ({ toolCalls }: { toolCalls: AIToolCall[] }) => {
  if (toolCalls.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      {toolCalls.map((call, i) => (
        <details key={i} className="group border border-mistral-border rounded-sm bg-white">
          <summary className="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer select-none text-mistral-muted hover:text-mistral-ink">
            <svg className="w-3.5 h-3.5 text-mistral-red" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="font-mono uppercase">{toolLabel(call.tool)}</span>
          </summary>
          <div className="px-3 pb-3 space-y-2">
            {call.input && Object.keys(call.input).length > 0 && (
              <div>
                <p className="text-xs font-mono uppercase text-mistral-muted mb-1">Input</p>
                <pre className="p-2 bg-mistral-inset rounded-sm text-xs overflow-x-auto font-mono">
                  {JSON.stringify(call.input, null, 2)}
                </pre>
              </div>
            )}
            {call.output && (
              <div>
                <p className="text-xs font-mono uppercase text-mistral-muted mb-1">Output</p>
                <pre className="p-2 bg-mistral-inset rounded-sm text-xs overflow-x-auto max-h-48 overflow-y-auto font-mono">
                  {JSON.stringify(call.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
};

const Composer = ({
  value,
  onChange,
  onSend,
  isSending,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  isSending: boolean;
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  return (
    <div className="border-t border-mistral-border bg-mistral-surface">
      <div className="px-4 sm:px-6 py-4">
        {/* Border wraps input and button with matching heights so nothing drifts out of the frame */}
        <div className="flex items-end gap-3 bg-white border border-mistral-border-strong rounded-lg p-2 pl-4 focus-within:border-mistral-ink transition-colors">
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder="Ask about your comments, classifications, clusters…"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            className="flex-1 resize-none bg-transparent outline-none text-sm leading-6 py-1.5 max-h-[200px]"
          />
          <button
            onClick={onSend}
            disabled={isSending || value.trim().length === 0}
            aria-label="Send message"
            className="shrink-0 w-9 h-9 flex items-center justify-center rounded-full bg-mistral-ink text-white transition-colors hover:bg-mistral-red disabled:opacity-30 disabled:hover:bg-mistral-ink"
          >
            {isSending ? (
              <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            )}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-mistral-muted">
          The assistant can search, classify and analyze your data with tools. Enter to send, Shift+Enter for a new line.
        </p>
      </div>
    </div>
  );
};

const SessionList = ({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
}) => (
  <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1">
    {sessions.length === 0 ? (
      <p className="px-3 py-6 text-center text-xs text-mistral-muted">
        No previous chats yet. Your conversations will appear here.
      </p>
    ) : (
      sessions.map((session) => {
        const active = session.sessionId === activeSessionId;
        return (
          <div
            key={session.sessionId}
            className={`group relative rounded-sm border transition-colors ${
              active
                ? 'border-mistral-border-strong bg-white'
                : 'border-transparent hover:border-mistral-border hover:bg-white'
            }`}
          >
            <button
              onClick={() => onSelect(session.sessionId)}
              className="w-full text-left px-3 py-2.5 pr-9"
            >
              <span className="block text-sm leading-5 truncate">{session.title}</span>
              <span className="block text-xs font-mono uppercase text-mistral-muted mt-0.5">
                {formatDate(session.updatedAt)}
              </span>
            </button>
            <button
              onClick={() => onDelete(session.sessionId)}
              aria-label="Delete chat"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 w-7 h-7 hidden md:group-hover:flex items-center justify-center rounded-sm text-mistral-muted hover:text-mistral-red-deep hover:bg-mistral-red-tint"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          </div>
        );
      })
    )}
  </div>
);

const AssistantContent = () => {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [error, setError] = useState('');
  const [restored, setRestored] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  const saveState = useCallback(
    (sid: string | null, msgs: AIChatMessage[]) => {
      if (!user) return;
      try {
        localStorage.setItem(storageKey(user.id), JSON.stringify({ sessionId: sid, messages: msgs }));
      } catch {
        // localStorage unavailable (private mode etc.) — chat still works in memory
      }
    },
    [user]
  );

  const refreshSessions = useCallback(async () => {
    try {
      const { data } = await aiApi.conversations({ page_size: 100 });
      const bySession = new Map<string, AIConversationItem[]>();
      for (const item of data.items) {
        const list = bySession.get(item.session_id) ?? [];
        list.push(item);
        bySession.set(item.session_id, list);
      }
      const next: ChatSession[] = [];
      for (const [sid, items] of bySession) {
        next.push({ sessionId: sid, title: sessionTitle(items), updatedAt: items[0].created_at });
      }
      next.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
      setSessions(next);
    } catch {
      // History is best-effort; the chat itself stays usable
    }
  }, []);

  // Restore the chat the user left behind, so conversations stay active across page visits
  useEffect(() => {
    if (!isAuthenticated || !user || restored) return;
    setRestored(true);
    try {
      const raw = localStorage.getItem(storageKey(user.id));
      if (raw) {
        const saved = JSON.parse(raw) as { sessionId?: string | null; messages?: AIChatMessage[] };
        if (Array.isArray(saved.messages)) {
          setSessionId(saved.sessionId ?? null);
          setMessages(saved.messages);
        }
      }
    } catch {
      // Corrupted state — start fresh
    }
    refreshSessions();
  }, [isAuthenticated, user, restored, refreshSessions]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || isSending) return;

    const userMessage: AIChatMessage = { role: 'user', content: message };
    setMessages((prev) => {
      const next = [...prev, userMessage];
      saveState(sessionId, next);
      return next;
    });
    setInput('');
    setIsSending(true);
    setError('');

    try {
      const response = await aiApi.chat(message, sessionId);
      const data = response.data;
      const assistantMessage: AIChatMessage = {
        role: 'assistant',
        content: data.response,
        tool_calls: data.tool_calls ?? [],
        model: data.model,
        tokens: data.tokens,
        latency_ms: data.latency_ms,
      };
      setSessionId(data.session_id);
      setMessages((prev) => {
        const next = [...prev, assistantMessage];
        saveState(data.session_id, next);
        return next;
      });
      refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The assistant failed to respond');
    } finally {
      setIsSending(false);
    }
  };

  const newChat = () => {
    setMessages([]);
    setSessionId(null);
    setError('');
    setSidebarOpen(false);
    saveState(null, []);
  };

  const selectSession = async (sid: string) => {
    setSidebarOpen(false);
    if (sid === sessionId) return;
    setError('');
    try {
      const { data } = await aiApi.conversations({ session_id: sid, page_size: 100 });
      const msgs = conversationToMessages(data.items);
      setSessionId(sid);
      setMessages(msgs);
      saveState(sid, msgs);
    } catch {
      setError('Could not load that chat.');
    }
  };

  const deleteSession = async (sid: string) => {
    try {
      await aiApi.deleteSession(sid);
    } catch {
      setError('Could not delete that chat.');
      return;
    }
    if (sid === sessionId) {
      setSessionId(null);
      setMessages([]);
      saveState(null, []);
    }
    refreshSessions();
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <div className="animate-spin h-8 w-8 border-2 border-mistral-border-strong border-t-mistral-ink rounded-full" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)] px-4">
        <div className="bg-mistral-yellow-tint text-mistral-ink border border-mistral-border px-4 py-3 rounded-sm">
          Please login to use the AI assistant.
        </div>
      </div>
    );
  }

  const newChatButton = (
    <button
      onClick={newChat}
      className="shrink-0 flex items-center gap-2 text-sm px-3 py-1.5 border border-mistral-border-strong rounded-sm hover:bg-mistral-band transition-colors"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
      </svg>
      New chat
    </button>
  );

  const sidebar = (
    <>
      <div className="p-3 border-b border-mistral-border">
        {newChatButton}
      </div>
      <SessionList
        sessions={sessions}
        activeSessionId={sessionId}
        onSelect={selectSession}
        onDelete={deleteSession}
      />
    </>
  );

  return (
    <div className="flex h-[calc(100vh-4rem)] min-h-0">
      {/* Chat history — full height, desktop */}
      <aside className="hidden md:flex w-72 shrink-0 flex-col border-r border-mistral-border bg-mistral-surface">
        {sidebar}
      </aside>

      {/* Chat history — mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-72 max-w-[85vw] flex flex-col bg-mistral-surface border-r border-mistral-border">
            {sidebar}
          </aside>
        </div>
      )}

      {/* Main chat column */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="shrink-0 border-b border-mistral-border bg-mistral-surface">
          <div className="h-16 px-4 sm:px-6 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={() => setSidebarOpen(true)}
                aria-label="Open chat history"
                className="md:hidden shrink-0 w-9 h-9 flex items-center justify-center rounded-sm border border-mistral-border-strong hover:bg-mistral-band"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <div className="flex items-baseline gap-3 overflow-hidden">
                <h1 className="font-display text-lg font-semibold truncate">AI Assistant</h1>
                <span className="hidden sm:inline text-xs font-mono uppercase text-mistral-muted">
                  Agentic · tools always on
                </span>
              </div>
            </div>
            {newChatButton}
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-8">
            {messages.length === 0 ? (
              <div className="pt-[10vh] pb-16 text-center">
                <p className="text-xs font-mono uppercase text-mistral-muted mb-4">
                  Comment Checker · Agentic Assistant
                </p>
                <h2 className="font-display text-3xl sm:text-4xl font-semibold leading-tight">
                  What do you want to know
                  <br />
                  about your{' '}
                  <span className="bg-mistral-yellow-highlight dark:bg-mistral-yellow-highlight/40 px-1">comments</span>?
                </h2>
                <p className="mt-4 text-mistral-muted">
                  It searches, classifies and summarizes your data with tools before answering.
                </p>
                <div className="grid sm:grid-cols-2 gap-3 mt-10 max-w-xl mx-auto text-left">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="group border border-mistral-border bg-white rounded-sm px-4 py-3 text-sm hover:border-mistral-ink transition-colors"
                    >
                      <span className="block text-mistral-muted text-xs font-mono uppercase mb-1">
                        {toolLabel(suggestionTool(s))}
                      </span>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, i) =>
                message.role === 'user' ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[85%] bg-mistral-ink text-white rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap break-words">
                      {message.content}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="space-y-2">
                    <p className="text-xs font-mono uppercase text-mistral-muted">Assistant</p>
                    <Markdown content={message.content} />
                    <ToolTrace toolCalls={message.tool_calls ?? []} />
                    {(message.model || message.latency_ms != null) && (
                      <p className="text-xs text-mistral-muted font-mono">
                        {message.model}
                        {message.latency_ms != null ? ` · ${message.latency_ms}ms` : ''}
                        {message.tokens != null ? ` · ${message.tokens} tokens` : ''}
                      </p>
                    )}
                  </div>
                )
              )
            )}

            {isSending && (
              <div className="space-y-2">
                <p className="text-xs font-mono uppercase text-mistral-muted">Assistant</p>
                <div className="flex items-center gap-2 text-mistral-muted text-sm">
                  <span className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-mistral-muted animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-mistral-muted animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-mistral-muted animate-bounce [animation-delay:300ms]" />
                  </span>
                  Thinking and running tools…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Composer */}
        <div className="shrink-0">
          {error && (
            <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-3">
              <p className="text-sm text-mistral-red-deep bg-mistral-red-tint border border-mistral-border rounded-sm px-3 py-2">
                {error}
              </p>
            </div>
          )}
          <Composer value={input} onChange={setInput} onSend={() => send(input)} isSending={isSending} />
        </div>
      </div>
    </div>
  );
};

const AssistantPage = () => (
  <AuthProvider>
    <AssistantContent />
  </AuthProvider>
);

export default AssistantPage;
