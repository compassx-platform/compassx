import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Bot,
  Plus,
  X,
  Maximize2,
  ChevronDown,
  Sparkles,
  MessageSquare,
  SquarePen,
  History,
  MoreVertical,
  Trash2,
  SlidersHorizontal,
  FileCode,
  LayoutDashboard,
  Database,
  ExternalLink,
  Check,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { getToken } from '@/lib/auth';
import api from '@/lib/api';

import { useAgents, type AgentListItem } from '@/modules/agents/hooks/useAgents';
import { useLLMConnections } from '@/modules/agents/hooks/useLLMConnections';
import {
  useChatSessions,
  useChatMessages,
  useSessionPlans,
  useCreateSession,
  useDeleteSession,
  type ChatSession,
} from '@/modules/agents/hooks/useChat';
import { useChatStore } from '@/modules/agents/stores/chatStore';
import { useAgentSidePanelStore } from '@/modules/agents/stores/agentSidePanelStore';
import { useCurrentPageContext } from '@/modules/agents/hooks/useCurrentPageContext';

import { ChatMessageList } from '@/modules/agents/components/chat/ChatMessageList';
import { ChatComposer } from '@/modules/agents/components/chat/ChatComposer';
import { PlanTaskViewer } from '@/modules/agents/components/PlanTaskViewer';
import { useNotebookStore } from '@/modules/notebooks/store/notebookStore';

export default function AgentSidePanel() {
  const queryClient = useQueryClient();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const {
    isOpen,
    setOpen,
    selectedAgentId,
    setSelectedAgentId,
    activeSessionPerAgent,
    setActiveSession,
    panelWidth,
    setPanelWidth,
  } = useAgentSidePanelStore();

  const { scopedPathname, buildPageContextPayload } = useCurrentPageContext();

  // Queries
  const { data: agents = [] } = useAgents();
  const { data: llmConnections = [] } = useLLMConnections();
  const activeAgents = useMemo(() => agents.filter((a) => a.is_active), [agents]);

  // Ensure an agent is selected if none chosen
  useEffect(() => {
    if (activeAgents.length > 0 && (selectedAgentId == null || !activeAgents.some((a) => a.id === selectedAgentId))) {
      setSelectedAgentId(activeAgents[0].id);
    }
  }, [activeAgents, selectedAgentId, setSelectedAgentId]);

  const currentAgent = useMemo(
    () => activeAgents.find((a) => a.id === selectedAgentId) || activeAgents[0] || null,
    [activeAgents, selectedAgentId]
  );

  const effectiveAgentId = currentAgent?.id ?? null;

  // Sessions for active agent
  const { data: sessions = [] } = useChatSessions(effectiveAgentId);
  const createSession = useCreateSession();
  const deleteSession = useDeleteSession();

  const activeSessionId = effectiveAgentId ? activeSessionPerAgent[effectiveAgentId] ?? null : null;

  // Auto-select or create session when agent is selected
  useEffect(() => {
    if (!effectiveAgentId) return;
    const currentSession = activeSessionPerAgent[effectiveAgentId];
    if (currentSession && sessions.some((s) => s.id === currentSession)) {
      return;
    }
    if (sessions.length > 0) {
      setActiveSession(effectiveAgentId, sessions[0].id);
      return;
    }
    if (!createSession.isPending) {
      createSession.mutate(
        { agentId: effectiveAgentId },
        {
          onSuccess: (newSession) => {
            setActiveSession(effectiveAgentId, newSession.id);
          },
        }
      );
    }
  }, [effectiveAgentId, sessions, activeSessionPerAgent, setActiveSession, createSession]);

  // Messages & Plans for current active session
  const { data: messages = [] } = useChatMessages(effectiveAgentId, activeSessionId);
  const { data: storedPlans = [] } = useSessionPlans(effectiveAgentId, activeSessionId);

  // Chat Store for streaming
  const {
    streamingText,
    isStreaming,
    streamingSessionId,
    activeToolName,
    activeToolArgs,
    streamingSteps,
    appendStreamingText,
    setStreaming,
    setActiveTool,
    addStreamingTimelineItem,
    resetStream,
  } = useChatStore();

  const isCurrentSessionStreaming = isStreaming && (streamingSessionId == null || streamingSessionId === activeSessionId);

  // Form / Composer state
  const [input, setInput] = useState('');
  const [selectedLlmConnectionId, setSelectedLlmConnectionId] = useState<number | null>(null);
  const [optimisticUserMsg, setOptimisticUserMsg] = useState<{ sessionId: number; content: string } | null>(null);

  // File upload state
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [uploadedDocIds, setUploadedDocIds] = useState<number[]>([]);

  // Dropdown toggles
  const [agentDropdownOpen, setAgentDropdownOpen] = useState(false);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const agentDropdownRef = useRef<HTMLDivElement>(null);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);
  const moreMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (agentDropdownRef.current && !agentDropdownRef.current.contains(e.target as Node)) {
        setAgentDropdownOpen(false);
      }
      if (sessionDropdownRef.current && !sessionDropdownRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
      }
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setMoreMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Resizable left border
  const [isResizing, setIsResizing] = useState(false);
  const handleMouseDownResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizing(true);
      const startX = e.clientX;
      const startW = panelWidth;

      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = startX - moveEvent.clientX;
        const newW = Math.max(300, Math.min(800, startW + delta));
        setPanelWidth(newW);
      };

      const onMouseUp = () => {
        setIsResizing(false);
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    },
    [panelWidth, setPanelWidth]
  );

  // Upload files handler
  const handleUploadFiles = useCallback(
    async (incomingFiles: File[]) => {
      if (!incomingFiles.length || !effectiveAgentId || !activeSessionId) return;
      setAttachedFiles((prev) => [...prev, ...incomingFiles]);

      for (const file of incomingFiles) {
        const formData = new FormData();
        formData.append('files', file);
        try {
          const res = await api.post(
            `/agents/${effectiveAgentId}/sessions/${activeSessionId}/documents`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          );
          const uploaded = res.data?.uploaded;
          if (Array.isArray(uploaded)) {
            const ids = uploaded.filter((u: any) => u.ok && u.doc_id).map((u: any) => u.doc_id);
            if (ids.length > 0) {
              setUploadedDocIds((prev) => [...prev, ...ids]);
            }
          }
        } catch {
          toast.error(`Failed to upload file ${file.name}`);
        }
      }
    },
    [effectiveAgentId, activeSessionId, toast]
  );

  const handleRemoveFile = useCallback((idx: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  // Expand to Full Page
  const handleExpandToFullPage = useCallback(() => {
    if (!effectiveAgentId) return;
    setOpen(false);
    if (activeSessionId) {
      navigate(`/agents/${effectiveAgentId}/chat/${activeSessionId}`);
    } else {
      navigate(`/agents/${effectiveAgentId}/chat`);
    }
  }, [effectiveAgentId, activeSessionId, navigate, setOpen]);

  // Create new session
  const handleNewSession = useCallback(() => {
    if (!effectiveAgentId) return;
    createSession.mutate(
      { agentId: effectiveAgentId },
      {
        onSuccess: (newSession) => {
          setActiveSession(effectiveAgentId, newSession.id);
          setSessionDropdownOpen(false);
          toast.success('Started new conversation');
        },
      }
    );
  }, [effectiveAgentId, createSession, setActiveSession, toast]);

  // Send message turn
  const handleSendMessage = async (textOverride?: string) => {
    const textToSend = textOverride !== undefined ? textOverride : input.trim();
    if (!textToSend || !effectiveAgentId || !activeSessionId || isStreaming) return;

    if (textOverride === undefined) {
      setInput('');
      setAttachedFiles([]);
      setUploadedDocIds([]);
    }

    setOptimisticUserMsg({ sessionId: activeSessionId, content: textToSend });
    resetStream();
    setStreaming(true, activeSessionId);

    requestAnimationFrame(() => {
      scrollToBottom('smooth');
    });

    const pageContext = buildPageContextPayload();
    const token = getToken();

    try {
      const resp = await fetch(`/api/v1/agents/${effectiveAgentId}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: activeSessionId,
          content: textToSend,
          context: pageContext,
          llm_connection_id: selectedLlmConnectionId ?? undefined,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP error ${resp.status}`);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error('No readable stream body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw || raw === '[DONE]') continue;

          try {
            const ev = JSON.parse(raw);
            if (ev.type === 'text' && ev.delta) {
              appendStreamingText(ev.delta);
            } else if (ev.type === 'tool_start') {
              setActiveTool(ev.tool_name, ev.args);
              addStreamingTimelineItem({
                type: 'tool',
                name: ev.tool_name,
                args: ev.args,
                ok: undefined,
              });
            } else if (ev.type === 'tool_end') {
              setActiveTool(null);
              addStreamingTimelineItem({
                type: 'tool',
                name: ev.tool_name,
                args: ev.args,
                result: ev.result,
                error: ev.error,
                ok: ev.ok,
              } as any);

              // Apply live notebook cell operations if returned
              if (ev.tool_name === 'notebook_manager' && ev.ok && ev.result) {
                const resData = ev.result;
                const operation = resData.operation || ev.args?.operation;
                if (operation === 'create_notebook' || operation === 'edit_cell' || operation === 'insert_cell') {
                  queryClient.invalidateQueries({ queryKey: ['notebooks'] });
                }
              }

              queryClient.invalidateQueries({
                queryKey: ['agents', effectiveAgentId, 'sessions', activeSessionId, 'changes'],
              });
              queryClient.invalidateQueries({
                queryKey: ['agents', effectiveAgentId, 'sessions', activeSessionId, 'plans'],
              });
            } else if (ev.type === 'error') {
              const errMsg = ev.message ?? 'Agent error';
              toast.error(errMsg);
              appendStreamingText(`\n\n> ⚠️ **Error**: ${errMsg}`);
              setActiveTool(null);
            } else if (ev.type === 'done') {
              queryClient.invalidateQueries({
                queryKey: ['agents', effectiveAgentId, 'sessions', activeSessionId, 'messages'],
              }).then(() => setOptimisticUserMsg(null));
              queryClient.invalidateQueries({
                queryKey: ['agents', effectiveAgentId, 'sessions'],
              });
            }
          } catch {
            // skip malformed JSON chunk
          }
        }
      }
    } catch (err: any) {
      toast.error(`Stream error: ${err?.message || 'Connection failed'}`);
      appendStreamingText(`\n\n> ⚠️ **Stream Error**: ${err?.message || 'Connection failed'}`);
    } finally {
      setStreaming(false);
      setActiveTool(null);
      queryClient.invalidateQueries({
        queryKey: ['agents', effectiveAgentId, 'sessions', activeSessionId, 'messages'],
      }).then(() => setOptimisticUserMsg(null));
      queryClient.invalidateQueries({
        queryKey: ['agents', effectiveAgentId, 'sessions', activeSessionId, 'plans'],
      });
      queryClient.invalidateQueries({
        queryKey: ['agents', effectiveAgentId, 'sessions'],
      });
    }
  };

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const latestUserMsgRef = useRef<HTMLDivElement>(null);
  const isUserScrolledUpRef = useRef(false);
  const initialScrollDoneRef = useRef<number | null>(null);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior, block: 'end' });
  }, []);

  const handleMessagesScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const threshold = 120;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    isUserScrolledUpRef.current = distanceFromBottom > threshold;
  }, []);

  useEffect(() => {
    if (activeSessionId == null) {
      initialScrollDoneRef.current = null;
      return;
    }
    if (messages.length > 0 && initialScrollDoneRef.current !== activeSessionId) {
      initialScrollDoneRef.current = activeSessionId;
      isUserScrolledUpRef.current = false;
      requestAnimationFrame(() => scrollToBottom('auto'));
    }
  }, [activeSessionId, messages.length, scrollToBottom]);

  useEffect(() => {
    if (isCurrentSessionStreaming && !isUserScrolledUpRef.current) {
      scrollToBottom('smooth');
    }
  }, [isCurrentSessionStreaming, streamingText, streamingSteps, activeToolName, scrollToBottom]);

  // Context pill indicator based on active route
  const contextIndicator = useMemo(() => {
    if (scopedPathname.startsWith('/notebooks/open') || scopedPathname.endsWith('.ipynb')) {
      return { icon: FileCode, label: 'Notebook Context Active', color: '#2563eb', bg: '#eff6ff' };
    }
    if (scopedPathname.startsWith('/dashboards')) {
      return { icon: LayoutDashboard, label: 'Dashboard Context Active', color: '#7c3aed', bg: '#f5f3ff' };
    }
    if (scopedPathname.startsWith('/catalog') || scopedPathname.startsWith('/data-catalog')) {
      return { icon: Database, label: 'Catalog Context Active', color: '#059669', bg: '#ecfdf5' };
    }
    return null;
  }, [scopedPathname]);

  const activeSessionTitle = useMemo(() => {
    const s = sessions.find((item) => item.id === activeSessionId);
    return s?.title || (activeSessionId ? `Session #${activeSessionId}` : 'New Session');
  }, [sessions, activeSessionId]);

  return (
    <div
      style={{
        width: panelWidth,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#ffffff',
        borderLeft: '1px solid #e2e8f0',
        position: 'relative',
        boxShadow: '-4px 0 16px rgba(0, 0, 0, 0.04)',
        zIndex: 50,
      }}
    >
      {/* 1. Left Resize Handle */}
      <div
        onMouseDown={handleMouseDownResize}
        title="Drag to resize panel"
        style={{
          position: 'absolute',
          left: -3,
          top: 0,
          bottom: 0,
          width: 6,
          cursor: 'ew-resize',
          zIndex: 60,
          background: isResizing ? 'var(--color-primary)' : 'transparent',
          transition: 'background 0.15s ease',
        }}
      />

      {/* 2. Top Header Bar with Agent Switcher & Session Controls */}
      <div
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid #f1f5f9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          background: '#ffffff',
          flexShrink: 0,
          minHeight: 48,
        }}
      >
        {/* Left: Agent Switcher Dropdown (Databricks clean typography style) */}
        <div ref={agentDropdownRef} style={{ position: 'relative', minWidth: 0 }}>
          <button
            type="button"
            onClick={() => setAgentDropdownOpen((prev) => !prev)}
            title="Switch Agent"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 6px',
              borderRadius: 6,
              border: 'none',
              background: agentDropdownOpen ? '#f1f5f9' : 'transparent',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'background 0.12s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
            }}
            onMouseLeave={(e) => {
              if (!agentDropdownOpen) e.currentTarget.style.background = 'transparent';
            }}
          >
            <span
              style={{
                fontSize: '0.88rem',
                fontWeight: 600,
                color: '#0f172a',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: 220,
              }}
            >
              {currentAgent?.name || 'Select Agent'}
            </span>
            <ChevronDown size={13} color="#64748b" style={{ flexShrink: 0 }} />
          </button>

          {/* Agent Switcher Menu Popover */}
          {agentDropdownOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 4px)',
                left: 0,
                width: 240,
                maxHeight: 280,
                overflowY: 'auto',
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
                zIndex: 100,
                padding: '4px',
              }}
            >
              <div style={{ padding: '6px 8px 4px', fontSize: '0.68rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Agents
              </div>
              {activeAgents.map((ag) => {
                const isSelected = ag.id === effectiveAgentId;
                return (
                  <button
                    key={ag.id}
                    type="button"
                    onClick={() => {
                      setSelectedAgentId(ag.id);
                      setAgentDropdownOpen(false);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                      width: '100%',
                      padding: '7px 8px',
                      borderRadius: 6,
                      border: 'none',
                      background: isSelected ? '#f1f5f9' : 'transparent',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'background 0.12s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.background = '#f8fafc';
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: isSelected ? 600 : 500, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {ag.name}
                      </div>
                      {ag.model && (
                        <div style={{ fontSize: '0.69rem', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ag.model}
                        </div>
                      )}
                    </div>
                    {isSelected && <Check size={14} color="#0f172a" style={{ flexShrink: 0 }} />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Action Icons: New Chat, History, More (with Full Screen), Close */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* 1. New Chat Button */}
          <button
            type="button"
            onClick={handleNewSession}
            title="New conversation"
            style={{
              width: 28,
              height: 28,
              padding: 0,
              borderRadius: 4,
              border: '1.5px solid transparent',
              background: 'transparent',
              color: '#5f6368',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
              e.currentTarget.style.color = '#0f172a';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = '#5f6368';
            }}
          >
            <SquarePen size={16} />
          </button>

          {/* 2. History / Sessions Dropdown */}
          <div ref={sessionDropdownRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setSessionDropdownOpen((prev) => !prev)}
              title={`Chat History (${sessions.length})`}
              style={{
                width: 28,
                height: 28,
                padding: 0,
                borderRadius: 4,
                border: sessionDropdownOpen ? '1.5px solid #2563eb' : '1.5px solid transparent',
                background: sessionDropdownOpen ? '#eff6ff' : 'transparent',
                color: sessionDropdownOpen ? '#2563eb' : '#5f6368',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!sessionDropdownOpen) {
                  e.currentTarget.style.background = '#f1f5f9';
                  e.currentTarget.style.color = '#0f172a';
                }
              }}
              onMouseLeave={(e) => {
                if (!sessionDropdownOpen) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#5f6368';
                }
              }}
            >
              <History size={16} />
            </button>

            {sessionDropdownOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  right: 0,
                  width: 260,
                  maxHeight: 320,
                  overflowY: 'auto',
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 10,
                  boxShadow: '0 10px 24px rgba(0,0,0,0.12)',
                  zIndex: 100,
                  padding: 4,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', borderBottom: '1px solid #f1f5f9' }}>
                  <span style={{ fontSize: '0.74rem', fontWeight: 600, color: '#0f172a' }}>Chat History</span>
                  <button
                    type="button"
                    onClick={handleNewSession}
                    title="Start new conversation"
                    style={{
                      width: 22,
                      height: 22,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#2563eb',
                      background: 'none',
                      border: 'none',
                      borderRadius: 4,
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#eff6ff')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    <Plus size={14} />
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '4px 0' }}>
                  {sessions.length === 0 ? (
                    <div style={{ padding: '12px 8px', fontSize: '0.74rem', color: '#94a3b8', textAlign: 'center' }}>
                      No previous sessions
                    </div>
                  ) : (
                    sessions.map((s) => {
                      const isActive = s.id === activeSessionId;
                      return (
                        <div
                          key={s.id}
                          onClick={() => {
                            if (effectiveAgentId) {
                              setActiveSession(effectiveAgentId, s.id);
                              setSessionDropdownOpen(false);
                            }
                          }}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 8px',
                            borderRadius: 6,
                            background: isActive ? '#f1f5f9' : 'transparent',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) e.currentTarget.style.background = '#f8fafc';
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          <span
                            style={{
                              fontSize: '0.76rem',
                              fontWeight: isActive ? 600 : 500,
                              color: isActive ? '#0f172a' : '#475569',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              flex: 1,
                            }}
                          >
                            {s.title || `Session #${s.id}`}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (effectiveAgentId) {
                                deleteSession.mutate({ agentId: effectiveAgentId, sessionId: s.id });
                              }
                            }}
                            title="Delete session"
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              color: '#94a3b8',
                              padding: '2px 4px',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.color = '#dc2626')}
                            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 3. Full Screen Workspace Button */}
          <button
            type="button"
            onClick={handleExpandToFullPage}
            title="Full screen workspace"
            style={{
              width: 28,
              height: 28,
              padding: 0,
              borderRadius: 4,
              border: '1.5px solid transparent',
              background: 'transparent',
              color: '#5f6368',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
              e.currentTarget.style.color = '#0f172a';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = '#5f6368';
            }}
          >
            <Maximize2 size={15} />
          </button>

          {/* 4. Settings & Options Dropdown (Three dots) */}
          <div ref={moreMenuRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setMoreMenuOpen((prev) => !prev)}
              title="Settings & Options"
              style={{
                width: 28,
                height: 28,
                padding: 0,
                borderRadius: 4,
                border: moreMenuOpen ? '1.5px solid #2563eb' : '1.5px solid transparent',
                background: moreMenuOpen ? '#eff6ff' : 'transparent',
                color: moreMenuOpen ? '#2563eb' : '#5f6368',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!moreMenuOpen) {
                  e.currentTarget.style.background = '#f1f5f9';
                  e.currentTarget.style.color = '#0f172a';
                }
              }}
              onMouseLeave={(e) => {
                if (!moreMenuOpen) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#5f6368';
                }
              }}
            >
              <MoreVertical size={16} />
            </button>

            {moreMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  right: 0,
                  width: 190,
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  boxShadow: '0 8px 20px rgba(0,0,0,0.1)',
                  zIndex: 100,
                  padding: '4px',
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    setMoreMenuOpen(false);
                    if (effectiveAgentId) {
                      navigate(`/platform/agents/${effectiveAgentId}`);
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '6px 8px',
                    border: 'none',
                    background: 'none',
                    fontSize: '0.78rem',
                    color: '#1e293b',
                    cursor: 'pointer',
                    borderRadius: 4,
                    textAlign: 'left',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                >
                  <SlidersHorizontal size={13} color="#475569" />
                  <span>Agent Settings</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMoreMenuOpen(false);
                    if (effectiveAgentId) {
                      navigate(`/platform/agents/${effectiveAgentId}`);
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '6px 8px',
                    border: 'none',
                    background: 'none',
                    fontSize: '0.78rem',
                    color: '#1e293b',
                    cursor: 'pointer',
                    borderRadius: 4,
                    textAlign: 'left',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                >
                  <FileCode size={13} color="#475569" />
                  <span>Session Logs</span>
                </button>
              </div>
            )}
          </div>

          {/* 5. Close Button */}
          <button
            type="button"
            onClick={() => setOpen(false)}
            title="Close"
            style={{
              width: 28,
              height: 28,
              padding: 0,
              borderRadius: 4,
              border: '1.5px solid transparent',
              background: 'transparent',
              color: '#5f6368',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
              e.currentTarget.style.color = '#0f172a';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = '#5f6368';
            }}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* 3. In-Context Banner Indicator */}
      {contextIndicator && (
        <div
          style={{
            padding: '5px 14px',
            background: contextIndicator.bg,
            borderBottom: '1px solid rgba(0,0,0,0.05)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: '0.72rem',
            color: contextIndicator.color,
            fontWeight: 600,
          }}
        >
          <contextIndicator.icon size={12} />
          <span>{contextIndicator.label}</span>
        </div>
      )}

      {/* 4. Chat Messages List Area */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <ChatMessageList
          messages={messages}
          optimisticUserMsg={optimisticUserMsg}
          activeSessionId={activeSessionId}
          isStreaming={isCurrentSessionStreaming}
          streamingSteps={streamingSteps}
          streamingText={streamingText}
          activeToolName={activeToolName}
          activeToolArgs={activeToolArgs}
          agentId={effectiveAgentId}
          messagesContainerRef={messagesContainerRef}
          messagesEndRef={messagesEndRef}
          latestUserMsgRef={latestUserMsgRef}
          onMessagesScroll={handleMessagesScroll}
          onOpenDiff={() => {}}
        />
      </div>

      {/* 5. Bottom Composer Area */}
      <div style={{ flexShrink: 0, borderTop: '1px solid #f1f5f9', background: '#ffffff', padding: '8px 12px 10px' }}>
        <ChatComposer
          input={input}
          onInputChange={setInput}
          onSend={() => handleSendMessage()}
          isStreaming={isCurrentSessionStreaming}
          attachedFiles={attachedFiles}
          onUploadFiles={handleUploadFiles}
          onRemoveFile={handleRemoveFile}
          agentId={effectiveAgentId}
          sessionId={activeSessionId}
          messagesCount={messages.length}
          selectedLlmConnectionId={selectedLlmConnectionId}
          onSelectLlmConnectionId={setSelectedLlmConnectionId}
          llmConnections={llmConnections}
        />
      </div>
    </div>
  );
}
