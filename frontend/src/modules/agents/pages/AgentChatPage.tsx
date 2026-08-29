/**
 * AgentChatPage — SSE streaming chat with modular architecture.
 * Refactored into focused, single-responsibility components following SOLID principles.
 */
import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useScopedNavigate } from '@/lib/appNavigation';
import { Bot, Plus, Terminal, PanelLeftOpen, ChevronDown } from 'lucide-react';
import {
  useChatSessions,
  useChatMessages,
  useSessionPlans,
  useCreateSession,
  useDeleteSession,
  type ChatSession,
} from '@/modules/agents/hooks/useChat';
import { useAgent } from '@/modules/agents/hooks/useAgents';
import { useLLMConnections } from '@/modules/agents/hooks/useLLMConnections';
import { useChatStore } from '@/modules/agents/stores/chatStore';
import { useToast } from '@/lib/toast';
import { useQueryClient } from '@tanstack/react-query';
import { getToken } from '@/lib/auth';
import api from '@/lib/api';

import { ChatSessionsSidebar } from '@/modules/agents/components/chat/ChatSessionsSidebar';
import { ChatMessageList } from '@/modules/agents/components/chat/ChatMessageList';
import { ChatComposer } from '@/modules/agents/components/chat/ChatComposer';
import { parseThoughtContent } from '@/modules/agents/components/chat/ThoughtAccordion';
import { AgentWorkspacePanel, WorkspacePanelItem } from '@/modules/agents/components/AgentWorkspacePanel';
import { PlanTaskViewer } from '@/modules/agents/components/PlanTaskViewer';
import { AgentCustomizationsView } from '@/modules/agents/components/AgentCustomizationsView';
import { SessionLlmLogsView } from '@/modules/agents/components/SessionLlmLogsView';
import { ChangeRecord } from '@/modules/agents/components/DiffSummaryCard';
import { useNotebookStore } from '@/modules/notebooks/store/notebookStore';

interface AgentChatPageProps {
  initialView?: 'chat' | 'customizations' | 'logs';
}

export default function AgentChatPage({ initialView }: AgentChatPageProps = {}) {
  const { agentId: agentIdStr, sessionId: sessionIdStr } = useParams<{ agentId: string; sessionId?: string }>();
  const agentId = agentIdStr ? parseInt(agentIdStr, 10) : null;
  const urlSessionId = sessionIdStr ? parseInt(sessionIdStr, 10) : null;

  const navigate = useScopedNavigate();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: agent } = useAgent(agentId);
  const { data: sessions = [] } = useChatSessions(agentId);
  const { data: llmConnections = [] } = useLLMConnections();
  const createSession = useCreateSession();
  const deleteSession = useDeleteSession();

  const [activeSessionId, setActiveSessionId] = useState<number | null>(urlSessionId);

  const effectiveSessionId = urlSessionId ?? activeSessionId ?? (sessions.length > 0 ? sessions[0].id : null);

  const isEditRoute =
    typeof window !== 'undefined' &&
    (window.location.pathname.endsWith('/edit') || window.location.pathname.endsWith('/customizations'));

  const [mainView, setMainView] = useState<'chat' | 'customizations' | 'logs'>(
    initialView ?? (isEditRoute ? 'customizations' : 'chat')
  );

  // Sync activeSessionId with URL param or auto-select first available session
  useEffect(() => {
    if (urlSessionId) {
      if (activeSessionId !== urlSessionId) {
        setActiveSessionId(urlSessionId);
      }
      if (!window.location.pathname.endsWith('/edit') && !window.location.pathname.endsWith('/customizations')) {
        setMainView('chat');
      }
    } else if (sessions.length > 0 && activeSessionId === null) {
      const firstId = sessions[0].id;
      setActiveSessionId(firstId);
      if (agentId) {
        navigate(`/agents/${agentId}/chat/${firstId}`, { replace: true });
      }
    }
  }, [urlSessionId, sessions, activeSessionId, agentId, navigate]);

  useEffect(() => {
    if (initialView) {
      setMainView(initialView);
    } else if (window.location.pathname.endsWith('/edit') || window.location.pathname.endsWith('/customizations')) {
      setMainView('customizations');
    }
  }, [initialView]);

  const { data: messages = [] } = useChatMessages(agentId, effectiveSessionId);
  const { data: storedPlans = [] } = useSessionPlans(agentId, effectiveSessionId);

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
    setStreamingAgent,
    resetStream,
  } = useChatStore();

  const isCurrentSessionStreaming = isStreaming && (streamingSessionId == null || streamingSessionId === activeSessionId);

  const [input, setInput] = useState('');
  const [selectedLlmConnectionId, setSelectedLlmConnectionId] = useState<number | null>(null);
  const [optimisticUserMsg, setOptimisticUserMsg] = useState<{ sessionId: number; content: string } | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  // Sidebar resizable state
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('agent_sidebar_width');
      if (saved) {
        const val = parseInt(saved, 10);
        if (!isNaN(val) && val >= 180 && val <= 500) return val;
      }
    } catch {}
    return 260;
  });
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const handleSidebarWidthChange = useCallback((w: number) => {
    setSidebarWidth(w);
    try {
      localStorage.setItem('agent_sidebar_width', String(w));
    } catch {}
  }, []);

  // File upload state
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [uploadedDocIds, setUploadedDocIds] = useState<number[]>([]);
  const attachedFilesRef = useRef(attachedFiles);
  attachedFilesRef.current = attachedFiles;

  const handleUploadFiles = useCallback(async (incomingFiles: File[]) => {
    if (!incomingFiles.length || !agentId || !activeSessionId) return;
    const currentFiles = attachedFilesRef.current;
    const existingKeys = new Set(currentFiles.map((f) => `${f.name}_${f.size}`));
    const filesToUpload: File[] = [];

    for (const f of incomingFiles) {
      const key = `${f.name}_${f.size}`;
      if (!existingKeys.has(key)) {
        existingKeys.add(key);
        filesToUpload.push(f);
      }
    }
    if (filesToUpload.length === 0) return;

    setAttachedFiles((prev) => [...prev, ...filesToUpload]);

    for (const file of filesToUpload) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await api.post(
          `/api/v1/agents/${agentId}/sessions/${activeSessionId}/documents`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        if (res.data?.id) {
          setUploadedDocIds((prev) => [...prev, res.data.id]);
        }
      } catch (err) {
        console.error('Failed to upload document:', err);
        toast.error(`Failed to upload ${file.name}`);
        setAttachedFiles((prev) => prev.filter((f) => f !== file));
      }
    }
  }, [agentId, activeSessionId, toast]);

  // Right-hand Workspace Panel state
  const [isWorkspacePanelOpen, setIsWorkspacePanelOpen] = useState<boolean>(false);
  const [activeWorkspaceItem, setActiveWorkspaceItem] = useState<WorkspacePanelItem | null>(null);
  const [workspacePanelWidth, setWorkspacePanelWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('agent_workspace_panel_width');
      return saved ? Number(saved) : 620;
    } catch {
      return 620;
    }
  });

  const handleSetWorkspacePanelWidth = useCallback((w: number) => {
    setWorkspacePanelWidth(w);
    try {
      localStorage.setItem('agent_workspace_panel_width', String(w));
    } catch {}
  }, []);

  const openInWorkspacePanel = useCallback((record: ChangeRecord) => {
    const isNb =
      record.object_type === 'notebook' ||
      record.full_name?.endsWith('.ipynb') ||
      record.full_name?.startsWith('workspace.notebooks.');
    setActiveWorkspaceItem({
      type: isNb ? 'notebook' : 'diff',
      title: record.full_name,
      fullName: record.full_name,
      objectType: record.object_type,
      notebookPath: record.full_name,
      changeRecord: record,
    });
    setIsWorkspacePanelOpen(true);
  }, []);

  const [knownAssetNames] = useState<Set<string>>(new Set());
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const latestUserMsgRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const isUserScrolledUpRef = useRef(false);
  const initialScrollDoneRef = useRef<number | null>(null);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false);

  // Per-session composer drafts
  const sessionDraftsRef = useRef<Map<number, { text: string; attachedFiles: File[] }>>(new Map());
  const prevSessionIdRef = useRef<number | null>(activeSessionId);
  const inputRef = useRef(input);
  inputRef.current = input;

  useEffect(() => {
    const prevId = prevSessionIdRef.current;
    if (prevId === activeSessionId) return;

    if (prevId != null) {
      sessionDraftsRef.current.set(prevId, {
        text: inputRef.current,
        attachedFiles: attachedFilesRef.current,
      });
    }

    if (activeSessionId != null) {
      const savedDraft = sessionDraftsRef.current.get(activeSessionId);
      setInput(savedDraft ? savedDraft.text : '');
      setAttachedFiles(savedDraft ? savedDraft.attachedFiles : []);
    } else {
      setInput('');
      setAttachedFiles([]);
    }

    prevSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  // Scroll to bottom logic
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (latestUserMsgRef.current && behavior === 'auto') {
      latestUserMsgRef.current.scrollIntoView({ behavior: 'auto', block: 'start' });
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  const handleMessagesScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const threshold = 120;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    const isScrolledUp = distanceFromBottom > threshold;
    isUserScrolledUpRef.current = isScrolledUp;
    setShowScrollBottomBtn(isScrolledUp);
  }, []);

  useEffect(() => {
    if (effectiveSessionId == null) {
      initialScrollDoneRef.current = null;
      return;
    }
    if (messages.length > 0 && initialScrollDoneRef.current !== effectiveSessionId) {
      initialScrollDoneRef.current = effectiveSessionId;
      isUserScrolledUpRef.current = false;
      setShowScrollBottomBtn(false);
      requestAnimationFrame(() => scrollToBottom('auto'));
    }
  }, [effectiveSessionId, messages.length, scrollToBottom]);

  useEffect(() => {
    if (isCurrentSessionStreaming && !isUserScrolledUpRef.current) {
      scrollToBottom('smooth');
    }
  }, [isCurrentSessionStreaming, streamingText, streamingSteps, activeToolName, scrollToBottom]);

  // Session switching & creation
  const selectSession = useCallback(
    (id: number) => {
      setActiveSessionId(id);
      setMainView('chat');
      if (agentId && urlSessionId !== id) {
        navigate(`/agents/${agentId}/chat/${id}`);
      }
    },
    [agentId, urlSessionId, navigate]
  );

  const handleNewSession = async () => {
    if (!agentId || isCreatingSession) return;
    setIsCreatingSession(true);
    try {
      const created = await createSession.mutateAsync({ agentId, title: 'New Conversation' });
      if (created?.id) {
        setActiveSessionId(created.id);
        setMainView('chat');
        navigate(`/agents/${agentId}/chat/${created.id}`);
        qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions'] });
      }
    } catch (err) {
      console.error('Failed to create session:', err);
      toast.error('Failed to start a new conversation');
    } finally {
      setIsCreatingSession(false);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, session: ChatSession) => {
    e.stopPropagation();
    if (!agentId) return;
    if (!window.confirm(`Delete "${session.title || 'this session'}"?`)) return;
    try {
      await deleteSession.mutateAsync({ agentId, sessionId: session.id });
      sessionDraftsRef.current.delete(session.id);
      if (activeSessionId === session.id) {
        const remaining = sessions.filter((s) => s.id !== session.id);
        if (remaining.length > 0) {
          selectSession(remaining[0].id);
        } else {
          setActiveSessionId(null);
          navigate(`/agents/${agentId}/chat`);
        }
      }
      qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions'] });
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // Send message & streaming logic
  const sendMessage = async (overrideText?: string) => {
    const rawMessage = (overrideText ?? input).trim();
    if (!rawMessage || !agentId || isCurrentSessionStreaming) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      try {
        const created = await createSession.mutateAsync({
          agentId,
          title: rawMessage.slice(0, 40) || 'New Conversation',
        });
        targetSessionId = created.id;
        setActiveSessionId(targetSessionId);
        navigate(`/agents/${agentId}/chat/${targetSessionId}`);
        qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions'] });
      } catch (err) {
        console.error('Failed to create initial session:', err);
        return;
      }
    }

    if (!overrideText) {
      setInput('');
      setAttachedFiles([]);
    }

    isUserScrolledUpRef.current = false;
    setOptimisticUserMsg({ sessionId: targetSessionId, content: rawMessage });
    resetStream();
    setStreaming(true, targetSessionId);

    requestAnimationFrame(() => {
      scrollToLatestUserMessage('smooth');
    });

    const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
    const match = window.location.pathname.match(/^\/w\/([^/]+)/);
    const workspaceSlug = match ? match[1] : null;
    const url = `${baseUrl}/agents/${agentId}/sessions/${targetSessionId}/stream${workspaceSlug ? `?workspace=${workspaceSlug}` : ''}`;

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const token = getToken();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['authkey'] = token;
        headers['Authorization'] = `Bearer ${token}`;
      }
      if (workspaceSlug) headers['X-Workspace-Slug'] = workspaceSlug;

      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          content: rawMessage,
          sandbox: false,
          llm_connection_id: selectedLlmConnectionId ?? undefined,
          document_ids: uploadedDocIds.length > 0 ? uploadedDocIds : undefined,
        }),
        signal: controller.signal,
      });

      setUploadedDocIds([]);

      if (!response.ok) {
        throw new Error(`Chat request failed with status ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let lineBuffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        lineBuffer += decoder.decode(value, { stream: true });
        const lines = lineBuffer.split('\n');
        lineBuffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const rawJson = line.slice(6).trim();
          if (!rawJson) continue;

          try {
            const ev = JSON.parse(rawJson);

            // Swarm: update which agent is currently streaming
            if (ev.agent_name !== undefined) {
              setStreamingAgent(
                ev.agent_name ?? null,
                ev.agent_color ?? null,
                ev.invocation_depth ?? 0
              );
            }

            if (ev.type === 'text' && ev.delta) {
              appendStreamingText(ev.delta);
            }

            if (ev.type === 'tool_start') {
              const currentText = useChatStore.getState().streamingText;
              if (currentText) {
                const { thought } = parseThoughtContent(currentText);
                if (thought) {
                  const items = thought
                    .split(/\n+/)
                    .map((item) => item.trim().replace(/^[-*•]\s*/, ''))
                    .filter((item) => item.length > 0);
                  items.forEach((txt) => addStreamingTimelineItem({ type: 'thought', text: txt }));
                }
                useChatStore.setState({ streamingText: '' });
              }
              setActiveTool(ev.tool_name ?? 'tool', ev.args);
            }

            if (ev.type === 'tool_end') {
              addStreamingTimelineItem({
                type: 'tool',
                name: ev.tool_name ?? 'tool',
                args: ev.args,
                result: ev.result,
                error: ev.error,
                ok: ev.ok,
              });
              setActiveTool(null);

              // ── Handle Notebook Manager Tool Mutations ──
              if (ev.ok && ev.tool_name === 'notebook_manager') {
                const operation = typeof ev.args?.operation === 'string' ? ev.args.operation : undefined;
                const payload = (ev.args?.payload as Record<string, unknown> | undefined) ?? {};
                const data = (ev.result?.data as Record<string, unknown> | undefined) ?? (ev.result as Record<string, unknown> | undefined);

                if (operation === 'edit_cell' || operation === 'propose_cell_edit' || operation === 'apply_notebook_edit') {
                  const code = (payload.code as string | undefined) ?? (data?.code as string | undefined);
                  const cellIndex = Number(payload.cell_index ?? data?.cell_index);
                  const cellType = (payload.cell_type as string | undefined) === 'markdown' ? 'markdown' : 'code';
                  const explanation = (payload.explanation as string | undefined) ?? (data?.explanation as string | undefined);

                  if (code) {
                    const currentCells = useNotebookStore.getState().cells;
                    const targetId = Number.isInteger(cellIndex) && cellIndex >= 0 ? currentCells[cellIndex]?.id : undefined;
                    useNotebookStore.getState().proposeAgentCellEdit({
                      action: 'replace_cell',
                      cellType,
                      proposedSource: code,
                      targetId,
                      explanation,
                    });
                  }
                } else if (operation === 'add_multiple_cells' || operation === 'add_cells') {
                  const cellsList = Array.isArray(payload.cells) ? payload.cells : Array.isArray(data?.cells) ? data.cells : [];
                  const insertAfterIndex = Number(payload.insert_after_cell_index ?? data?.insert_after_cell_index);
                  const currentCells = useNotebookStore.getState().cells;
                  let afterId = Number.isInteger(insertAfterIndex) && insertAfterIndex >= 0 ? currentCells[insertAfterIndex]?.id : undefined;

                  cellsList.forEach((c: any) => {
                    const code = c?.code?.trim();
                    if (!code) return;
                    const cellType = c?.cell_type === 'markdown' || c?.cell_type === 'raw' ? c.cell_type : 'code';
                    const createdId = useNotebookStore.getState().proposeAgentCellEdit({
                      action: 'insert_below',
                      cellType,
                      proposedSource: code,
                      afterId,
                      explanation: c?.explanation || (payload.explanation as string | undefined),
                    });
                    afterId = createdId ?? afterId;
                  });
                } else if (operation === 'run_cell') {
                  const cellIndex = Number(payload.cell_index ?? data?.cell_index);
                  const cell = Number.isInteger(cellIndex) ? useNotebookStore.getState().cells[cellIndex] : undefined;
                  if (cell && cell.type === 'code' && data?.outputs) {
                    useNotebookStore.getState().clearOutput(cell.id);
                    const outputs = Array.isArray(data.outputs) ? data.outputs : [];
                    outputs.forEach((out: any) => {
                      useNotebookStore.getState().appendOutput(cell.id, {
                        type: out.output_type === 'stream' ? 'stream'
                          : out.output_type === 'execute_result' ? 'result'
                          : out.output_type === 'display_data' ? 'display'
                          : 'error',
                        name: out.name === 'stderr' ? 'stderr' : 'stdout',
                        text: Array.isArray(out.text) ? out.text.join('') : (out.text || ''),
                        execution_count: out.execution_count ?? null,
                        data: out.data || {},
                        metadata: out.metadata || {},
                        ename: out.ename || '',
                        evalue: out.evalue || '',
                        traceback: out.traceback || [],
                      } as any);
                    });
                    if (data.execution_count !== undefined) {
                      useNotebookStore.getState().setExecutionCount(cell.id, data.execution_count as number);
                    }
                  }
                } else if (operation === 'approve_cell_edit' && data) {
                  const cellIndex = Number(data.cell_index);
                  const cell = Number.isInteger(cellIndex) ? useNotebookStore.getState().cells[cellIndex] : undefined;
                  if (cell) {
                    useNotebookStore.getState().acceptAgentCellEdit(cell.id);
                  }
                } else if (operation === 'reject_cell_edit' && data) {
                  const cellIndex = Number(data.cell_index);
                  const cell = Number.isInteger(cellIndex) ? useNotebookStore.getState().cells[cellIndex] : undefined;
                  if (cell) {
                    useNotebookStore.getState().rejectAgentCellEdit(cell.id);
                  }
                }
              }

              qc.invalidateQueries({
                queryKey: ['agents', agentId, 'sessions', targetSessionId, 'changes'],
              });
              qc.invalidateQueries({
                queryKey: ['agents', agentId, 'sessions', targetSessionId, 'plans'],
              });
            }

            if (ev.tool_name === 'create_plan' || ev.tool_name === 'mark_step' || ev.tool_name === 'approve_plan') {
              qc.invalidateQueries({
                queryKey: ['agents', agentId, 'sessions', targetSessionId, 'plans'],
              });
            }

            if (ev.type === 'handoff') {
              addStreamingTimelineItem({
                type: 'tool',
                name: 'handoff',
                args: { target_agent: ev.target_agent, reason: ev.reason },
                result: { success: true },
                ok: true,
              });
            }

            if (ev.type === 'error') {
              const errMsg = ev.message ?? 'Agent encountered an error';
              toast.error(errMsg);
              appendStreamingText(`\n\n> ⚠️ **Error**: ${errMsg}`);
              setStreaming(false);
              setActiveTool(null);
              qc.invalidateQueries({
                queryKey: ['agents', agentId, 'sessions', targetSessionId, 'messages'],
              });
            }

            if (ev.type === 'done') {
              qc.invalidateQueries({
                queryKey: ['agents', agentId, 'sessions', targetSessionId, 'messages'],
              }).then(() => setOptimisticUserMsg(null));
              qc.invalidateQueries({
                queryKey: ['agents', agentId, 'sessions'],
              });
            }
          } catch {
            // skip malformed line
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        const errMsg = err.message || 'Stream connection failed';
        toast.error(`Stream error — ${errMsg}`);
        appendStreamingText(`\n\n> ⚠️ **Stream Connection Error**: ${errMsg}`);
      }
    } finally {
      setStreaming(false);
      setActiveTool(null);
      setOptimisticUserMsg(null);
      qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions', targetSessionId, 'messages'] });
      qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions', targetSessionId, 'changes'] });
      qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions', targetSessionId, 'context'] });
      qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions', targetSessionId, 'plans'] });
      qc.invalidateQueries({ queryKey: ['agents', agentId, 'sessions'] });
    }
  };

  // Compute docked plan element if active
  const dockedPlanElement = useMemo(() => {
    // 1. Prefer stored authoritative plan from PlanService if available
    const activeStoredPlan = storedPlans.find((p) => {
      const hasIncomplete = p.steps?.some((s: any) => s.status === 'pending' || s.status === 'in_progress');
      return !p.approved_at || hasIncomplete;
    }) || storedPlans[0];

    if (activeStoredPlan && Array.isArray(activeStoredPlan.steps) && activeStoredPlan.steps.length > 0) {
      const isAllDone = activeStoredPlan.steps.every((s: any) => s.status === 'done');
      if (isAllDone) return null;

      const isPlanApproved = Boolean(activeStoredPlan.approved_at);

      return (
        <PlanTaskViewer
          isDocked={true}
          defaultExpanded={!isPlanApproved}
          plan={{
            plan_id: activeStoredPlan.plan_id,
            agent_id: activeStoredPlan.agent_id || 'agent',
            goal: activeStoredPlan.goal || 'Execution Plan',
            steps: activeStoredPlan.steps.map((s: any, idx: number) => ({
              id: Number(s.id ?? idx + 1),
              description: s.description ?? s.text ?? '',
              status: s.status || 'pending',
              verification: s.verification ?? 'Automatic check',
              corrections: s.corrections ?? [],
              attempts: s.attempts ?? 1,
            })),
            approved_at: activeStoredPlan.approved_at,
            execution_approved_at: activeStoredPlan.execution_approved_at,
          }}
          onApprovePlan={() => sendMessage('Approved. Proceed to execute the plan.')}
          onRejectPlan={() =>
            sendMessage('Plan rejected. Re-evaluate the requirements and propose a different approach.')
          }
          onRequestChange={(feedback) => sendMessage(`Plan changes requested: ${feedback}`)}
        />
      );
    }

    // 2. Fallback: Parse from latest create_plan in message stream
    let latestCreatePlanIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'tool' && messages[i].tool_name === 'create_plan') {
        latestCreatePlanIdx = i;
        break;
      }
    }
    if (latestCreatePlanIdx === -1) return null;

    const createPlanMsg = messages[latestCreatePlanIdx];
    if (!createPlanMsg || !createPlanMsg.tool_result) return null;

    const res = createPlanMsg.tool_result.result as any;
    const args = createPlanMsg.tool_result.args as any;
    const stepsData = args?.steps || res?.steps || [];
    const goalData = args?.goal || res?.goal || 'Execution Plan';
    const planIdData = res?.plan_id || 'plan';

    // Only collect mark_step updates that occurred AFTER this specific create_plan
    const messagesAfterPlan = messages.slice(latestCreatePlanIdx + 1);
    const stepStatusMap: Record<number, string> = {};

    messagesAfterPlan.forEach((m) => {
      if (m.role === 'tool' && m.tool_name === 'mark_step' && m.tool_result) {
        const r = m.tool_result.result as any;
        const stepIdRaw = r?.updated_step ?? (m.tool_result.args as any)?.step_id;
        const status = r?.status ?? (m.tool_result.args as any)?.status;
        const planId = r?.plan_id ?? (m.tool_result.args as any)?.plan_id;
        if ((!planId || planId === planIdData) && stepIdRaw != null && status) {
          stepStatusMap[Number(stepIdRaw)] = String(status);
        }
      }
    });

    const mappedSteps = stepsData.map((s: any, idx: number) => {
      const stepId = Number(s.id ?? idx + 1);
      return {
        id: stepId,
        description: s.description ?? s.text ?? '',
        status: stepStatusMap[stepId] || s.status || 'pending',
        verification: s.verification ?? 'Automatic check',
        corrections: s.corrections ?? [],
        attempts: s.attempts ?? 1,
      };
    });

    const isAllDone = mappedSteps.length > 0 && mappedSteps.every((s: any) => s.status === 'done');
    if (isAllDone) return null;

    const isPlanApproved = Boolean(
      res?.approved_at ||
        messagesAfterPlan.some(
          (m) =>
            m.role === 'tool' && (m.tool_name === 'mark_step' || m.tool_name === 'get_next_step')
        )
    );

    return (
      <PlanTaskViewer
        isDocked={true}
        defaultExpanded={!isPlanApproved}
        plan={{
          plan_id: planIdData,
          agent_id: 'agent',
          goal: goalData,
          steps: mappedSteps,
          approved_at: isPlanApproved ? res?.approved_at || new Date().toISOString() : null,
          execution_approved_at: res?.execution_approved_at,
        }}
        onApprovePlan={() => sendMessage('Approved. Proceed to execute the plan.')}
        onRejectPlan={() =>
          sendMessage('Plan rejected. Re-evaluate the requirements and propose a different approach.')
        }
        onRequestChange={(feedback) => sendMessage(`Plan changes requested: ${feedback}`)}
      />
    );
  }, [storedPlans, messages]);

  const handleInsertTable = useCallback((identifier: string) => {
    setInput((prev) => (prev ? `${prev.trim()} \`${identifier}\` ` : `\`${identifier}\` `));
    toast.success(`Inserted ${identifier} into prompt`);
  }, [toast]);

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden' }}>
      {/* 1. Left Sessions Sidebar */}
      <ChatSessionsSidebar
        agent={agent}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={selectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        mainView={mainView}
        onSetMainView={setMainView}
        isSidebarOpen={!isSidebarCollapsed}
        onToggleSidebar={() => setIsSidebarCollapsed((prev) => !prev)}
        sidebarWidth={sidebarWidth}
        onSidebarWidthChange={handleSidebarWidthChange}
        onInsertTable={handleInsertTable}
      />

      {/* 2. Main Center / Right View */}
      {mainView === 'customizations' && agentId ? (
        <AgentCustomizationsView agentId={agentId} onClose={() => setMainView('chat')} />
      ) : mainView === 'logs' && agentId && activeSessionId ? (
        <SessionLlmLogsView
          agentId={agentId}
          agentName={agent?.name}
          sessionId={activeSessionId}
          onClose={() => setMainView('chat')}
        />
      ) : (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'row',
            overflow: 'hidden',
            height: '100%',
            position: 'relative',
          }}
        >
          {/* Center Chat Column */}
          <div
            style={{
              flex: 1,
              minWidth: 360,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              height: '100%',
            }}
          >
            {/* Top Action Bar */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 8,
                padding: '8px 16px',
                borderBottom: '1px solid #f1f5f9',
                flexShrink: 0,
                minHeight: 42,
              }}
            >

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {activeSessionId && (
                  <button
                    type="button"
                    onClick={() => setMainView('logs')}
                    title="View LLM Call Logs for this session"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '5px 10px',
                      borderRadius: 6,
                      border: '1px solid #e2e8f0',
                      background: '#ffffff',
                      color: '#475569',
                      fontSize: '0.76rem',
                      fontWeight: 500,
                      cursor: 'pointer',
                      boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Terminal size={13} color="#2563eb" />
                    <span>LLM Logs</span>
                  </button>
                )}
              </div>
            </div>

            {!activeSessionId ? (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  color: 'var(--color-text-muted)',
                }}
              >
                <Bot size={40} style={{ opacity: 0.2 }} />
                <div style={{ fontSize: '0.9rem' }}>Select or create a conversation to start.</div>
                <button className="btn btn-primary" onClick={handleNewSession}>
                  <Plus size={14} /> New conversation
                </button>
              </div>
            ) : (
              <>
                {/* Messages List */}
                <ChatMessageList
                  messages={messages}
                  optimisticUserMsg={optimisticUserMsg}
                  activeSessionId={activeSessionId}
                  isStreaming={isCurrentSessionStreaming}
                  streamingSteps={streamingSteps}
                  streamingText={streamingText}
                  activeToolName={activeToolName}
                  activeToolArgs={activeToolArgs}
                  agentId={agentId}
                  knownAssetNames={knownAssetNames}
                  messagesContainerRef={messagesContainerRef}
                  messagesEndRef={messagesEndRef}
                  latestUserMsgRef={latestUserMsgRef}
                  onMessagesScroll={handleMessagesScroll}
                  onOpenDiff={openInWorkspacePanel}
                  onStatusChange={() => {
                    qc.invalidateQueries({
                      queryKey: ['agents', agentId, 'sessions', activeSessionId, 'changes'],
                    });
                    qc.invalidateQueries({
                      queryKey: ['agents', agentId, 'sessions', activeSessionId, 'messages'],
                    });
                  }}
                />

                {/* Floating Scroll to Bottom button */}
                {showScrollBottomBtn && (
                  <div style={{ display: 'flex', justifyContent: 'center', position: 'relative', zIndex: 30 }}>
                    <button
                      type="button"
                      onClick={() => scrollToBottom('smooth')}
                      title="Scroll to bottom"
                      style={{
                        position: 'absolute',
                        top: -36,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '6px 14px',
                        borderRadius: 20,
                        background: '#ffffff',
                        color: '#1e293b',
                        border: '1px solid var(--color-border, #e2e8f0)',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04)',
                        fontSize: '0.76rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      <ChevronDown size={14} color="#2563eb" style={{ strokeWidth: 2.5 }} />
                      <span>Scroll to bottom</span>
                    </button>
                  </div>
                )}

                {/* Bottom Composer */}
                <ChatComposer
                  input={input}
                  onInputChange={setInput}
                  onSend={sendMessage}
                  isStreaming={isCurrentSessionStreaming}
                  attachedFiles={attachedFiles}
                  onUploadFiles={handleUploadFiles}
                  onRemoveFile={(idx) => setAttachedFiles((prev) => prev.filter((_, i) => i !== idx))}
                  agentId={agentId}
                  sessionId={activeSessionId}
                  messagesCount={messages.length}
                  selectedLlmConnectionId={selectedLlmConnectionId}
                  onSelectLlmConnectionId={setSelectedLlmConnectionId}
                  llmConnections={llmConnections}
                  dockedPlanElement={dockedPlanElement}
                  onOpenDiff={openInWorkspacePanel}
                  onStatusChange={() => {
                    qc.invalidateQueries({
                      queryKey: ['agents', agentId, 'sessions', activeSessionId, 'changes'],
                    });
                    qc.invalidateQueries({
                      queryKey: ['agents', agentId, 'sessions', activeSessionId, 'messages'],
                    });
                  }}
                />

                {/* Disclaimer */}
                <div
                  style={{
                    textAlign: 'center',
                    fontSize: '0.68rem',
                    color: 'var(--color-text-subtle, var(--color-text-muted))',
                    padding: '4px 0 8px',
                  }}
                >
                  Always review the accuracy of responses.
                </div>
              </>
            )}
          </div>

          {/* Right-hand Workspace Panel */}
          {isWorkspacePanelOpen && (
            <AgentWorkspacePanel
              activeItem={activeWorkspaceItem}
              width={workspacePanelWidth}
              onWidthChange={handleSetWorkspacePanelWidth}
              onClose={() => setIsWorkspacePanelOpen(false)}
              onCollapse={() => setIsWorkspacePanelOpen(false)}
              agentId={agentId}
              sessionId={activeSessionId}
              onStatusChange={() => {
                qc.invalidateQueries({
                  queryKey: ['agents', agentId, 'sessions', activeSessionId, 'changes'],
                });
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}
