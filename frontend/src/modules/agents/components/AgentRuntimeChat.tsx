import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowUp, ChevronDown, ChevronRight, Loader2, Square } from 'lucide-react';
import { agentRuntimeApi, type AgentChatMessage } from '@/modules/agents/agentRuntimeApi';
import { canvasNamesInText } from '@/modules/agents/canvas/canvasSourceGate';
import { AttachmentChips, ComposerPlusButton, composeMessage } from '@/modules/agents/components/ComposerPlusMenu';
import { planTitle } from '@/modules/agents/components/PlanPanel';
import { readRuntimeMode, RuntimeModePicker, type RuntimeMode } from '@/modules/agents/components/RuntimeModePicker';

const TOOL_TITLES: Record<string, string> = {
  read_file: 'Read',
  read: 'Read',
  bash: 'Ran',
  run_command: 'Ran',
  shell: 'Ran',
  edit: 'Edit',
  write: 'Write',
  grep: 'Search',
  glob: 'Find files',
  webfetch: 'Fetch',
};

function toolTitle(name: string) {
  return TOOL_TITLES[name] || name.replace(/_/g, ' ');
}

function parseToolCall(content: string) {
  const lines = content.split('\n');
  const name = (lines[0] || 'tool').trim();
  const detail = (lines[1] || '').trim();
  const output = lines.slice(2).join('\n').trim();
  return { name, detail, output };
}

function canvasLinkText(text: string) {
  const names = new Set(canvasNamesInText(text));
  const linked = text.replace(/`([a-z0-9]+(?:-[a-z0-9]+)*)`/gi, (full, name: string) => {
    if (!names.has(name)) return full;
    return `[${name}](#canvas/${encodeURIComponent(name)})`;
  });
  return linked.replace(/\bcanvas\s+([a-z0-9]+(?:-[a-z0-9]+)*)\b/gi, (full, name: string) => {
    if (!names.has(name) || linked.includes(`(#canvas/${encodeURIComponent(name)})`)) return full;
    return `canvas [${name}](#canvas/${encodeURIComponent(name)})`;
  });
}

function ChatMarkdown({ text, color, onOpenCanvas }: { text: string; color: string; onOpenCanvas?: (name: string) => void }) {
  return (
    <div className="agent-runtime-markdown" style={{ color, fontSize: '0.88rem', lineHeight: 1.55 }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p style={{ margin: '0 0 8px' }}>{children}</p>,
          ul: ({ children }) => <ul style={{ margin: '0 0 8px', paddingLeft: 18 }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '0 0 8px', paddingLeft: 18 }}>{children}</ol>,
          li: ({ children }) => <li style={{ marginBottom: 2 }}>{children}</li>,
          h1: ({ children }) => <h3 style={{ margin: '0 0 8px', fontSize: '1rem' }}>{children}</h3>,
          h2: ({ children }) => <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem' }}>{children}</h3>,
          h3: ({ children }) => <h3 style={{ margin: '0 0 8px', fontSize: '0.9rem' }}>{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote style={{ margin: '0 0 8px', paddingLeft: 10, borderLeft: '3px solid #d4d4d8', color: '#3f3f46' }}>{children}</blockquote>
          ),
          a: ({ href, children }) => {
            if (href?.includes('#canvas/')) {
              const name = decodeURIComponent(href.slice(href.indexOf('#canvas/') + '#canvas/'.length));
              return (
                <button
                  type="button"
                  onClick={() => onOpenCanvas?.(name)}
                  style={{ border: 'none', background: 'transparent', padding: 0, color: '#1d4ed8', font: 'inherit', cursor: 'pointer', textDecoration: 'underline' }}
                >
                  {children}
                </button>
              );
            }
            if (!href || href.startsWith('file:')) return <span>{children}</span>;
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: '#1d4ed8' }}>
                {children}
              </a>
            );
          },
          code: ({ className, children }) => {
            if (className) return <code className={className}>{children}</code>;
            return (
              <code style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.84em', background: '#e4e4e7', borderRadius: 4, padding: '1px 4px' }}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => {
            const block = React.Children.toArray(children)[0] as React.ReactElement<{ className?: string }> | undefined;
            const language = /language-([\w-]+)/.exec(block?.props?.className || '')?.[1];
            return (
              <div style={{ margin: '8px 0', border: '1px solid #e4e4e7', borderRadius: 8, overflow: 'hidden', background: '#ffffff' }}>
                {language && language !== 'text' && (
                  <div style={{ padding: '3px 10px', background: '#f4f4f5', color: '#71717a', fontSize: '0.68rem', letterSpacing: '0.04em', textTransform: 'lowercase' }}>
                    {language}
                  </div>
                )}
                <pre style={{ margin: 0, padding: '8px 10px', overflow: 'auto', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.82rem', lineHeight: 1.45 }}>
                  {children}
                </pre>
              </div>
            );
          },
        }}
      >
        {canvasLinkText(text)}
      </ReactMarkdown>
    </div>
  );
}

function ActivityRow({ kind, content }: { kind: 'thinking' | 'tool'; content: string }) {
  const [open, setOpen] = useState(false);
  const tool = kind === 'tool' ? parseToolCall(content) : null;
  const label = kind === 'thinking' ? 'Thought' : toolTitle(tool?.name || 'tool');
  const preview = (kind === 'thinking' ? content : tool?.detail || tool?.output || '').replace(/\s+/g, ' ').trim();
  return (
    <div style={{ maxWidth: '92%' }}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          width: '100%',
          minWidth: 0,
          padding: '2px 0',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          textAlign: 'left',
          color: '#71717a',
        }}
      >
        <ChevronRight size={14} aria-hidden="true" style={{ flexShrink: 0, transform: open ? 'rotate(90deg)' : 'none' }} />
        <span style={{ flexShrink: 0, fontSize: '0.8rem', fontWeight: 600, color: '#3f3f46' }}>{label}</span>
        {!open && preview && (
          <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.78rem' }}>
            {preview}
          </span>
        )}
      </button>
      {open && (
        <div style={{ margin: '2px 0 4px 20px', color: '#3f3f46', fontSize: '0.82rem', lineHeight: 1.5 }}>
          {kind === 'thinking' ? (
            <div style={{ whiteSpace: 'pre-wrap', fontStyle: 'italic' }}>{content}</div>
          ) : (
            <>
              {tool?.detail && (
                <pre style={{ margin: '0 0 6px', whiteSpace: 'pre-wrap', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.78rem' }}>
                  {tool.detail}
                </pre>
              )}
              {tool?.output && (
                <pre style={{ margin: 0, padding: '8px 10px', overflow: 'auto', border: '1px solid #e4e4e7', borderRadius: 8, background: '#fafafa', color: '#18181b', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.78rem', lineHeight: 1.45, whiteSpace: 'pre-wrap' }}>
                  {tool.output}
                </pre>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function AgentRuntimeChat({
  sessionId,
  agentLabel,
  messages,
  sandboxReady,
  onMessage,
  onSync,
  agentType,
  llmModel,
  llmModels = [],
  llmModelsLoading = false,
  onLlmModelChange,
  onOpenCanvas,
  onOpenPlan,
  buildRequest,
  onWorkingChange,
}: {
  sessionId: string;
  agentLabel: string;
  messages: AgentChatMessage[];
  sandboxReady: boolean;
  onMessage: (message: AgentChatMessage) => void;
  onSync: (messages: AgentChatMessage[]) => void;
  agentType?: string;
  llmModel?: string | null;
  llmModels?: { id: string; label?: string }[];
  llmModelsLoading?: boolean;
  onLlmModelChange?: (modelId: string) => void;
  onOpenCanvas?: (name: string) => void;
  onOpenPlan?: (message: AgentChatMessage) => void;
  buildRequest?: { nonce: number; content: string } | null;
  onWorkingChange?: (working: boolean) => void;
}) {
  const [draft, setDraft] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState('');
  const [llmOpen, setLlmOpen] = useState(false);
  const showLlm = agentType === 'nova';
  const selectedLlm = llmModels.find((item) => item.id === llmModel);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const syncSeq = useRef(0);
  const knownPlans = useRef<Set<string> | null>(null);
  const seenBuild = useRef(0);
  const visibleMessages = messages
    .filter((message) => {
      if (message.role === 'user') return true;
      if (message.role !== 'assistant' || message.content.startsWith('👋')) return false;
      if (message.kind === 'error' && agentType !== 'nova') return false;
      return true;
    })
    .slice()
    .sort((left, right) => (left.timestamp || '').localeCompare(right.timestamp || ''));
  const lastUserAt = [...visibleMessages].reverse().find((message) => message.role === 'user')?.timestamp || '';
  const answered = visibleMessages.some((message) => {
    if (message.role !== 'assistant' || (message.timestamp || '') <= lastUserAt) return false;
    return message.kind === 'reply' || message.kind === 'plan' || message.kind === 'debug' || message.kind === 'error' || !message.kind;
  });
  const working = sending || (Boolean(lastUserAt) && !answered);

  useEffect(() => {
    onWorkingChange?.(working);
  }, [working, onWorkingChange]);

  const stop = async () => {
    if (stopping) return;
    setStopping(true);
    setError('');
    try {
      const session = await agentRuntimeApi.stopSession(sessionId);
      onSync(session.messages || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to stop');
    } finally {
      setStopping(false);
    }
  };

  const syncNotices = async () => {
    const request = ++syncSeq.current;
    const session = await agentRuntimeApi.syncNotices(sessionId);
    if (request === syncSeq.current) onSync(session.messages || []);
  };

  useEffect(() => {
    if (!sandboxReady) return undefined;
    let cancelled = false;
    const load = () => {
      syncNotices().catch(() => undefined);
    };
    load();
    const timer = window.setInterval(() => {
      if (!cancelled) load();
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sessionId, sandboxReady]);

  useEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [working, visibleMessages.map((message) => `${message.id}:${message.content}`).join('\n')]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [draft]);

  useEffect(() => {
    if (!llmOpen) return undefined;
    const close = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Node && composerRef.current?.contains(target)) return;
      setLlmOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [llmOpen]);

  const deliver = async (content: string, mode?: RuntimeMode) => {
    if (!content || sending || !sandboxReady) return;
    setSending(true);
    setError('');
    try {
      const message = await agentRuntimeApi.sendMessage(
        sessionId,
        content,
        showLlm ? llmModel || undefined : undefined,
        showLlm ? mode || readRuntimeMode() : undefined,
      );
      onMessage(message);
      window.setTimeout(() => {
        syncNotices().catch(() => undefined);
      }, 1200);
      window.setTimeout(() => {
        syncNotices().catch(() => undefined);
      }, 3000);
      return true;
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to send the message');
      return false;
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (!buildRequest || seenBuild.current === buildRequest.nonce) return;
    seenBuild.current = buildRequest.nonce;
    void deliver(buildRequest.content, 'agent');
  }, [buildRequest]);

  useEffect(() => {
    const plans = visibleMessages.filter((message) => message.kind === 'plan');
    const ids = plans.map((message) => message.id);
    if (knownPlans.current === null) {
      knownPlans.current = new Set(ids);
      return;
    }
    const fresh = plans.filter((message) => !knownPlans.current?.has(message.id));
    knownPlans.current = new Set(ids);
    const latest = fresh[fresh.length - 1];
    if (latest) onOpenPlan?.(latest);
  }, [visibleMessages, onOpenPlan]);

  const send = async () => {
    const content = (await composeMessage(draft, files)).trim();
    if (!content) return;
    const sent = await deliver(content);
    if (sent) {
      setDraft('');
      setFiles([]);
    }
  };

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <div ref={scrollerRef} style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '12px 12px 8px' }}>
        {visibleMessages.map((message) => {
          const kind = message.role === 'user'
            ? 'user'
            : message.kind === 'thinking' || message.kind === 'tool' || message.kind === 'reply' || message.kind === 'plan' || message.kind === 'debug'
              ? message.kind
              : 'error';
          if (kind === 'tool' || kind === 'thinking') {
            return (
              <div key={message.id} style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 6 }}>
                <ActivityRow kind={kind} content={message.content} />
              </div>
            );
          }
          if (kind === 'reply') {
            return (
              <div key={message.id} style={{ margin: '4px 0 14px', maxWidth: '100%', color: '#18181b', fontSize: '0.92rem', lineHeight: 1.6 }}>
                <ChatMarkdown text={message.content} color="#18181b" onOpenCanvas={onOpenCanvas} />
              </div>
            );
          }
          if (kind === 'plan') {
            return (
              <button
                key={message.id}
                type="button"
                onClick={() => onOpenPlan?.(message)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  maxWidth: 520,
                  margin: '4px 0 14px',
                  border: '1px solid #e4e4e7',
                  background: '#fafafa',
                  color: '#18181b',
                  borderRadius: 12,
                  padding: '10px 12px',
                  textAlign: 'left',
                  cursor: 'pointer',
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#71717a' }}>Plan</span>
                <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 14 }}>{planTitle(message.content)}</span>
              </button>
            );
          }
          if (kind === 'debug') {
            return (
              <div key={message.id} style={{ margin: '4px 0 14px', maxWidth: '100%', border: '1px solid #e4e4e7', borderRadius: 12, padding: '12px 14px', background: '#fafafa' }}>
                <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#71717a', marginBottom: 8 }}>
                  Debug
                </div>
                <div style={{ color: '#18181b', fontSize: '0.92rem', lineHeight: 1.6 }}>
                  <ChatMarkdown text={message.content} color="#18181b" onOpenCanvas={onOpenCanvas} />
                </div>
                <button
                  type="button"
                  disabled={sending || !sandboxReady}
                  onClick={() => { void deliver(`Fix this using the evidence below.\n\n${message.content}`, 'agent'); }}
                  style={{
                    marginTop: 10,
                    border: 'none',
                    background: '#18181b',
                    color: '#ffffff',
                    borderRadius: 8,
                    padding: '6px 12px',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: sending || !sandboxReady ? 'default' : 'pointer',
                    opacity: sending || !sandboxReady ? 0.5 : 1,
                  }}
                >
                  Fix
                </button>
              </div>
            );
          }
          const stopped = kind === 'error' && message.content.trim() === 'Stopped.';
          const palette = stopped
            ? { background: '#f4f4f5', color: '#3f3f46', border: '1px solid #e4e4e7', label: '' }
            : {
                user: { background: '#18181b', color: '#ffffff', border: 'none', label: '' },
                error: { background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', label: 'Error' },
              }[kind];
          return (
            <div key={message.id} style={{ display: 'flex', justifyContent: kind === 'user' ? 'flex-end' : 'flex-start', marginBottom: 10 }}>
              <div
                style={{
                  maxWidth: '85%',
                  background: palette.background,
                  color: palette.color,
                  border: palette.border,
                  borderRadius: 12,
                  padding: '8px 12px',
                  fontSize: '0.88rem',
                  lineHeight: 1.5,
                  overflowWrap: 'anywhere',
                }}
              >
                {palette.label && (
                  <div style={{ fontSize: '0.68rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 4, opacity: 0.8 }}>
                    {palette.label}
                  </div>
                )}
                {kind === 'user' ? (
                  <div style={{ whiteSpace: 'pre-wrap' }}>
                    {message.image && (
                      <img src={message.image} alt="" style={{ display: 'block', width: '100%', maxHeight: 180, objectFit: 'contain', borderRadius: 8, marginBottom: 8, background: '#ffffff' }} />
                    )}
                    {message.content}
                  </div>
                ) : (
                  <ChatMarkdown text={message.content} color={palette.color} onOpenCanvas={onOpenCanvas} />
                )}
              </div>
            </div>
          );
        })}
        {working && (
          <div role="status" aria-live="polite" style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 10 }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                background: '#f4f4f5',
                color: '#3f3f46',
                border: '1px solid #e4e4e7',
                borderRadius: 12,
                padding: '8px 12px',
                fontSize: '0.88rem',
              }}
            >
              <Loader2 size={14} className="spin" aria-hidden="true" />
              {agentLabel} is working
              <button
                type="button"
                aria-label="Stop"
                onClick={() => { void stop(); }}
                disabled={stopping}
                style={{ border: 'none', background: 'transparent', color: '#18181b', fontWeight: 600, cursor: stopping ? 'default' : 'pointer', padding: 0 }}
              >
                Stop
              </button>
            </div>
          </div>
        )}
      </div>
      <div style={{ padding: '8px 10px calc(10px + env(safe-area-inset-bottom))' }}>
        {error && <div style={{ color: '#b91c1c', fontSize: '0.75rem', marginBottom: 6 }}>{error}</div>}
        <div
          ref={composerRef}
          className="agent-runtime-chat-composer"
          style={{
            background: '#ffffff',
            border: '1px solid #e4e4e7',
            boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
            borderRadius: 12,
          }}
        >
          <style>{`.agent-runtime-chat-composer textarea::placeholder { color: #a1a1aa; }`}</style>
          <AttachmentChips files={files} onRemove={(index) => setFiles((current) => current.filter((_, item) => item !== index))} />
          <textarea
            ref={textareaRef}
            value={draft}
            aria-label={`Message ${agentLabel}`}
            placeholder={`Message ${agentLabel}`}
            rows={2}
            disabled={sending || !sandboxReady}
            onChange={(event) => setDraft(event.target.value)}
            onPaste={(event) => {
              const picked = Array.from(event.clipboardData?.files || []);
              if (!picked.length) return;
              event.preventDefault();
              setFiles((current) => [...current, ...picked]);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
            style={{
              display: 'block',
              width: '100%',
              minHeight: 52,
              boxSizing: 'border-box',
              resize: 'none',
              border: 'none',
              outline: 'none',
              padding: '12px 14px 4px',
              font: 'inherit',
              fontSize: 16,
              lineHeight: 1.45,
              color: '#18181b',
              background: 'transparent',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px 8px' }}>
            <ComposerPlusButton
              disabled={sending || !sandboxReady}
              onAddFiles={(incoming) => setFiles((current) => [...current, ...incoming])}
            />
            {showLlm && <RuntimeModePicker upward />}
            {showLlm && (
              <div style={{ position: 'relative' }}>
                <button
                  type="button"
                  aria-label="Select model"
                  aria-expanded={llmOpen}
                  onClick={() => setLlmOpen((open) => !open)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    maxWidth: 220,
                    border: 'none',
                    background: llmOpen ? '#f4f4f5' : 'transparent',
                    color: '#3f3f46',
                    borderRadius: 6,
                    fontSize: 13,
                    cursor: 'pointer',
                    padding: '4px 6px',
                  }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {selectedLlm?.label || selectedLlm?.id || llmModel || 'Model'}
                  </span>
                  <ChevronDown size={13} />
                </button>
                {llmOpen && (
                  <div
                    role="menu"
                    style={{
                      position: 'absolute',
                      bottom: '100%',
                      left: 0,
                      zIndex: 20,
                      minWidth: 200,
                      maxHeight: 220,
                      overflow: 'auto',
                      marginBottom: 6,
                      background: '#ffffff',
                      border: '1px solid #e4e4e7',
                      borderRadius: 10,
                      boxShadow: '0 12px 32px rgba(15, 23, 42, 0.12)',
                      padding: 4,
                    }}
                  >
                    {llmModelsLoading && <div style={{ padding: '7px 8px', color: '#71717a', fontSize: 13 }}>Loading models…</div>}
                    {!llmModelsLoading && llmModels.length === 0 && (
                      <div style={{ padding: '7px 8px', color: '#71717a', fontSize: 13 }}>No AI Gateway models.</div>
                    )}
                    {llmModels.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          onLlmModelChange?.(item.id);
                          setLlmOpen(false);
                        }}
                        style={{
                          display: 'block',
                          width: '100%',
                          textAlign: 'left',
                          border: 'none',
                          background: item.id === llmModel ? '#f4f4f5' : 'transparent',
                          color: '#18181b',
                          borderRadius: 6,
                          padding: '7px 8px',
                          fontSize: 13,
                          cursor: 'pointer',
                        }}
                      >
                        {item.label || item.id}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <span style={{ flex: 1 }} />
            {working ? (
              <button
                type="button"
                aria-label="Stop"
                title="Stop"
                disabled={stopping || !sandboxReady}
                onClick={() => { void stop(); }}
                style={{
                  width: 28,
                  height: 28,
                  border: 'none',
                  borderRadius: 999,
                  background: stopping || !sandboxReady ? '#f4f4f5' : '#18181b',
                  color: stopping || !sandboxReady ? '#a1a1aa' : '#ffffff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: stopping || !sandboxReady ? 'default' : 'pointer',
                  flexShrink: 0,
                }}
              >
                {stopping ? <Loader2 size={15} className="spin" /> : <Square size={11} fill="currentColor" />}
              </button>
            ) : (
            <button
              type="button"
              aria-label="Send message"
              disabled={sending || !sandboxReady || (!draft.trim() && files.length === 0)}
              onClick={send}
              style={{
                width: 28,
                height: 28,
                border: 'none',
                borderRadius: 999,
                background: sending || !sandboxReady || (!draft.trim() && files.length === 0) ? '#f4f4f5' : '#18181b',
                color: sending || !sandboxReady || (!draft.trim() && files.length === 0) ? '#a1a1aa' : '#ffffff',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: sending || !sandboxReady || (!draft.trim() && files.length === 0) ? 'default' : 'pointer',
                flexShrink: 0,
              }}
            >
              {sending ? <Loader2 size={15} className="spin" /> : <ArrowUp size={15} />}
            </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
