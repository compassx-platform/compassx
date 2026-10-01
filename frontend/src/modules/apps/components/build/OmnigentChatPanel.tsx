import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  Send,
  Loader2,
  Bot,
  User,
  Trash2,
  Terminal,
  FileCode,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  RefreshCw,
  HelpCircle,
  Zap,
  Code2,
  CornerDownLeft,
  AlertCircle,
  Wand2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AppItem, DevSessionStatus } from '../../hooks/useApps';
import {
  OmnigentAgent,
  OmnigentSession,
  ChatMessage,
  useOmnigentAgents,
  useOmnigentMessages,
  useSendOmnigentPrompt,
  useClearOmnigentSession,
} from '../../hooks/useOmnigentChat';
import { useToast } from '@/lib/toast';

interface OmnigentChatPanelProps {
  app: AppItem;
  resolvedAppId: string;
  session?: OmnigentSession;
  devStatus?: DevSessionStatus;
  isDevPodRunning: boolean;
  onCodeUpdated?: () => void;
}

const QUICK_PROMPTS = [
  'Add modern dark/light mode toggle with smooth transition',
  'Connect to CompassX catalog tables and display a data grid',
  'Create a responsive dashboard navbar with search and filters',
  'Add metric summary cards with percentage indicators',
];

export function OmnigentChatPanel({
  app,
  resolvedAppId,
  session,
  devStatus,
  isDevPodRunning,
  onCodeUpdated,
}: OmnigentChatPanelProps) {
  const toast = useToast();
  const [promptText, setPromptText] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('polly');
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [copiedCodeId, setCopiedCodeId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: agents = [] } = useOmnigentAgents(resolvedAppId);
  const sessionId = session?.session_id;

  const {
    data: serverMessages = [],
    refetch: refetchMessages,
    isFetching: isFetchingMessages,
  } = useOmnigentMessages(resolvedAppId, sessionId, isSending);

  const sendPromptMutation = useSendOmnigentPrompt();
  const clearSessionMutation = useClearOmnigentSession();

  // Merge server messages with optimistic user messages
  const allMessages: ChatMessage[] = React.useMemo(() => {
    if (!serverMessages || serverMessages.length === 0) {
      return optimisticMessages;
    }
    // If server has returned items, reconcile
    return serverMessages;
  }, [serverMessages, optimisticMessages]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allMessages, isSending]);

  // Adjust textarea height automatically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [promptText]);

  async function handleSendPrompt(textToSend?: string) {
    const finalPrompt = (textToSend ?? promptText).trim();
    if (!finalPrompt || isSending) return;

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp_user_${Date.now()}`,
      role: 'user',
      type: 'message',
      content: finalPrompt,
      created_at: new Date().toISOString(),
    };
    setOptimisticMessages((prev) => [...prev, tempUserMsg]);
    setPromptText('');
    setIsSending(true);

    try {
      await sendPromptMutation.mutateAsync({
        appId: resolvedAppId,
        prompt: finalPrompt,
        sessionId,
        agentName: selectedAgent,
        workspaceId: session?.workspace_id,
      });

      // Poll for response & trigger hot-reload check
      refetchMessages();
      if (onCodeUpdated) {
        setTimeout(onCodeUpdated, 2500);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to send prompt to Omnigent AI.');
    } finally {
      setIsSending(false);
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendPrompt();
    }
  }

  async function handleClearHistory() {
    if (!confirm('Clear Omnigent conversation history for this workspace?')) return;
    try {
      await clearSessionMutation.mutateAsync({
        appId: resolvedAppId,
        workspaceId: session?.workspace_id,
        sessionId,
      });
      setOptimisticMessages([]);
      toast.success('Conversation history cleared.');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to clear session.');
    }
  }

  function toggleToolExpand(toolId: string) {
    setExpandedTools((prev) => ({ ...prev, [toolId]: !prev[toolId] }));
  }

  function handleCopyCode(code: string, id: string) {
    navigator.clipboard.writeText(code);
    setCopiedCodeId(id);
    setTimeout(() => setCopiedCodeId(null), 2000);
    toast.success('Code snippet copied to clipboard');
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        background: '#0b0f19',
        color: '#f1f5f9',
        overflow: 'hidden',
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          background: '#131c2e',
          borderBottom: '1px solid #1e293b',
          gap: 12,
          minHeight: 48,
        }}
      >
        {/* Left: Branding & Agent Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
            }}
          >
            <Sparkles size={15} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#f8fafc' }}>
                Omnigent AI Studio
              </span>
              <span
                style={{
                  fontSize: '0.68rem',
                  padding: '1px 6px',
                  borderRadius: 10,
                  background: 'rgba(99, 102, 241, 0.2)',
                  color: '#a5b4fc',
                  fontWeight: 600,
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                }}
              >
                v1.0
              </span>
            </div>
          </div>
        </div>

        {/* Right: Agent Dropdown & Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Agent Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>Agent:</span>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              style={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 6,
                color: '#e2e8f0',
                fontSize: '0.75rem',
                fontWeight: 600,
                padding: '4px 8px',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="polly">Polly (Full-Stack)</option>
              <option value="antigravity-native-ui">Antigravity (Pair Programmer)</option>
              <option value="opencode-native-ui">OpenCode (Terminal & FS)</option>
              <option value="codex-native-ui">Codex (UI & Components)</option>
            </select>
          </div>

          {/* Clear Button */}
          <button
            onClick={handleClearHistory}
            title="Clear Chat History"
            style={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              color: '#94a3b8',
              padding: '5px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.72rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Trash2 size={13} />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Messages Transcript Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 20px 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
        }}
      >
        {allMessages.length === 0 ? (
          /* Empty Welcome State */
          <div
            style={{
              margin: 'auto 0',
              padding: '28px 20px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              gap: 16,
              maxWidth: 520,
              alignSelf: 'center',
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 16,
                background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.2) 100%)',
                border: '1px solid rgba(99, 102, 241, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#a5b4fc',
              }}
            >
              <Bot size={28} />
            </div>

            <div>
              <h4 style={{ margin: '0 0 6px', fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                How can I help you build {app.name}?
              </h4>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.5 }}>
                Describe any feature, UI change, or bug fix. Omnigent AI executes commands, modifies codebase files inside the dev sandbox, and previews changes live in real-time.
              </p>
            </div>

            {/* Quick Starter Chips */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%', marginTop: 8 }}>
              {QUICK_PROMPTS.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendPrompt(prompt)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '9px 14px',
                    borderRadius: 8,
                    background: '#131c2e',
                    border: '1px solid #1e293b',
                    color: '#cbd5e1',
                    fontSize: '0.78rem',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#1e293b';
                    e.currentTarget.style.borderColor = '#6366f1';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#131c2e';
                    e.currentTarget.style.borderColor = '#1e293b';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Wand2 size={13} color="#818cf8" />
                    <span>{prompt}</span>
                  </div>
                  <CornerDownLeft size={12} color="#64748b" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message Stream */
          allMessages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const isTool = msg.type === 'tool_call' || msg.type === 'tool_result' || !!msg.tool;

            if (isTool && msg.tool) {
              const toolKey = msg.id || `tool_${index}`;
              const isExpanded = !!expandedTools[toolKey];
              return (
                <div
                  key={toolKey}
                  style={{
                    background: '#131c2e',
                    border: '1px solid #1e293b',
                    borderRadius: 8,
                    overflow: 'hidden',
                    fontSize: '0.78rem',
                  }}
                >
                  <div
                    onClick={() => toggleToolExpand(toolKey)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      cursor: 'pointer',
                      background: '#0f172a',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Terminal size={14} color="#38bdf8" />
                      <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                        {msg.tool.name || 'Tool Execution'}
                      </span>
                      {msg.tool.status === 'completed' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#22c55e', fontSize: '0.72rem' }}>
                          <CheckCircle2 size={12} /> Success
                        </span>
                      ) : msg.tool.status === 'error' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#ef4444', fontSize: '0.72rem' }}>
                          <XCircle size={12} /> Error
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#38bdf8', fontSize: '0.72rem' }}>
                          <Loader2 size={12} className="spin" /> Running
                        </span>
                      )}
                    </div>
                    <div>
                      {isExpanded ? <ChevronDown size={14} color="#94a3b8" /> : <ChevronRight size={14} color="#94a3b8" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{ padding: '10px 12px', background: '#090d16', borderTop: '1px solid #1e293b', fontFamily: 'monospace', fontSize: '0.74rem', color: '#94a3b8', whiteSpace: 'pre-wrap', maxHeight: 220, overflowY: 'auto' }}>
                      {typeof msg.tool.input === 'object' ? JSON.stringify(msg.tool.input, null, 2) : msg.tool.input}
                      {msg.tool.output && (
                        <div style={{ marginTop: 8, color: '#e2e8f0', borderTop: '1px dashed #334155', paddingTop: 6 }}>
                          {typeof msg.tool.output === 'object' ? JSON.stringify(msg.tool.output, null, 2) : msg.tool.output}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <div
                key={msg.id || index}
                style={{
                  display: 'flex',
                  gap: 12,
                  alignItems: 'flex-start',
                  flexDirection: isUser ? 'row-reverse' : 'row',
                }}
              >
                {/* Avatar */}
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 10,
                    background: isUser
                      ? 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)'
                      : 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                    flexShrink: 0,
                    boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                  }}
                >
                  {isUser ? <User size={16} /> : <Bot size={16} />}
                </div>

                {/* Bubble Container */}
                <div
                  style={{
                    maxWidth: '85%',
                    background: isUser ? '#1e293b' : '#131c2e',
                    border: isUser ? '1px solid #334155' : '1px solid #1e293b',
                    borderRadius: isUser ? '12px 2px 12px 12px' : '2px 12px 12px 12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '0.84rem',
                    lineHeight: 1.6,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                  }}
                >
                  {/* Header Line */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, gap: 10 }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 600, color: isUser ? '#93c5fd' : '#a5b4fc' }}>
                      {isUser ? 'You' : msg.agent || selectedAgent}
                    </span>
                    {msg.created_at && (
                      <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>

                  {/* Message Content with Markdown */}
                  <div className="prose prose-invert" style={{ fontSize: '0.84rem', color: '#e2e8f0' }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const codeText = String(children).replace(/\n$/, '');
                          if (inline) {
                            return (
                              <code
                                style={{
                                  background: '#0f172a',
                                  padding: '2px 6px',
                                  borderRadius: 4,
                                  color: '#38bdf8',
                                  fontSize: '0.8em',
                                  fontFamily: 'monospace',
                                }}
                                {...props}
                              >
                                {children}
                              </code>
                            );
                          }
                          const codeId = `code_${Math.random()}`;
                          return (
                            <div style={{ position: 'relative', margin: '8px 0', borderRadius: 6, overflow: 'hidden', background: '#090d16', border: '1px solid #1e293b' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 10px', background: '#0f172a', borderBottom: '1px solid #1e293b', fontSize: '0.7rem', color: '#94a3b8' }}>
                                <span>Code Snippet</span>
                                <button
                                  onClick={() => handleCopyCode(codeText, codeId)}
                                  style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
                                >
                                  {copiedCodeId === codeId ? <Check size={12} color="#22c55e" /> : <Copy size={12} />}
                                  <span>{copiedCodeId === codeId ? 'Copied' : 'Copy'}</span>
                                </button>
                              </div>
                              <pre style={{ padding: '10px 12px', margin: 0, overflowX: 'auto', fontSize: '0.78rem', color: '#f8fafc', fontFamily: 'monospace' }}>
                                <code>{children}</code>
                              </pre>
                            </div>
                          );
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            );
          })
        )}

        {/* Live Thinking Indicator */}
        {isSending && (
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                flexShrink: 0,
              }}
            >
              <Bot size={16} />
            </div>

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                borderRadius: 12,
                background: '#131c2e',
                border: '1px solid #1e293b',
                color: '#a5b4fc',
                fontSize: '0.8rem',
              }}
            >
              <Loader2 size={14} className="spin" />
              <span>Omnigent AI is thinking and applying changes...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Prompt Composer */}
      <div
        style={{
          padding: '12px 16px',
          background: '#131c2e',
          borderTop: '1px solid #1e293b',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: 8,
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 10,
            padding: '8px 12px',
          }}
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask ${selectedAgent} to build, modify, or fix ${app.name}...`}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#f8fafc',
              fontSize: '0.86rem',
              lineHeight: 1.4,
              resize: 'none',
              maxHeight: 180,
              fontFamily: 'inherit',
            }}
          />

          <button
            onClick={() => handleSendPrompt()}
            disabled={!promptText.trim() || isSending}
            title="Send Instruction (Enter)"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 34,
              height: 34,
              borderRadius: 8,
              background: promptText.trim() && !isSending ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' : '#334155',
              border: 'none',
              color: '#ffffff',
              cursor: promptText.trim() && !isSending ? 'pointer' : 'not-allowed',
              flexShrink: 0,
              boxShadow: promptText.trim() && !isSending ? '0 2px 8px rgba(99, 102, 241, 0.4)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            {isSending ? <Loader2 size={16} className="spin" /> : <Send size={15} />}
          </button>
        </div>

        {/* Footer Shortcut & Status Hint */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: '#64748b' }}>
          <span>
            Press <strong style={{ color: '#94a3b8' }}>Enter</strong> to send • <strong style={{ color: '#94a3b8' }}>Shift+Enter</strong> for newline
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {isDevPodRunning ? (
              <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} /> Connected to pod ({devStatus?.dev_port || 9201})
              </span>
            ) : (
              <span style={{ color: '#f59e0b' }}>Pod offline • Changes will queue</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
