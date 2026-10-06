import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Sparkles,
  Send,
  Loader2,
  Bot,
  User,
  Trash2,
  Terminal as TerminalIcon,
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
  Cpu,
  Search,
  X,
  Layout,
  Layers,
  TerminalSquare,
  Flame,
  ShieldCheck,
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
import { DevTerminal } from '../DevTerminal';
import { useToast } from '@/lib/toast';

interface OmnigentChatPanelProps {
  app: AppItem;
  resolvedAppId: string;
  session?: OmnigentSession;
  devStatus?: DevSessionStatus;
  isDevPodRunning: boolean;
  onCodeUpdated?: () => void;
}

type StudioViewMode = 'chat' | 'cli' | 'split';

const DEFAULT_AGENTS: OmnigentAgent[] = [
  {
    id: 'agent_claude_code',
    name: 'claude-code',
    display_name: 'Claude Code',
    provider: 'Anthropic',
    description: 'Autonomous agentic coding CLI with tool calling, file patch editing, and terminal bash execution',
    role: 'Autonomous Coding Agent',
    badge: 'Claude 3.7',
    color: '#d97706',
    icon: 'terminal',
  },
  {
    id: 'agent_antigravity',
    name: 'antigravity-native-ui',
    display_name: 'Antigravity',
    provider: 'Google DeepMind',
    description: 'Google DeepMind Antigravity Pair Programmer for system architecture, refactoring, and verification',
    role: 'Lead Architect & Pair Programmer',
    badge: 'Advanced AGY',
    color: '#6366f1',
    icon: 'sparkles',
  },
  {
    id: 'agent_polly',
    name: 'polly',
    display_name: 'Omnigent Polly',
    provider: 'Omnigent',
    description: 'Full-stack AI developer for general app building, styling, state management, and debugging',
    role: 'Full-Stack AI Developer',
    badge: 'Generalist',
    color: '#8b5cf6',
    icon: 'bot',
  },
  {
    id: 'agent_opencode',
    name: 'opencode-native-ui',
    display_name: 'OpenCode',
    provider: 'OpenCode',
    description: 'OpenCode terminal and file system execution agent with direct shell tool access',
    role: 'Terminal & Shell Specialist',
    badge: 'Shell First',
    color: '#10b981',
    icon: 'code',
  },
  {
    id: 'agent_codex',
    name: 'codex-native-ui',
    display_name: 'Codex UI',
    provider: 'OpenAI',
    description: 'Codex UI assistant specialized in frontend design, responsive styling, and React components',
    role: 'Frontend Specialist',
    badge: 'UI & Components',
    color: '#0284c7',
    icon: 'layout',
  },
  {
    id: 'agent_gemini_cli',
    name: 'gemini-cli',
    display_name: 'Gemini CLI',
    provider: 'Google',
    description: 'Google Gemini 2.0 Pro ultra-fast code intelligence and multi-turn refactoring',
    role: 'Fast Reasoning Agent',
    badge: 'Gemini 2.0',
    color: '#ec4899',
    icon: 'zap',
  },
  {
    id: 'agent_deepseek_coder',
    name: 'deepseek-coder',
    display_name: 'DeepSeek Coder',
    provider: 'DeepSeek',
    description: 'DeepSeek R1 / V3 deep mathematical reasoning, complex algorithms, and backend logic',
    role: 'Logic & Algorithm Specialist',
    badge: 'Deep Reasoning',
    color: '#06b6d4',
    icon: 'cpu',
  },
];

const AGENT_PROMPTS: Record<string, string[]> = {
  'claude-code': [
    'Run a full codebase audit and fix any linting/compilation warnings',
    'Implement responsive navigation bar with search and active routing',
    'Connect to CompassX catalog APIs with authentication headers',
  ],
  'antigravity-native-ui': [
    'Refactor architecture into clean reusable modular components',
    'Optimize rendering performance and eliminate unnecessary re-renders',
    'Add comprehensive error boundaries and fallback state screens',
  ],
  polly: [
    'Add modern dark/light mode toggle with smooth transition',
    'Connect to CompassX catalog tables and display a live data grid',
    'Create metric summary cards with trend percentage indicators',
  ],
  'opencode-native-ui': [
    'Inspect package dependencies and run build validation',
    'Check git status and display modified workspace files',
    'Execute unit test suite and report results',
  ],
  'codex-native-ui': [
    'Enhance UI layout with modern gradients, subtle shadows, and borders',
    'Create an interactive modal dialog for adding new items',
    'Improve mobile viewport responsiveness and padding',
  ],
};

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
  const [selectedAgentName, setSelectedAgentName] = useState('claude-code');
  const [viewMode, setViewMode] = useState<StudioViewMode>('chat');
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [agentSearchQuery, setAgentSearchQuery] = useState('');

  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [copiedCodeId, setCopiedCodeId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: serverAgents = [] } = useOmnigentAgents(resolvedAppId);
  const allAgents: OmnigentAgent[] = useMemo(() => {
    if (serverAgents && serverAgents.length > 0) {
      // Merge with default details for richer UI
      return DEFAULT_AGENTS.map((def) => {
        const found = serverAgents.find((s: OmnigentAgent) => s.name === def.name || s.id === def.id);
        return found ? { ...def, ...found } : def;
      });
    }
    return DEFAULT_AGENTS;
  }, [serverAgents]);

  const activeAgent = useMemo(() => {
    return (
      allAgents.find((a) => a.name === selectedAgentName || a.id === selectedAgentName) ||
      allAgents[0]
    );
  }, [allAgents, selectedAgentName]);

  const filteredAgents = useMemo(() => {
    const q = agentSearchQuery.trim().toLowerCase();
    if (!q) return allAgents;
    return allAgents.filter(
      (a) =>
        (a.display_name && a.display_name.toLowerCase().includes(q)) ||
        a.name.toLowerCase().includes(q) ||
        (a.provider && a.provider.toLowerCase().includes(q)) ||
        (a.description && a.description.toLowerCase().includes(q)) ||
        (a.role && a.role.toLowerCase().includes(q))
    );
  }, [allAgents, agentSearchQuery]);

  const sessionId = session?.session_id;

  const {
    data: serverMessages = [],
    refetch: refetchMessages,
  } = useOmnigentMessages(resolvedAppId, sessionId, isSending);

  const sendPromptMutation = useSendOmnigentPrompt();
  const clearSessionMutation = useClearOmnigentSession();

  const allMessages: ChatMessage[] = useMemo(() => {
    if (!serverMessages || serverMessages.length === 0) {
      return optimisticMessages;
    }
    return serverMessages;
  }, [serverMessages, optimisticMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allMessages, isSending]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [promptText]);

  async function handleSendPrompt(textToSend?: string) {
    const finalPrompt = (textToSend ?? promptText).trim();
    if (!finalPrompt || isSending) return;

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
        agentName: activeAgent.name,
        workspaceId: session?.workspace_id,
      });

      refetchMessages();
      if (onCodeUpdated) {
        setTimeout(onCodeUpdated, 2000);
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

  const quickPromptsForCurrentAgent =
    AGENT_PROMPTS[activeAgent.name] || AGENT_PROMPTS['polly'];

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
        position: 'relative',
      }}
    >
      {/* Top Header Bar: Agent Selector & View Mode Switcher */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          background: '#131c2e',
          borderBottom: '1px solid #1e293b',
          gap: 10,
          minHeight: 46,
          flexWrap: 'wrap',
          zIndex: 20,
        }}
      >
        {/* Left: Active Agent Trigger Button */}
        <button
          onClick={() => setIsAgentModalOpen(true)}
          title="Change Active AI Coding Agent"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '4px 10px',
            borderRadius: 8,
            background: '#0f172a',
            border: `1px solid ${activeAgent.color || '#6366f1'}50`,
            color: '#f8fafc',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <div
            style={{
              width: 20,
              height: 20,
              borderRadius: 5,
              background: activeAgent.color || '#6366f1',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
            }}
          >
            {activeAgent.icon === 'terminal' ? (
              <TerminalIcon size={12} />
            ) : activeAgent.icon === 'sparkles' ? (
              <Sparkles size={12} />
            ) : activeAgent.icon === 'code' ? (
              <Code2 size={12} />
            ) : activeAgent.icon === 'layout' ? (
              <Layout size={12} />
            ) : (
              <Bot size={12} />
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#f8fafc' }}>
              {activeAgent.display_name || activeAgent.name}
            </span>
            <span
              style={{
                fontSize: '0.66rem',
                padding: '1px 6px',
                borderRadius: 4,
                background: 'rgba(255,255,255,0.08)',
                color: '#94a3b8',
                fontWeight: 600,
              }}
            >
              {activeAgent.badge || activeAgent.provider || 'AI'}
            </span>
          </div>

          <ChevronDown size={14} color="#94a3b8" />
        </button>

        {/* Center/Right: View Mode Switcher (Chat vs. CLI vs. Split) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 2, background: '#090d16', padding: '2px', borderRadius: 8 }}>
            <button
              onClick={() => setViewMode('chat')}
              title="AI Conversational Chat UI"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: 6,
                border: 'none',
                background: viewMode === 'chat' ? '#3b82f6' : 'transparent',
                color: viewMode === 'chat' ? '#ffffff' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Bot size={13} />
              <span>Chat AI</span>
            </button>

            <button
              onClick={() => setViewMode('cli')}
              title="Omnigent Terminal / CLI UI Mode"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: 6,
                border: 'none',
                background: viewMode === 'cli' ? '#3b82f6' : 'transparent',
                color: viewMode === 'cli' ? '#ffffff' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <TerminalIcon size={13} />
              <span>CLI UI</span>
            </button>

            <button
              onClick={() => setViewMode('split')}
              title="Dual Stack: Chat + CLI Terminal Split"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 8px',
                borderRadius: 6,
                border: 'none',
                background: viewMode === 'split' ? '#3b82f6' : 'transparent',
                color: viewMode === 'split' ? '#ffffff' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Layers size={13} />
              <span>Dual</span>
            </button>
          </div>

          {/* Clear History Button */}
          <button
            onClick={handleClearHistory}
            title="Clear Chat History"
            style={{
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: 6,
              color: '#94a3b8',
              padding: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.72rem',
              cursor: 'pointer',
            }}
          >
            <Trash2 size={12} />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Main Studio Body (Chat / CLI / Split) */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* 1. CHAT UI MODE */}
        {(viewMode === 'chat' || viewMode === 'split') && (
          <div
            style={{
              flex: viewMode === 'split' ? '0 0 55%' : '1',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              borderBottom: viewMode === 'split' ? '1px solid #334155' : 'none',
            }}
          >
            {/* Messages Transcript Scroll Area */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '16px 16px 10px',
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
              }}
            >
              {allMessages.length === 0 ? (
                /* Empty Welcome State */
                <div
                  style={{
                    margin: 'auto 0',
                    padding: '20px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    textAlign: 'center',
                    gap: 14,
                    maxWidth: 500,
                    alignSelf: 'center',
                  }}
                >
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: 14,
                      background: `linear-gradient(135deg, ${activeAgent.color || '#6366f1'}30 0%, ${activeAgent.color || '#6366f1'}15 100%)`,
                      border: `1px solid ${activeAgent.color || '#6366f1'}60`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: activeAgent.color || '#6366f1',
                    }}
                  >
                    {activeAgent.icon === 'terminal' ? (
                      <TerminalIcon size={26} />
                    ) : (
                      <Sparkles size={26} />
                    )}
                  </div>

                  <div>
                    <h4 style={{ margin: '0 0 6px', fontSize: '1.02rem', fontWeight: 700, color: '#f8fafc' }}>
                      {activeAgent.display_name} Active
                    </h4>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5 }}>
                      {activeAgent.description}
                    </p>
                  </div>

                  {/* Quick Starter Chips */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 7, width: '100%', marginTop: 6 }}>
                    {quickPromptsForCurrentAgent.map((prompt, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSendPrompt(prompt)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          borderRadius: 8,
                          background: '#131c2e',
                          border: '1px solid #1e293b',
                          color: '#cbd5e1',
                          fontSize: '0.76rem',
                          textAlign: 'left',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#1e293b';
                          e.currentTarget.style.borderColor = activeAgent.color || '#6366f1';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#131c2e';
                          e.currentTarget.style.borderColor = '#1e293b';
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <Wand2 size={13} color={activeAgent.color || '#818cf8'} />
                          <span>{prompt}</span>
                        </div>
                        <CornerDownLeft size={11} color="#64748b" />
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
                            padding: '7px 12px',
                            cursor: 'pointer',
                            background: '#0f172a',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <TerminalIcon size={13} color="#38bdf8" />
                            <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                              {msg.tool.name || 'Tool Execution'}
                            </span>
                            {msg.tool.status === 'completed' ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#22c55e', fontSize: '0.7rem' }}>
                                <CheckCircle2 size={11} /> Completed
                              </span>
                            ) : msg.tool.status === 'error' ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#ef4444', fontSize: '0.7rem' }}>
                                <XCircle size={11} /> Error
                              </span>
                            ) : (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#38bdf8', fontSize: '0.7rem' }}>
                                <Loader2 size={11} className="spin" /> Executing
                              </span>
                            )}
                          </div>
                          <div>
                            {isExpanded ? <ChevronDown size={13} color="#94a3b8" /> : <ChevronRight size={13} color="#94a3b8" />}
                          </div>
                        </div>

                        {isExpanded && (
                          <div style={{ padding: '9px 12px', background: '#090d16', borderTop: '1px solid #1e293b', fontFamily: 'monospace', fontSize: '0.74rem', color: '#94a3b8', whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto' }}>
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
                        gap: 10,
                        alignItems: 'flex-start',
                        flexDirection: isUser ? 'row-reverse' : 'row',
                      }}
                    >
                      {/* Avatar */}
                      <div
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: 8,
                          background: isUser
                            ? 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)'
                            : activeAgent.color || '#6366f1',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#ffffff',
                          flexShrink: 0,
                          boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                        }}
                      >
                        {isUser ? <User size={15} /> : <Bot size={15} />}
                      </div>

                      {/* Bubble Container */}
                      <div
                        style={{
                          maxWidth: '86%',
                          background: isUser ? '#1e293b' : '#131c2e',
                          border: isUser ? '1px solid #334155' : '1px solid #1e293b',
                          borderRadius: isUser ? '12px 2px 12px 12px' : '2px 12px 12px 12px',
                          padding: '10px 14px',
                          color: '#f8fafc',
                          fontSize: '0.82rem',
                          lineHeight: 1.55,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5, gap: 10 }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: isUser ? '#93c5fd' : activeAgent.color || '#a5b4fc' }}>
                            {isUser ? 'You' : msg.agent || activeAgent.display_name}
                          </span>
                          {msg.created_at && (
                            <span style={{ fontSize: '0.66rem', color: '#64748b' }}>
                              {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          )}
                        </div>

                        <div className="prose prose-invert" style={{ fontSize: '0.82rem', color: '#e2e8f0' }}>
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              code({ node, inline, className, children, ...props }: any) {
                                const codeText = String(children).replace(/\n$/, '');
                                if (inline) {
                                  return (
                                    <code
                                      style={{
                                        background: '#090d16',
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
                                    <pre style={{ padding: '10px 12px', margin: 0, overflowX: 'auto', fontSize: '0.76rem', color: '#f8fafc', fontFamily: 'monospace' }}>
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

              {/* Thinking Indicator */}
              {isSending && (
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 8,
                      background: activeAgent.color || '#6366f1',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#ffffff',
                      flexShrink: 0,
                    }}
                  >
                    <Bot size={15} />
                  </div>

                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 12px',
                      borderRadius: 10,
                      background: '#131c2e',
                      border: '1px solid #1e293b',
                      color: '#a5b4fc',
                      fontSize: '0.78rem',
                    }}
                  >
                    <Loader2 size={13} className="spin" />
                    <span>{activeAgent.display_name} is analyzing and applying code changes...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Prompt Composer */}
            <div
              style={{
                padding: '10px 14px',
                background: '#131c2e',
                borderTop: '1px solid #1e293b',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: 8,
                  background: '#090d16',
                  border: '1px solid #334155',
                  borderRadius: 10,
                  padding: '7px 10px',
                }}
              >
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Instruct ${activeAgent.display_name} to build, edit, or fix ${app.name}...`}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: '#f8fafc',
                    fontSize: '0.84rem',
                    lineHeight: 1.4,
                    resize: 'none',
                    maxHeight: 160,
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
                    width: 32,
                    height: 32,
                    borderRadius: 7,
                    background: promptText.trim() && !isSending ? (activeAgent.color || '#6366f1') : '#334155',
                    border: 'none',
                    color: '#ffffff',
                    cursor: promptText.trim() && !isSending ? 'pointer' : 'not-allowed',
                    flexShrink: 0,
                    boxShadow: promptText.trim() && !isSending ? `0 2px 8px ${activeAgent.color || '#6366f1'}50` : 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {isSending ? <Loader2 size={15} className="spin" /> : <Send size={14} />}
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.68rem', color: '#64748b' }}>
                <span>
                  <strong style={{ color: '#94a3b8' }}>Enter</strong> send • <strong style={{ color: '#94a3b8' }}>Shift+Enter</strong> newline
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isDevPodRunning ? (
                    <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} /> Pod connected
                    </span>
                  ) : (
                    <span style={{ color: '#f59e0b' }}>Pod offline</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. CLI / TERMINAL UI MODE */}
        {(viewMode === 'cli' || viewMode === 'split') && (
          <div
            style={{
              flex: viewMode === 'split' ? '0 0 45%' : '1',
              display: 'flex',
              flexDirection: 'column',
              background: '#ffffff',
              overflow: 'hidden',
              position: 'relative',
            }}
          >
            <DevTerminal
              appId={resolvedAppId}
              appName={app.name}
              workspaceId={session?.workspace_id}
              workspaceName={session?.workspace_name}
              isDevPodRunning={isDevPodRunning}
            />
          </div>
        )}
      </div>

      {/* ── AGENT SELECTOR MODAL ────────────────────────────────────────────── */}
      {isAgentModalOpen && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(9, 13, 22, 0.85)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
            zIndex: 50,
          }}
          onClick={() => setIsAgentModalOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 580,
              background: '#131c2e',
              border: '1px solid #334155',
              borderRadius: 14,
              boxShadow: '0 16px 40px rgba(0, 0, 0, 0.6)',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '85vh',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '14px 18px',
                borderBottom: '1px solid #1e293b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Sparkles size={18} color="#8b5cf6" />
                <span style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
                  Select Omnigent AI Agent
                </span>
              </div>

              <button
                onClick={() => setIsAgentModalOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: 4,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Search Filter Bar */}
            <div style={{ padding: '12px 18px', borderBottom: '1px solid #1e293b', background: '#0f172a' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: '#131c2e',
                  border: '1px solid #334155',
                  borderRadius: 8,
                  padding: '6px 12px',
                }}
              >
                <Search size={14} color="#64748b" />
                <input
                  type="text"
                  placeholder="Search agents by name, provider, or capability..."
                  value={agentSearchQuery}
                  onChange={(e) => setAgentSearchQuery(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: '#f8fafc',
                    fontSize: '0.82rem',
                  }}
                  autoFocus
                />
              </div>
            </div>

            {/* Agent Grid */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {filteredAgents.map((agent) => {
                const isSelected = activeAgent.name === agent.name;
                return (
                  <div
                    key={agent.id || agent.name}
                    onClick={() => {
                      setSelectedAgentName(agent.name);
                      setIsAgentModalOpen(false);
                      toast.success(`Switched AI Agent to ${agent.display_name || agent.name}`);
                    }}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 10,
                      background: isSelected ? 'rgba(99, 102, 241, 0.15)' : '#0f172a',
                      border: isSelected ? `2px solid ${agent.color || '#6366f1'}` : '1px solid #1e293b',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 12,
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = '#1a243b';
                        e.currentTarget.style.borderColor = '#334155';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = '#0f172a';
                        e.currentTarget.style.borderColor = '#1e293b';
                      }
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        background: agent.color || '#6366f1',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#ffffff',
                        flexShrink: 0,
                        marginTop: 2,
                      }}
                    >
                      {agent.icon === 'terminal' ? (
                        <TerminalIcon size={18} />
                      ) : agent.icon === 'sparkles' ? (
                        <Sparkles size={18} />
                      ) : agent.icon === 'code' ? (
                        <Code2 size={18} />
                      ) : agent.icon === 'layout' ? (
                        <Layout size={18} />
                      ) : agent.icon === 'zap' ? (
                        <Zap size={18} />
                      ) : (
                        <Bot size={18} />
                      )}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f8fafc' }}>
                            {agent.display_name || agent.name}
                          </span>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              padding: '1px 6px',
                              borderRadius: 4,
                              background: 'rgba(255,255,255,0.08)',
                              color: '#94a3b8',
                              fontWeight: 600,
                            }}
                          >
                            {agent.provider}
                          </span>
                        </div>

                        {isSelected && (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              color: agent.color || '#6366f1',
                            }}
                          >
                            <Check size={13} strokeWidth={3} /> Active
                          </span>
                        )}
                      </div>

                      <div style={{ fontSize: '0.76rem', color: '#94a3b8', lineHeight: 1.45 }}>
                        {agent.description}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
                        <span style={{ fontSize: '0.68rem', color: '#64748b' }}>Role:</span>
                        <span style={{ fontSize: '0.7rem', color: '#cbd5e1', fontWeight: 500 }}>
                          {agent.role || 'Developer'}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
