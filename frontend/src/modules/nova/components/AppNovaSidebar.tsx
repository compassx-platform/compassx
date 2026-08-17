import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useAgents } from '@/modules/agents/hooks/useAgents';
import { useChatMessages, useChatSessions, useCreateSession, type ChatSession } from '@/modules/agents/hooks/useChat';
import { useLLMConnections } from '@/modules/agents/hooks/useLLMConnections';
import NovaSidePanel, { type NovaEnvelope, type NovaMessage } from '@/modules/nova/components/NovaSidePanel';
import { useNovaStore } from '@/modules/nova/stores/novaStore';
import { useExecuteCell } from '@/modules/notebooks/hooks/useExecuteCell';
import { useNotebookStore, type Cell, type CellOutput } from '@/modules/notebooks/store/notebookStore';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { stripAppScope } from '@/lib/appNavigation';
import { getAuthKey } from '@/lib/auth';
import { useNovaAttachments } from '@/modules/nova/hooks/useNovaAttachments';

function outputToSerializable(output: CellOutput) {
  if (output.type === 'stream') return { type: output.type, name: output.name, text: output.text };
  if (output.type === 'result') return output;
  if (output.type === 'display') return output;
  return output;
}

function buildCellStates(cells: Cell[]) {
  return cells.map((cell, index) => ({
    cell_index: index,
    output: cell.outputs.map(outputToSerializable),
    execution_count: cell.executionCount,
    variable_state: {},
    source: cell.source,
    committed_source: cell.committedSource ?? null,
    pending_source: cell.pendingSource ?? null,
    cell_status: cell.cellStatus ?? 'clean',
  }));
}

function buildExecutionFollowUp(cellIndex: number, cell: Cell | undefined) {
  if (!cell) {
    return `Notebook cell ${cellIndex} could not be executed because it no longer exists.`;
  }
  return [
    `Notebook cell ${cellIndex} has finished executing.`,
    '',
    'Cell source:',
    '```',
    cell.source,
    '```',
    '',
    'Captured output:',
    '```json',
    JSON.stringify(cell.outputs.map(outputToSerializable), null, 2),
    '```',
    '',
    'Use this execution output to continue the task. If the output shows an error or the result is not sufficient, fix the notebook and request another execution only when needed.',
  ].join('\n');
}

function findLastExecutedIndex(cells: Cell[]) {
  let lastIndex: number | null = null;
  let lastTime = -1;
  cells.forEach((cell, index) => {
    if (!cell.executedAt) return;
    const time = new Date(cell.executedAt).getTime();
    if (time > lastTime) {
      lastTime = time;
      lastIndex = index;
    }
  });
  return lastIndex;
}

function normalizeNovaEnvelope(envelope: NovaEnvelope | null): NovaEnvelope | null {
  if (!envelope) return null;
  const action = String(envelope.action ?? '').toLowerCase();
  const normalizedAction: NovaEnvelope['action'] | undefined =
    action === 'replace' ? 'replace_focused'
      : action === 'append' || action === 'append_cell' ? 'append_to_focused'
        : action === 'insert' || action === 'add_cell' || action === 'create_cell' ? 'insert_below'
          : action === 'chat' || action === 'replace_focused' || action === 'replace_cell' || action === 'add_cells' || action === 'insert_below' || action === 'append_to_focused' ? action
            : undefined;

  if (normalizedAction) return { ...envelope, action: normalizedAction };
  if (envelope.code?.trim()) return { ...envelope, action: 'insert_below' };
  return envelope;
}

function isNovaEnvelope(value: unknown): value is NovaEnvelope {
  if (!value || typeof value !== 'object') return false;
  const record = value as Record<string, unknown>;
  return typeof record.action === 'string' || typeof record.code === 'string' || Array.isArray(record.cells);
}

function getContextMeta(pathname: string, notebookPath: string) {
  if (pathname.startsWith('/notebooks/open')) {
    const fileName = notebookPath.split('/').pop() || notebookPath;
    return {
      subtitle: 'Notebook Assistant',
      pill: 'Notebook context',
      placeholder: `Ask an agent about ${fileName}`,
    };
  }

  if (pathname.startsWith('/assets')) {
    return {
      subtitle: 'Asset Manager Assistant',
      pill: 'Asset context',
      placeholder: 'Ask an asset agent about assets...',
    };
  }

  return {
    subtitle: 'App Assistant',
    pill: 'Navigation aware',
    placeholder: 'Select an agent to use this Nova shell.',
  };
}

function getAssetManagerMode(pathname: string) {
  if (pathname === '/assets/types' || pathname.startsWith('/assets/types/')) return 'asset_types';
  if (pathname.endsWith('/edit')) return 'edit_asset';
  if (pathname === '/assets/new') return 'create_asset';
  if (pathname === '/assets/search') return 'search_assets';
  return 'assets';
}

function getAssetRouteSelection(pathname: string) {
  const assetMatch = pathname.match(/^\/assets\/(\d+)(?:\/edit)?$/);
  const assetTypeMatch = pathname.match(/^\/assets\/types\/(\d+)\/edit$/);
  return {
    selected_asset_id: assetMatch ? Number(assetMatch[1]) : null,
    selected_asset_type_id: assetTypeMatch ? Number(assetTypeMatch[1]) : null,
  };
}

export default function AppNovaSidebar() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const scopedPathname = stripAppScope(location.pathname);
  const [searchParams] = useSearchParams();
  const notebookPath = searchParams.get('path') ?? 'notebooks/untitled.ipynb';
  const { data: agents = [] } = useAgents();
  const { data: llmConnections = [] } = useLLMConnections();
  const proposeAgentCellEdit = useNotebookStore((s) => s.proposeAgentCellEdit);
  const { executeCell } = useExecuteCell();

  const requirement = useNovaStore((s) => s.requirement);
  const selectedLlmConnectionId = useNovaStore((s) => s.selectedLlmConnectionId);
  const selectedTarget = useNovaStore((s) => s.selectedTarget);
  const activeAgentSessionIds = useNovaStore((s) => s.activeAgentSessionIds);
  const historyOpen = useNovaStore((s) => s.historyOpen);
  const setRequirement = useNovaStore((s) => s.setRequirement);
  const setSelectedLlmConnectionId = useNovaStore((s) => s.setSelectedLlmConnectionId);
  const setSelectedTarget = useNovaStore((s) => s.setSelectedTarget);
  const setActiveAgentSession = useNovaStore((s) => s.setActiveAgentSession);
  const setHistoryOpen = useNovaStore((s) => s.setHistoryOpen);

  const activeAgents = useMemo(() => agents.filter((agent) => agent.is_active), [agents]);
  const selectedAgentId = selectedTarget?.agentId ?? null;
  const selectedAgent = useMemo(
    () => activeAgents.find((agent) => agent.id === selectedAgentId) ?? null,
    [activeAgents, selectedAgentId],
  );
  const { data: agentSessions = [] } = useChatSessions(selectedAgentId);
  const activeAgentSessionId = selectedAgentId ? (activeAgentSessionIds[selectedAgentId] ?? null) : null;
  const {
    attachments,
    isUploading: isUploadingAttachments,
    uploadFiles,
    removeAttachment,
    promoteAttachment,
  } = useNovaAttachments(activeAgentSessionId);
  const { data: agentMessages = [] } = useChatMessages(selectedAgentId, activeAgentSessionId);
  const createAgentSession = useCreateSession();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [agentStreamingText, setAgentStreamingText] = useState('');
  const [agentOptimisticUserMessage, setAgentOptimisticUserMessage] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState('Ready');
  const [activeToolName, setActiveToolName] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const stopRequestedRef = useRef(false);
  const activeStreamIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!llmConnections.length) {
      setSelectedLlmConnectionId(null);
      return;
    }
    setSelectedLlmConnectionId(
      selectedLlmConnectionId && llmConnections.some((item) => item.id === selectedLlmConnectionId)
        ? selectedLlmConnectionId
        : (llmConnections.find((item) => item.is_fallback)?.id ?? llmConnections[0].id),
    );
  }, [llmConnections, selectedLlmConnectionId, setSelectedLlmConnectionId]);

  useEffect(() => {
    if (!selectedTarget) return;
    if (!selectedAgent) {
      setSelectedTarget(null);
      return;
    }
    const current = activeAgentSessionIds[selectedAgent.id];
    if (current && (agentSessions.length === 0 || agentSessions.some((session) => session.id === current))) return;
    if (agentSessions.length > 0) {
      setActiveAgentSession(selectedAgent.id, agentSessions[0].id);
      return;
    }
    if (!createAgentSession.isPending) {
      createAgentSession.mutate({ agentId: selectedAgent.id }, {
        onSuccess: (session) => setActiveAgentSession(selectedAgent.id, session.id),
      });
    }
  }, [selectedTarget, selectedAgent, activeAgentSessionIds, agentSessions, setSelectedTarget, setActiveAgentSession, createAgentSession]);

  const contextMeta = useMemo(
    () => getContextMeta(scopedPathname, notebookPath),
    [scopedPathname, notebookPath],
  );

  function proposeGeneratedCode(envelope: NovaEnvelope) {
    const code = envelope.code?.trim();
    if (!code) throw new Error('Agent returned no code');
    const currentCells = useNotebookStore.getState().cells;
    const currentFocusedCellId = useNotebookStore.getState().focusedCellId;
    const currentFocusedCellIndex = currentCells.findIndex((cell) => cell.id === currentFocusedCellId);
    const cellType = envelope.cell_type === 'markdown' ? 'markdown' : 'code';
    const requestedCellIndex = Number.isInteger(envelope.cell_index) ? Number(envelope.cell_index) : null;
    const targetIndex = requestedCellIndex ?? envelope.insert_after_cell_index ?? currentFocusedCellIndex;
    const afterId = envelope.action === 'insert_below' && targetIndex != null && targetIndex >= 0 ? currentCells[targetIndex]?.id : undefined;
    const targetId = targetIndex != null && targetIndex >= 0 ? currentCells[targetIndex]?.id : currentFocusedCellId ?? undefined;
    if (envelope.action === 'replace_cell' && !targetId) {
      throw new Error(`Agent requested edit for missing cell ${requestedCellIndex ?? ''}`.trim());
    }

    proposeAgentCellEdit({
      action: envelope.action === 'replace_focused' || envelope.action === 'replace_cell' || envelope.action === 'append_to_focused'
        ? envelope.action
        : 'insert_below',
      cellType,
      proposedSource: code,
      targetId,
      afterId,
      explanation: envelope.explanation,
    });
  }

  function proposeGeneratedCells(envelope: NovaEnvelope) {
    const proposedCells = Array.isArray(envelope.cells) ? envelope.cells : [];
    if (!proposedCells.length) throw new Error('Agent returned no cells');

    const currentCells = useNotebookStore.getState().cells;
    const currentFocusedCellId = useNotebookStore.getState().focusedCellId;
    const currentFocusedCellIndex = currentCells.findIndex((cell) => cell.id === currentFocusedCellId);
    const targetIndex = envelope.insert_after_cell_index ?? currentFocusedCellIndex;
    let afterId = targetIndex != null && targetIndex >= 0 ? currentCells[targetIndex]?.id : undefined;

    proposedCells.forEach((cell, index) => {
      const code = cell.code?.trim();
      if (!code) throw new Error(`Agent returned no code for cell ${index + 1}`);
      const cellType = cell.cell_type === 'markdown' || cell.cell_type === 'raw' ? cell.cell_type : 'code';
      const createdId = proposeAgentCellEdit({
        action: 'insert_below',
        cellType,
        proposedSource: code,
        afterId,
        explanation: cell.explanation || envelope.explanation,
      });
      afterId = createdId ?? afterId;
    });
  }

  function buildAgentContextPayload() {
    const assetSelection = getAssetRouteSelection(scopedPathname);
    const currentCells = useNotebookStore.getState().cells;
    const currentFocusedCellId = useNotebookStore.getState().focusedCellId;
    const currentFocusedCellIndex = currentCells.findIndex((cell) => cell.id === currentFocusedCellId);

    // Dashboard context — injected when the user is on any /dashboards/:id route
    let dashboardContext: Record<string, unknown> | null = null;
    if (scopedPathname.match(/^\/dashboards\/[^/]+/)) {
      const activeDashboard = useDashboardStore.getState().activeDashboard;
      if (activeDashboard) {
        dashboardContext = {
          dashboard_id: activeDashboard.id,
          dashboard_name: activeDashboard.name,
          is_draft: activeDashboard.isDraft,
          // Pages — agent needs page_id to add/target widgets correctly
          pages: activeDashboard.pages.map((p) => ({
            id: p.id,
            name: p.name,
            order: p.order,
            widget_count: activeDashboard.widgets.filter((w) => w.pageId === p.id).length,
          })),
          // Widgets — full summary so agent can rename/update by id without a get_dashboard call
          widgets: activeDashboard.widgets.map((w) => ({
            id: w.id,
            page_id: w.pageId,
            widget_type: w.widgetType,
            title: w.title ?? null,
            chart_type: w.chartConfig?.chartType ?? null,
            dataset_id: w.chartConfig?.datasetId ?? null,
            x_field: w.chartConfig?.xField ?? null,
            y_fields: w.chartConfig?.yFields ?? null,
            color_field: w.chartConfig?.colorField ?? null,
          })),
          // Datasets — agent can reference by id when adding/updating widgets
          datasets: activeDashboard.datasets.map((d) => ({
            id: d.id,
            name: d.name,
            sql: d.sql,
          })),
        };
      }
    }

    const activeNotebookPath = searchParams.get('path')
      || (scopedPathname.startsWith('/notebooks/open') ? notebookPath : null)
      || useNotebookStore.getState().notebookPath;

    const isNotebookActive = scopedPathname.startsWith('/notebooks/open')
      || (scopedPathname.startsWith('/data-catalog') && (scopedPathname.endsWith('.ipynb') || searchParams.has('notebook') || searchParams.has('path') || currentCells.length > 0));

    return {
      surface: 'nova',
      route: scopedPathname,
      notebook: isNotebookActive
        ? {
            notebook_path: activeNotebookPath,
            focused_cell_index: currentFocusedCellIndex >= 0 ? currentFocusedCellIndex : null,
            last_executed_cell_index: findLastExecutedIndex(currentCells),
            attached_kernel: 'python3',
            kernel_id: useNotebookStore.getState().kernelRef?.id || null,
            cell_states: buildCellStates(currentCells),
          }
        : null,
      asset_manager: scopedPathname.startsWith('/assets')
        ? {
            route: scopedPathname,
            mode: getAssetManagerMode(scopedPathname),
            ...assetSelection,
            filters: Object.fromEntries(searchParams.entries()),
            view_state: {},
          }
        : null,
      dashboard: dashboardContext,
    };
  }

  async function submitRequirement() {
    await submitAgentRequirement();
  }

  async function readSseStream(
    response: Response,
    handleEvent: (event: { type: string; delta?: string; message?: string; stream_id?: string; tool_name?: string; args?: Record<string, unknown>; result?: Record<string, unknown>; ok?: boolean }) => Promise<void>,
  ) {
    if (!response.ok || !response.body) throw new Error(`Agent request failed with status ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      if (stopRequestedRef.current) throw new DOMException('Stopped', 'AbortError');
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop() ?? '';
      for (const chunk of chunks) {
        const line = chunk.split('\n').find((entry) => entry.startsWith('data: '));
        if (!line) continue;
        await handleEvent(JSON.parse(line.slice(6)));
      }
    }
    if (buffer.trim().startsWith('data: ')) {
      await handleEvent(JSON.parse(buffer.trim().slice(6)));
    }
  }

  useEffect(() => {
    if (!selectedAgentId || !activeAgentSessionId || isSubmitting) return;
    let cancelled = false;
    const abortController = new AbortController();

    async function attachRunningStream() {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const match = window.location.pathname.match(/^\/w\/([^/]+)/);
      const workspaceSlug = match ? match[1] : null;
      const authkey = getAuthKey();
      const headers: Record<string, string> = {};
      if (authkey) {
        headers.authkey = authkey;
        headers['Authorization'] = `Bearer ${authkey}`;
      }
      if (workspaceSlug) headers['X-Workspace-Slug'] = workspaceSlug;
      const activeResponse = await fetch(
        `${baseUrl}/streams/active?kind=agent&agent_id=${selectedAgentId}&session_id=${activeAgentSessionId}${workspaceSlug ? `&workspace=${workspaceSlug}` : ''}`,
        { headers, signal: abortController.signal },
      );
      if (!activeResponse.ok) return;
      const payload = await activeResponse.json() as { streams?: Array<{ id: string }> };
      const streamId = payload.streams?.[0]?.id;
      if (!streamId || cancelled) return;

      activeStreamIdRef.current = streamId;
      abortControllerRef.current = abortController;
      setIsSubmitting(true);
      setAgentStatus('Reattached to running turn...');
      setAgentStreamingText('');
      setActiveToolName(null);

      const streamResponse = await fetch(`${baseUrl}/streams/${streamId}/events${workspaceSlug ? `?workspace=${workspaceSlug}` : ''}`, { headers, signal: abortController.signal });
      await readSseStream(streamResponse, async (event) => {
        if (event.type === 'stream_attached') {
          activeStreamIdRef.current = event.stream_id ?? streamId;
          return;
        }
        if (event.type === 'text' && event.delta) setAgentStreamingText((text) => text + event.delta);
        if (event.type === 'tool_start') {
          setActiveToolName(event.tool_name ?? 'tool');
          setAgentStatus(`Using ${event.tool_name ?? 'tool'}...`);
        }
        if (event.type === 'tool_end') {
          setActiveToolName(null);
          setAgentStatus('Thinking...');
        }
        if (event.type === 'error') throw new Error(event.message || 'Agent stream error');
        if (event.type === 'done') setAgentStatus('Response ready');
      });
      await queryClient.invalidateQueries({ queryKey: ['agents', selectedAgentId, 'sessions', activeAgentSessionId, 'messages'] });
      await queryClient.invalidateQueries({ queryKey: ['agents', selectedAgentId, 'sessions'] });
    }

    attachRunningStream().catch((error) => {
      if (cancelled || (error instanceof DOMException && error.name === 'AbortError')) return;
      setAgentStatus('Error');
      setAgentStreamingText((text) => `${text}${text ? '\n\n' : ''}⚠️ ${error instanceof Error ? error.message : 'Failed to reattach stream'}`);
    }).finally(() => {
      if (cancelled) return;
      abortControllerRef.current = null;
      activeStreamIdRef.current = null;
      setIsSubmitting(false);
      setActiveToolName(null);
    });

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [selectedAgentId, activeAgentSessionId, isSubmitting, queryClient]);

  async function submitAgentRequirement(contentOverride?: string, autoFollowUpDepth = 0) {
    const content = (contentOverride ?? requirement).trim();
    if (!selectedAgentId || !activeAgentSessionId || !content || !selectedLlmConnectionId || (isSubmitting && !contentOverride)) return;
    if (!contentOverride) {
      stopRequestedRef.current = false;
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    setIsSubmitting(true);
    setAgentStatus(autoFollowUpDepth > 0 ? 'Checking notebook output...' : 'Thinking...');
    setAgentOptimisticUserMessage(contentOverride ? null : content);
    setAgentStreamingText('');
    setActiveToolName(null);
    if (!contentOverride) setRequirement('');

    let failed = false;
    const executionFollowUps: string[] = [];
    try {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const match = window.location.pathname.match(/^\/w\/([^/]+)/);
      const workspaceSlug = match ? match[1] : null;
      const authkey = getAuthKey();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (authkey) {
        headers.authkey = authkey;
        headers['Authorization'] = `Bearer ${authkey}`;
      }
      if (workspaceSlug) headers['X-Workspace-Slug'] = workspaceSlug;
      const response = await fetch(`${baseUrl}/agents/${selectedAgentId}/sessions/${activeAgentSessionId}/stream${workspaceSlug ? `?workspace=${workspaceSlug}` : ''}`, {
        method: 'POST',
        signal: abortController.signal,
        headers,
        body: JSON.stringify({
          content,
          sandbox: false,
          llm_connection_id: selectedLlmConnectionId,
          context: buildAgentContextPayload(),
        }),
      });
      if (!response.ok || !response.body) throw new Error(`Agent request failed with status ${response.status}`);

      let sawEvent = false;
      const handleAgentEvent = async (event: { type: string; delta?: string; message?: string; tool_name?: string; args?: Record<string, unknown>; result?: Record<string, unknown>; ok?: boolean }) => {
        if (event.type === 'stream_started' && 'stream_id' in event) activeStreamIdRef.current = String(event.stream_id);
        if (event.type !== 'stream_started') sawEvent = true;
        if (event.type === 'text' && event.delta) setAgentStreamingText((text) => text + event.delta);
        if (event.type === 'tool_start') {
          setActiveToolName(event.tool_name ?? 'tool');
          setAgentStatus(`Using ${event.tool_name ?? 'tool'}...`);
        }
        if (event.type === 'tool_end') {
          setActiveToolName(null);
          setAgentStatus('Thinking...');
          const operation = typeof event.args?.operation === 'string' ? event.args.operation : undefined;
          const data = event.result?.data as Record<string, unknown> | undefined;
          if (event.ok && event.tool_name === 'notebook_manager') {
            if ((operation === 'apply_notebook_edit' || operation === 'edit_cell' || operation === 'propose_cell_edit' || operation === 'add_multiple_cells') && isNovaEnvelope(data)) {
              const envelope = normalizeNovaEnvelope(data);
              if (envelope?.action === 'add_cells') {
                proposeGeneratedCells(envelope);
                setAgentStatus('Notebook changes pending approval');
              } else if (envelope?.action && envelope.action !== 'chat' && envelope.code?.trim()) {
                proposeGeneratedCode(envelope);
                setAgentStatus('Notebook change pending approval');
              }
              return;
            }
            if (operation === 'run_cell') {
              const cellIndex = Number(data?.cell_index);
              const cell = Number.isInteger(cellIndex) ? useNotebookStore.getState().cells[cellIndex] : undefined;
              if (!cell || cell.type !== 'code') {
                executionFollowUps.push(`Notebook cell ${cellIndex} could not be executed because it is missing or is not a code cell.`);
                return;
              }
              // Backend executes atomically and returns outputs directly.
              // execution_requested is no longer a valid response — treat as error.
              if (data?.status === 'execution_requested') {
                executionFollowUps.push(`Cell ${cellIndex} execution failed: backend did not execute the cell. Please ensure a compute resource is connected.`);
              } else if (data) {
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
                } else {
                  useNotebookStore.getState().setExecutionCount(cell.id, (cell.executionCount || 0) + 1);
                }
                const executedCell = useNotebookStore.getState().cells[cellIndex];
                executionFollowUps.push(buildExecutionFollowUp(cellIndex, executedCell));
              }
            }
            if (operation === 'approve_cell_edit' && data) {
              const cellIndex = Number(data.cell_index);
              const cell = Number.isInteger(cellIndex) ? useNotebookStore.getState().cells[cellIndex] : undefined;
              if (cell) {
                useNotebookStore.getState().acceptAgentCellEdit(cell.id);
              }
            }
            if (operation === 'reject_cell_edit' && data) {
              const cellIndex = Number(data.cell_index);
              const cell = Number.isInteger(cellIndex) ? useNotebookStore.getState().cells[cellIndex] : undefined;
              if (cell) {
                useNotebookStore.getState().rejectAgentCellEdit(cell.id);
              }
            }
          }
          // ── Dashboard Manager — sync UI after agent writes to DB ───────────
          if (event.ok && event.tool_name === 'dashboard_manager') {
            const DASHBOARD_MUTATING_OPS = new Set([
              'create_dashboard', 'update_dashboard',
              'add_dataset', 'update_dataset',
              'add_widget', 'update_widget',
              'publish_dashboard',
            ]);
            if (operation && DASHBOARD_MUTATING_OPS.has(operation)) {
              const payload = event.args?.payload as Record<string, unknown> | undefined;
              const dashboardId =
                (payload?.dashboard_id as string | undefined) ??
                (payload?.dashboardId as string | undefined) ??
                ((data?.id) as string | undefined) ??
                ((data?.dashboardId) as string | undefined);
              if (dashboardId) {
                // Invalidate React Query cache so DashboardEditorPage gets fresh data
                await queryClient.invalidateQueries({ queryKey: ['dashboards', dashboardId] });
                // Dispatch a DOM event so DashboardEditorPage knows to re-sync
                // its Zustand store when the refetched data arrives
                window.dispatchEvent(
                  new CustomEvent('dashboard:agent-mutation', { detail: { dashboardId } }),
                );
              } else {
                // Fallback when we can't determine the id (e.g. list/query ops)
                await queryClient.invalidateQueries({ queryKey: ['dashboards'] });
              }
            }
          }
        }
        if (event.type === 'error') throw new Error(event.message || 'Agent stream error');
        if (event.type === 'done') setAgentStatus('Response ready');
      };

      await readSseStream(response, handleAgentEvent);
      if (!sawEvent) throw new Error('Agent stream ended without events');
      await queryClient.invalidateQueries({ queryKey: ['agents', selectedAgentId, 'sessions', activeAgentSessionId, 'messages'] });
      await queryClient.invalidateQueries({ queryKey: ['agents', selectedAgentId, 'sessions'] });
      if (!stopRequestedRef.current && executionFollowUps.length > 0 && autoFollowUpDepth < 3) {
        await submitAgentRequirement(executionFollowUps.join('\n\n---\n\n'), autoFollowUpDepth + 1);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        setAgentStatus('Stopped');
        await queryClient.invalidateQueries({ queryKey: ['agents', selectedAgentId, 'sessions', activeAgentSessionId, 'messages'] });
        return;
      }
      failed = true;
      setAgentStatus('Error');
      setAgentStreamingText((text) => `${text}${text ? '\n\n' : ''}⚠️ ${error instanceof Error ? error.message : 'Agent request failed'}`);
    } finally {
      abortControllerRef.current = null;
      activeStreamIdRef.current = null;
      if (autoFollowUpDepth === 0 || failed) stopRequestedRef.current = false;
      if (autoFollowUpDepth === 0 || failed) setIsSubmitting(false);
      setActiveToolName(null);
      setAgentOptimisticUserMessage(null);
    }
  }

  async function stopCurrentTurn() {
    stopRequestedRef.current = true;
    const streamId = activeStreamIdRef.current;
    if (streamId) {
      const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
      const match = window.location.pathname.match(/^\/w\/([^/]+)/);
      const workspaceSlug = match ? match[1] : null;
      const authkey = getAuthKey();
      const headers: Record<string, string> = {};
      if (authkey) {
        headers.authkey = authkey;
        headers['Authorization'] = `Bearer ${authkey}`;
      }
      if (workspaceSlug) headers['X-Workspace-Slug'] = workspaceSlug;
      fetch(`${baseUrl}/streams/${streamId}/cancel${workspaceSlug ? `?workspace=${workspaceSlug}` : ''}`, { method: 'POST', headers }).catch(() => undefined);
    }
    abortControllerRef.current?.abort();
    setActiveToolName(null);
    setAgentStatus('Stopping...');
  }

  async function handleNewChat() {
    if (!selectedAgentId || createAgentSession.isPending) return;
    const session = await createAgentSession.mutateAsync({ agentId: selectedAgentId });
    setActiveAgentSession(selectedAgentId, session.id);
    setHistoryOpen(false);
  }

  function handleSelectSession(sessionId: string) {
    if (!selectedAgentId) return;
    setActiveAgentSession(selectedAgentId, Number(sessionId));
    setRequirement('');
    setHistoryOpen(false);
  }

  function toNovaMessagesFromAgent() {
    const mapped: NovaMessage[] = agentMessages
      .filter((message) => message.role !== 'tool')
      .map((message) => ({
        role: message.role === 'user' ? 'user' : 'assistant',
        content: message.content ?? '',
      }));
    if (agentOptimisticUserMessage) mapped.push({ role: 'user', content: agentOptimisticUserMessage });
    const lastAssistantMessage = [...mapped].reverse().find((message) => message.role === 'assistant');
    if (agentStreamingText && lastAssistantMessage?.content !== agentStreamingText) {
      mapped.push({ role: 'assistant', content: agentStreamingText });
    }
    return mapped;
  }

  const panelMessages = selectedAgent ? toNovaMessagesFromAgent() : [];
  const panelSessions = selectedAgent
    ? agentSessions.map((session: ChatSession) => ({
        id: String(session.id),
        title: session.title || `Chat ${session.id}`,
        updatedAt: session.updated_at,
      }))
    : [];
  const panelStatus = selectedAgent ? (activeToolName ? `Using ${activeToolName}...` : agentStatus) : 'Select an agent';
  const panelPlaceholder = selectedAgent ? `Ask ${selectedAgent.name}...` : 'Select an agent to start chatting.';
  const panelWarning = !selectedAgent ? 'Nova is now an agent chat shell. Select an active agent to continue.' : undefined;
  const panelFooter = <div className="nova-panel-surface-pill">{selectedAgent?.name ?? contextMeta.pill}</div>;

  return (
    <NovaSidePanel
      title="Nova"
      subtitle={contextMeta.subtitle}
      sessionTitle={selectedAgent?.name}
      status={panelStatus}
      requirement={requirement}
      onRequirementChange={setRequirement}
      messages={panelMessages}
      historyOpen={historyOpen}
      sessions={panelSessions}
      onNewChat={handleNewChat}
      onToggleHistory={() => setHistoryOpen(!historyOpen)}
      onSelectSession={handleSelectSession}
      activeSessionId={String(activeAgentSessionId ?? '')}
      onSubmit={submitRequirement}
      onStop={stopCurrentTurn}
      isSubmitting={isSubmitting}
      warning={panelWarning}
      target={selectedTarget}
      agents={activeAgents}
      onTargetChange={setSelectedTarget}
      llmConnections={llmConnections}
      selectedLlmConnectionId={selectedLlmConnectionId}
      onSelectedLlmConnectionIdChange={setSelectedLlmConnectionId}
      placeholder={panelPlaceholder}
      footerExtras={panelFooter}
      disableComposer={!selectedAgent || !activeAgentSessionId}
      attachments={attachments}
      onUploadFiles={uploadFiles}
      onRemoveAttachment={removeAttachment}
      onPromoteAttachment={promoteAttachment}
      isUploadingAttachments={isUploadingAttachments}
    />
  );
}
