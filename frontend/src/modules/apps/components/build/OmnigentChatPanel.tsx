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
  FileText,
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
  Wrench,
  MoreVertical,
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
import { DevTerminal } from '../DevTerminal';

export type StudioViewMode = 'chat' | 'cli' | 'split';

export interface OmnigentChatPanelProps {
  app: AppItem;
  resolvedAppId: string;
  session?: OmnigentSession;
  devStatus?: DevSessionStatus;
  isDevPodRunning: boolean;
  onCodeUpdated?: () => void;
  viewMode?: StudioViewMode;
  onViewModeChange?: (mode: StudioViewMode) => void;
  showHeader?: boolean;
  agentName?: string;
  sessionId?: string;
  sessionTitle?: string;
  workspaceId?: string;
  workspaceName?: string;
}

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
  viewMode: propViewMode,
  onViewModeChange,
  showHeader = true,
  agentName,
  sessionId: propSessionId,
  sessionTitle,
  workspaceId: propWorkspaceId,
  workspaceName: propWorkspaceName,
}: OmnigentChatPanelProps) {
  const toast = useToast();
  const [promptText, setPromptText] = useState('');
  const [selectedAgentName, setSelectedAgentName] = useState(agentName || 'claude-code');
  const [internalViewMode, setInternalViewMode] = useState<StudioViewMode>('chat');
  const viewMode = propViewMode ?? internalViewMode;

  const setViewMode = (m: StudioViewMode) => {
    setInternalViewMode(m);
    onViewModeChange?.(m);
  };

  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);
  const [agentSearchQuery, setAgentSearchQuery] = useState('');

  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [copiedCodeId, setCopiedCodeId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (agentName) {
      setSelectedAgentName(agentName);
    }
  }, [agentName]);

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

  const resolvedSessionId = propSessionId || session?.session_id;
  const resolvedWorkspaceId = propWorkspaceId || session?.workspace_id || devStatus?.workspace_id;
  const resolvedWorkspaceName = propWorkspaceName || session?.workspace_name || devStatus?.workspace_name;

  const {
    data: serverMessages = [],
    refetch: refetchMessages,
  } = useOmnigentMessages(resolvedAppId, resolvedSessionId, isSending);

  const sendPromptMutation = useSendOmnigentPrompt();
  const clearSessionMutation = useClearOmnigentSession();

  const allMessages: ChatMessage[] = useMemo(() => {
    if (!serverMessages || serverMessages.length === 0) {
      return optimisticMessages;
    }
    return serverMessages;
  }, [serverMessages, optimisticMessages]);

  const prevToolCallCountRef = useRef<number>(0);
  useEffect(() => {
    const currentToolCalls = allMessages.filter((m) => m.type === 'tool_call' || !!m.tool).length;
    if (currentToolCalls > prevToolCallCountRef.current) {
      prevToolCallCountRef.current = currentToolCalls;
      onCodeUpdated?.();
    }
  }, [allMessages, onCodeUpdated]);

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
        sessionId: resolvedSessionId,
        agentName: activeAgent.name,
        workspaceId: resolvedWorkspaceId,
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
        workspaceId: resolvedWorkspaceId,
        sessionId: resolvedSessionId,
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

  function getToolBadge(toolName: string) {
    const norm = (toolName || '').toLowerCase();
    if (norm.includes('bash') || norm.includes('command') || norm.includes('exec') || norm.includes('terminal')) {
      return { label: 'Bash', bg: '#eff6ff', color: '#0284c7', border: '#bfdbfe', icon: TerminalIcon };
    }
    if (norm.includes('edit') || norm.includes('patch') || norm.includes('write')) {
      return { label: 'Edit', bg: '#fef3c7', color: '#d97706', border: '#fde68a', icon: FileCode };
    }
    if (norm.includes('read') || norm.includes('view') || norm.includes('cat')) {
      return { label: 'Read', bg: '#f1f5f9', color: '#475569', border: '#e2e8f0', icon: FileText };
    }
    if (norm.includes('search') || norm.includes('grep') || norm.includes('find')) {
      return { label: 'Search', bg: '#f5f3ff', color: '#7c3aed', border: '#ddd6fe', icon: Search };
    }
    if (norm.includes('thought') || norm.includes('think')) {
      return { label: 'Thought', bg: '#fdf2f8', color: '#db2777', border: '#fbcfe8', icon: Sparkles };
    }
    return { label: toolName || 'Tool', bg: '#f1f5f9', color: '#0f172a', border: '#e2e8f0', icon: Wrench };
  }

  type RenderGroupItem =
    | { type: 'user'; message: ChatMessage; id: string }
    | { type: 'assistant'; message: ChatMessage; id: string }
    | { type: 'tool_group'; tools: ChatMessage[]; id: string };

  const groupedItems: RenderGroupItem[] = useMemo(() => {
    const items: RenderGroupItem[] = [];
    let currentToolBatch: ChatMessage[] = [];

    const flushTools = () => {
      if (currentToolBatch.length > 0) {
        items.push({
          type: 'tool_group',
          tools: [...currentToolBatch],
          id: `tool_group_${currentToolBatch[0].id || items.length}`,
        });
        currentToolBatch = [];
      }
    };

    for (let i = 0; i < allMessages.length; i++) {
      const msg = allMessages[i];
      const isTool = msg.type === 'tool_call' || msg.type === 'tool_result' || msg.type === 'thought' || !!msg.tool;

      if (isTool) {
        currentToolBatch.push(msg);
      } else {
        flushTools();
        if (msg.role === 'user') {
          items.push({ type: 'user', message: msg, id: msg.id || `user_${i}` });
        } else {
          items.push({ type: 'assistant', message: msg, id: msg.id || `asst_${i}` });
        }
      }
    }

    flushTools();
    return items;
  }, [allMessages]);

  const quickPromptsForCurrentAgent =
    AGENT_PROMPTS[activeAgent.name] || AGENT_PROMPTS['polly'];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        background: '#ffffff',
        color: '#0f172a',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Top Header Bar: Agent Selector & View Mode Switcher */}
      {showHeader && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 14px',
            background: '#ffffff',
            borderBottom: '1px solid #e2e8f0',
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
            background: '#f8fafc',
            border: `1px solid ${activeAgent.color || '#6366f1'}40`,
            color: '#0f172a',
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
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#0f172a' }}>
              {activeAgent.display_name || activeAgent.name}
            </span>
            <span
              style={{
                fontSize: '0.66rem',
                padding: '1px 6px',
                borderRadius: 4,
                background: '#f1f5f9',
                color: '#64748b',
                fontWeight: 600,
              }}
            >
              {activeAgent.badge || activeAgent.provider || 'AI'}
            </span>
          </div>

          <ChevronDown size={14} color="#64748b" />
        </button>

        {/* Right: Actions & Three Dot Dropdown Menu */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setIsMoreMenuOpen((prev) => !prev)}
              title="More options"
              style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                border: '1px solid #e2e8f0',
                background: isMoreMenuOpen ? '#e0f2fe' : '#ffffff',
                color: isMoreMenuOpen ? '#0284c7' : '#64748b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <MoreVertical size={15} />
            </button>

            {isMoreMenuOpen && (
              <>
                <div
                  style={{ position: 'fixed', inset: 0, zIndex: 45 }}
                  onClick={() => setIsMoreMenuOpen(false)}
                />
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: '100%',
                    marginTop: 4,
                    zIndex: 50,
                    width: 190,
                    background: '#ffffff',
                    borderRadius: 8,
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
                    padding: 5,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                  }}
                >
                  <div style={{ padding: '4px 8px 2px 8px', fontSize: '0.66rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    View Mode
                  </div>

                  <button
                    onClick={() => {
                      setIsMoreMenuOpen(false);
                      setViewMode('cli');
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 5,
                      border: 'none',
                      background: viewMode === 'cli' ? '#f0fdf4' : 'transparent',
                      color: viewMode === 'cli' ? '#166534' : '#1e293b',
                      fontSize: '0.78rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'background 0.12s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <TerminalIcon size={14} color={viewMode === 'cli' ? '#16a34a' : '#64748b'} />
                      <span style={{ fontWeight: viewMode === 'cli' ? 600 : 500 }}>Terminal (CLI)</span>
                    </div>
                    {viewMode === 'cli' && <Check size={14} color="#16a34a" />}
                  </button>

                  <button
                    onClick={() => {
                      setIsMoreMenuOpen(false);
                      setViewMode('chat');
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 5,
                      border: 'none',
                      background: viewMode === 'chat' ? '#eef2ff' : 'transparent',
                      color: viewMode === 'chat' ? '#4338ca' : '#1e293b',
                      fontSize: '0.78rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'background 0.12s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Bot size={14} color={viewMode === 'chat' ? '#6366f1' : '#64748b'} />
                      <span style={{ fontWeight: viewMode === 'chat' ? 600 : 500 }}>Chat UI</span>
                    </div>
                    {viewMode === 'chat' && <Check size={14} color="#6366f1" />}
                  </button>

                  <button
                    onClick={() => {
                      setIsMoreMenuOpen(false);
                      setViewMode('split');
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 5,
                      border: 'none',
                      background: viewMode === 'split' ? '#f5f3ff' : 'transparent',
                      color: viewMode === 'split' ? '#6d28d9' : '#1e293b',
                      fontSize: '0.78rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'background 0.12s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Layers size={14} color={viewMode === 'split' ? '#8b5cf6' : '#64748b'} />
                      <span style={{ fontWeight: viewMode === 'split' ? 600 : 500 }}>Split (Dual)</span>
                    </div>
                    {viewMode === 'split' && <Check size={14} color="#8b5cf6" />}
                  </button>

                  <div style={{ height: 1, background: '#e2e8f0', margin: '4px 0' }} />

                  <button
                    onClick={() => {
                      setIsMoreMenuOpen(false);
                      handleClearHistory();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: 5,
                      border: 'none',
                      background: 'transparent',
                      color: '#dc2626',
                      fontSize: '0.78rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'background 0.12s ease',
                    }}
                  >
                    <Trash2 size={14} color="#dc2626" />
                    <span style={{ fontWeight: 500 }}>Clear Chat History</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      )}

      {/* Main Studio Body (Chat / CLI / Split) */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative',
          background: '#ffffff',
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
              borderBottom: viewMode === 'split' ? '1px solid #e2e8f0' : 'none',
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
            background: '#f8fafc',
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
                      background: `linear-gradient(135deg, ${activeAgent.color || '#6366f1'}20 0%, ${activeAgent.color || '#6366f1'}10 100%)`,
                      border: `1px solid ${activeAgent.color || '#6366f1'}40`,
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
                    <h4 style={{ margin: '0 0 6px', fontSize: '1.02rem', fontWeight: 700, color: '#0f172a' }}>
                      {activeAgent.display_name} Active
                    </h4>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b', lineHeight: 1.5 }}>
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
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          color: '#334155',
                          fontSize: '0.76rem',
                          textAlign: 'left',
                          cursor: 'pointer',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                          transition: 'all 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#f1f5f9';
                          e.currentTarget.style.borderColor = activeAgent.color || '#6366f1';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#ffffff';
                          e.currentTarget.style.borderColor = '#e2e8f0';
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <Wand2 size={13} color={activeAgent.color || '#6366f1'} />
                          <span>{prompt}</span>
                        </div>
                        <CornerDownLeft size={11} color="#94a3b8" />
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                /* Message Stream */
                groupedItems.map((item) => {
                  if (item.type === 'tool_group') {
                    const isGroupExpanded = !!expandedTools[item.id];
                    const tools = item.tools;
                    const count = tools.length;

                    return (
                      <div
                        key={item.id}
                        style={{
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: 8,
                          overflow: 'hidden',
                          fontSize: '0.78rem',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        }}
                      >
                        {/* Group Header Bar */}
                        <div
                          onClick={() => toggleToolExpand(item.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            cursor: 'pointer',
                            background: '#f8fafc',
                            userSelect: 'none',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', minWidth: 0 }}>
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: 5,
                                background: '#e0f2fe',
                                color: '#0284c7',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                              }}
                            >
                              <TerminalIcon size={12} />
                            </div>

                            <span style={{ fontWeight: 600, color: '#0f172a', whiteSpace: 'nowrap' }}>
                              {count === 1 ? 'Tool Call' : `Executed ${count} tools`}
                            </span>

                            {/* Quick Preview Chips (first 3) */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
                              {tools.slice(0, 3).map((t, idx) => {
                                const tName = t.tool?.name || t.type || 'Tool';
                                const tArg = (t.tool?.input ? (typeof t.tool.input === 'string' ? t.tool.input : JSON.stringify(t.tool.input)) : '') || (t.tool as any)?.arg || t.content || '';
                                const badge = getToolBadge(tName);
                                return (
                                  <span
                                    key={idx}
                                    style={{
                                      fontSize: '0.68rem',
                                      padding: '1px 6px',
                                      borderRadius: 4,
                                      background: badge.bg,
                                      color: badge.color,
                                      border: `1px solid ${badge.border}`,
                                      fontFamily: 'monospace',
                                      maxWidth: 160,
                                      whiteSpace: 'nowrap',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                    }}
                                    title={tArg || tName}
                                  >
                                    {badge.label}
                                    {tArg ? `: ${tArg.split('/').pop()?.split(' ')[0] || tArg}` : ''}
                                  </span>
                                );
                              })}
                              {count > 3 && (
                                <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>
                                  +{count - 3} more
                                </span>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#16a34a', fontSize: '0.7rem', fontWeight: 500 }}>
                              <CheckCircle2 size={12} /> Completed
                            </span>
                            {isGroupExpanded ? <ChevronDown size={14} color="#64748b" /> : <ChevronRight size={14} color="#64748b" />}
                          </div>
                        </div>

                        {/* Expanded Tools List */}
                        {isGroupExpanded && (
                          <div style={{ borderTop: '1px solid #e2e8f0', background: '#ffffff', display: 'flex', flexDirection: 'column' }}>
                            {tools.map((t, idx) => {
                              const tName = t.tool?.name || t.type || 'Tool';
                              const tArg = (t.tool?.input ? (typeof t.tool.input === 'string' ? t.tool.input : JSON.stringify(t.tool.input)) : '') || (t.tool as any)?.arg || t.content || '';
                              const badge = getToolBadge(tName);
                              const Icon = badge.icon;
                              const singleKey = `${item.id}_tool_${idx}`;
                              const isSingleExpanded = !!expandedTools[singleKey];

                              return (
                                <div
                                  key={singleKey}
                                  style={{
                                    borderBottom: idx < tools.length - 1 ? '1px solid #f1f5f9' : 'none',
                                    padding: '7px 12px',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 4,
                                  }}
                                >
                                  <div
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      toggleToolExpand(singleKey);
                                    }}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'space-between',
                                      cursor: 'pointer',
                                      gap: 8,
                                    }}
                                  >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                                      <Icon size={13} color={badge.color} />
                                      <span
                                        style={{
                                          fontSize: '0.68rem',
                                          fontWeight: 600,
                                          padding: '1px 6px',
                                          borderRadius: 4,
                                          background: badge.bg,
                                          color: badge.color,
                                          border: `1px solid ${badge.border}`,
                                        }}
                                      >
                                        {badge.label}
                                      </span>
                                      <span
                                        style={{
                                          fontFamily: 'monospace',
                                          fontSize: '0.74rem',
                                          color: '#0f172a',
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          whiteSpace: 'nowrap',
                                        }}
                                        title={tArg}
                                      >
                                        {tArg || tName}
                                      </span>
                                    </div>

                                    <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>
                                      {isSingleExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                    </div>
                                  </div>

                                  {isSingleExpanded && (
                                    <div
                                      style={{
                                        marginTop: 4,
                                        padding: '6px 10px',
                                        background: '#f8fafc',
                                        borderRadius: 6,
                                        border: '1px solid #e2e8f0',
                                        fontFamily: 'monospace',
                                        fontSize: '0.72rem',
                                        color: '#334155',
                                        whiteSpace: 'pre-wrap',
                                        maxHeight: 160,
                                        overflowY: 'auto',
                                      }}
                                    >
                                      {t.tool?.input || t.content}
                                      {t.tool?.output && (
                                        <div style={{ marginTop: 6, paddingTop: 4, borderTop: '1px dashed #cbd5e1', color: '#0f172a' }}>
                                          {typeof t.tool.output === 'object' ? JSON.stringify(t.tool.output, null, 2) : t.tool.output}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  }

                  const isUser = item.type === 'user';
                  const msg = item.message;

                  if (isUser) {
                    return (
                      <div
                        key={item.id}
                        style={{
                          display: 'flex',
                          justifyContent: 'flex-end',
                          width: '100%',
                          margin: '4px 0',
                        }}
                      >
                        <div
                          style={{
                            maxWidth: '82%',
                            background: '#f1f5f9',
                            color: '#0f172a',
                            borderRadius: 14,
                            padding: '8px 14px',
                            fontSize: '0.84rem',
                            lineHeight: 1.5,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {msg?.content}
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={item.id}
                      style={{
                        width: '100%',
                        margin: '4px 0',
                        color: '#0f172a',
                        fontSize: '0.84rem',
                        lineHeight: 1.6,
                        wordBreak: 'break-word',
                      }}
                    >
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ node, inline, className, children, ...props }: any) {
                            const codeText = String(children).replace(/\n$/, '');
                            if (inline) {
                              return (
                                <code
                                  style={{
                                    background: '#f1f5f9',
                                    padding: '2px 6px',
                                    borderRadius: 4,
                                    color: '#0369a1',
                                    fontSize: '0.84em',
                                    fontFamily: 'monospace',
                                    border: '1px solid #e2e8f0',
                                  }}
                                  {...props}
                                >
                                  {children}
                                </code>
                              );
                            }
                            const codeId = `code_${Math.random()}`;
                            return (
                              <div style={{ position: 'relative', margin: '8px 0', borderRadius: 6, overflow: 'hidden', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 10px', background: '#f1f5f9', borderBottom: '1px solid #e2e8f0', fontSize: '0.7rem', color: '#64748b' }}>
                                  <span style={{ fontWeight: 500 }}>Code</span>
                                  <button
                                    onClick={() => handleCopyCode(codeText, codeId)}
                                    style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.7rem' }}
                                  >
                                    {copiedCodeId === codeId ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                                    <span>{copiedCodeId === codeId ? 'Copied' : 'Copy'}</span>
                                  </button>
                                </div>
                                <pre style={{ padding: '10px 12px', margin: 0, overflowX: 'auto', fontSize: '0.76rem', color: '#0f172a', background: '#ffffff', fontFamily: 'monospace' }}>
                                  <code>{children}</code>
                                </pre>
                              </div>
                            );
                          },
                          p({ children }: any) {
                            return <p style={{ margin: '0 0 6px 0', lineHeight: 1.6 }}>{children}</p>;
                          },
                          ul({ children }: any) {
                            return <ul style={{ margin: '4px 0 6px 18px', padding: 0 }}>{children}</ul>;
                          },
                          ol({ children }: any) {
                            return <ol style={{ margin: '4px 0 6px 18px', padding: 0 }}>{children}</ol>;
                          },
                        }}
                      >
                        {msg?.content}
                      </ReactMarkdown>
                    </div>
                  );
                })
              )}

              {/* Thinking Indicator */}
              {isSending && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6366f1', fontSize: '0.8rem', padding: '4px 0', margin: '4px 0' }}>
                  <Loader2 size={14} className="spin" />
                  <span>{activeAgent.display_name} is thinking...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Prompt Composer */}
            <div
              style={{
                padding: '10px 14px',
                background: '#ffffff',
                borderTop: '1px solid #e2e8f0',
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
                  background: '#f8fafc',
                  border: '1px solid #cbd5e1',
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
                    color: '#0f172a',
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
                    background: promptText.trim() && !isSending ? (activeAgent.color || '#6366f1') : '#e2e8f0',
                    border: 'none',
                    color: promptText.trim() && !isSending ? '#ffffff' : '#94a3b8',
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
                  <strong style={{ color: '#334155' }}>Enter</strong> send • <strong style={{ color: '#334155' }}>Shift+Enter</strong> newline
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isDevPodRunning ? (
                    <span style={{ color: '#16a34a', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#16a34a' }} /> Pod connected
                    </span>
                  ) : (
                    <span style={{ color: '#d97706' }}>Pod offline</span>
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
              workspaceId={resolvedWorkspaceId}
              workspaceName={resolvedWorkspaceName}
              isDevPodRunning={isDevPodRunning}
              agent={activeAgent.name}
              sessionId={resolvedSessionId}
              sessionTitle={sessionTitle || session?.title}
              fullHeight={true}
            />
          </div>
        )}
      </div>
      {isAgentModalOpen && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.45)',
            backdropFilter: 'blur(4px)',
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
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 14,
              boxShadow: '0 16px 40px rgba(0, 0, 0, 0.15)',
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
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#ffffff',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Sparkles size={18} color="#6366f1" />
                <span style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>
                  Select Omnigent AI Agent
                </span>
              </div>

              <button
                onClick={() => setIsAgentModalOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
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
            <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: '#ffffff',
                  border: '1px solid #cbd5e1',
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
                    color: '#0f172a',
                    fontSize: '0.82rem',
                  }}
                  autoFocus
                />
              </div>
            </div>

            {/* Agent Grid */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 10, background: '#ffffff' }}>
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
                      background: isSelected ? 'rgba(99, 102, 241, 0.08)' : '#f8fafc',
                      border: isSelected ? `2px solid ${agent.color || '#6366f1'}` : '1px solid #e2e8f0',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 12,
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = '#f1f5f9';
                        e.currentTarget.style.borderColor = '#cbd5e1';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = '#f8fafc';
                        e.currentTarget.style.borderColor = '#e2e8f0';
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
                          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a' }}>
                            {agent.display_name || agent.name}
                          </span>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              padding: '1px 6px',
                              borderRadius: 4,
                              background: '#f1f5f9',
                              color: '#64748b',
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

                      <div style={{ fontSize: '0.76rem', color: '#64748b', lineHeight: 1.45 }}>
                        {agent.description}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
                        <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Role:</span>
                        <span style={{ fontSize: '0.7rem', color: '#475569', fontWeight: 500 }}>
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
