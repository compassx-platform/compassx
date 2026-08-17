import { create } from 'zustand';
import type { StateCreator } from 'zustand';
import type { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';
import type { ISessionConnection } from '@jupyterlab/services/lib/session/session';

export type CellType = 'code' | 'markdown';
export type KernelStatus = 'idle' | 'busy' | 'dead' | 'unknown' | 'connecting';
export type AgentEditAction = 'replace_focused' | 'replace_cell' | 'insert_below' | 'append_to_focused';

export interface AgentCellEditProposal {
  action: AgentEditAction;
  originalSource: string;
  proposedSource: string;
  cellType: CellType;
  explanation?: string;
  createdCell: boolean;
}

export interface StreamOutput {
  type: 'stream';
  name: 'stdout' | 'stderr';
  text: string;
}
export interface ResultOutput {
  type: 'result';
  execution_count: number | null;
  data: Record<string, string>;
  metadata: Record<string, unknown>;
}
export interface DisplayOutput {
  type: 'display';
  data: Record<string, string>;
  metadata: Record<string, unknown>;
}
export interface ErrorOutput {
  type: 'error';
  ename: string;
  evalue: string;
  traceback: string[];
}
export type CellOutput = StreamOutput | ResultOutput | DisplayOutput | ErrorOutput;

export interface Cell {
  id: string;
  type: CellType;
  source: string;
  committedSource?: string;
  pendingSource?: string;
  cellStatus?: 'clean' | 'pending';
  hasConfirmedSideEffects?: boolean;
  pendingAgentEdit?: AgentCellEditProposal;
  outputs: CellOutput[];
  executionCount: number | null;
  isRunning: boolean;
  executedAt?: Date;
  title?: string;
}

export function hasDatabaseSideEffects(code: string): boolean {
  const normalized = code.toLowerCase();
  const sqlKeywords = ['insert\\s+into', 'update\\s+', 'delete\\s+from', 'drop\\s+table', 'alter\\s+table', 'create\\s+table', 'truncate\\s+'];
  const pythonKeywords = ['\\.to_sql\\s*\\(', 'execute\\s*\\(\\s*[\'"`]\\s*(insert|update|delete|drop|alter|create|truncate)', 'engine\\.execute', 'cursor\\.execute'];
  const pattern = new RegExp(
    `(${sqlKeywords.join('|')}|${pythonKeywords.join('|')})`,
    'i'
  );
  return pattern.test(normalized);
}

export interface KernelInfo {
  name: string;
  language: string;
  version: string;
}

export interface SelectedPod {
  resource_id: string;
  runtime_id: string | null;
  runtime: string;
  kernel_id: string | null;
  kernel_name: string | null;
  state: 'starting' | 'connected';
}

export interface LastComputeInfo {
  resource_id: string;
  kernel_name: string | null;
}

interface NotebookStore {
  cells: Cell[];
  kernelRef: IKernelConnection | null;
  sessionRef: ISessionConnection | null;
  kernelStatus: KernelStatus;
  kernelInfo: KernelInfo | null;
  isDirty: boolean;
  notebookPath: string;
  notebookId: string | null;
  focusedCellId: string | null;
  showLineNumbers: boolean;
  collapsedOutputs: Set<string>;
  collapsedCells: Set<string>;
  variables: string[];

  // Cell CRUD
  addCell: (type: CellType, afterId?: string) => void;
  deleteCell: (id: string) => void;
  updateCellSource: (id: string, source: string) => void;
  updateCellTitle: (id: string, title: string) => void;
  setCellType: (id: string, type: CellType) => void;
  reorderCells: (ids: string[]) => void;
  moveCellUp: (id: string) => void;
  moveCellDown: (id: string) => void;
  toggleCollapseCell: (id: string) => void;

  // Output
  appendOutput: (id: string, output: CellOutput) => void;
  clearOutput: (id: string) => void;
  clearAllOutputs: () => void;
  toggleCollapseOutput: (id: string) => void;
  setCellRunning: (id: string, running: boolean) => void;
  setExecutionCount: (id: string, count: number | null) => void;

  // Kernel/session
  setKernel: (kernel: IKernelConnection) => void;
  setSession: (session: ISessionConnection) => void;
  setKernelStatus: (status: KernelStatus) => void;
  setKernelInfo: (info: KernelInfo | null) => void;

  selectedPod: SelectedPod | null;
  setSelectedPod: (pod: SelectedPod | null) => void;

  lastComputeInfo: LastComputeInfo | null;
  notebookComputeLoaded: boolean;
  setLastComputeInfo: (info: LastComputeInfo | null) => void;

  // UI state
  setFocusedCell: (id: string | null) => void;
  setNotebookPath: (path: string) => void;
  setNotebookId: (id: string | null) => void;
  toggleLineNumbers: () => void;
  markClean: () => void;
  setVariables: (vars: string[]) => void;
  setCells: (cells: Cell[]) => void;
  replaceCellSource: (id: string, source: string, type?: CellType) => void;
  appendToCellSource: (id: string, source: string) => void;
  insertGeneratedCell: (type: CellType, source: string, afterId?: string) => string;
  proposeAgentCellEdit: (proposal: {
    action: AgentEditAction;
    cellType: CellType;
    proposedSource: string;
    targetId?: string;
    afterId?: string;
    explanation?: string;
  }) => string | null;
  acceptAgentCellEdit: (id: string) => void;
  rejectAgentCellEdit: (id: string) => void;
  confirmSideEffects: (id: string) => void;
}

function makeId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function makeCell(type: CellType): Cell {
  return { id: makeId(), type, source: '', outputs: [], executionCount: null, isRunning: false, cellStatus: 'clean' };
}

const notebookStoreCreator: StateCreator<NotebookStore> = (set, get) => ({
  cells: [makeCell('code')],
  kernelRef: null,
  sessionRef: null,
  kernelStatus: 'unknown',
  kernelInfo: null,
  isDirty: false,
  notebookPath: 'notebooks/untitled.ipynb',
  notebookId: null,
  selectedPod: null,
  lastComputeInfo: null,
  notebookComputeLoaded: false,
  focusedCellId: null,
  showLineNumbers: true,
  collapsedOutputs: new Set(),
  collapsedCells: new Set(),
  variables: [],

  addCell: (type, afterId) =>
    set((s) => {
      const cell = makeCell(type);
      if (!afterId) return { cells: [...s.cells, cell], isDirty: true, focusedCellId: cell.id };
      const idx = s.cells.findIndex((c) => c.id === afterId);
      const cells = [...s.cells];
      cells.splice(idx + 1, 0, cell);
      return { cells, isDirty: true, focusedCellId: cell.id };
    }),

  deleteCell: (id) =>
    set((s) => {
      if (s.cells.length <= 1) return {};
      const idx = s.cells.findIndex((c) => c.id === id);
      const cells = s.cells.filter((c) => c.id !== id);
      const nextFocus = cells[Math.min(idx, cells.length - 1)]?.id ?? null;
      return { cells, isDirty: true, focusedCellId: nextFocus };
    }),

  updateCellSource: (id, source) =>
    set((s) => ({
      cells: s.cells.map((c) => {
        if (c.id !== id) return c;
        if (c.cellStatus === 'pending') {
          return {
            ...c,
            source,
            pendingSource: source,
            pendingAgentEdit: c.pendingAgentEdit
              ? { ...c.pendingAgentEdit, proposedSource: source }
              : undefined,
          };
        }
        return { ...c, source };
      }),
      isDirty: true,
    })),

  updateCellTitle: (id, title) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, title } : c)),
      isDirty: true,
    })),

  setCellType: (id, type) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, type } : c)),
      isDirty: true,
    })),

  reorderCells: (ids) =>
    set((s) => {
      const map = new Map(s.cells.map((c) => [c.id, c]));
      const cells = ids.map((id) => map.get(id)!).filter(Boolean);
      return { cells, isDirty: true };
    }),

  moveCellUp: (id) =>
    set((s) => {
      const idx = s.cells.findIndex((c) => c.id === id);
      if (idx <= 0) return {};
      const cells = [...s.cells];
      [cells[idx - 1], cells[idx]] = [cells[idx], cells[idx - 1]];
      return { cells, isDirty: true };
    }),

  moveCellDown: (id) =>
    set((s) => {
      const idx = s.cells.findIndex((c) => c.id === id);
      if (idx >= s.cells.length - 1) return {};
      const cells = [...s.cells];
      [cells[idx], cells[idx + 1]] = [cells[idx + 1], cells[idx]];
      return { cells, isDirty: true };
    }),

  toggleCollapseCell: (id) =>
    set((s) => {
      const next = new Set(s.collapsedCells);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { collapsedCells: next };
    }),

  appendOutput: (id, output) =>
    set((s) => ({
      cells: s.cells.map((c) =>
        c.id === id ? { ...c, outputs: [...c.outputs, output] } : c,
      ),
    })),

  clearOutput: (id) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, outputs: [] } : c)),
    })),

  clearAllOutputs: () =>
    set((s) => ({
      cells: s.cells.map((c) => ({ ...c, outputs: [], executionCount: null })),
    })),

  toggleCollapseOutput: (id) =>
    set((s) => {
      const next = new Set(s.collapsedOutputs);
      if (next.has(id)) next.delete(id); else next.add(id);
      return { collapsedOutputs: next };
    }),

  setCellRunning: (id, running) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, isRunning: running } : c)),
    })),

  setExecutionCount: (id, count) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, executionCount: count, executedAt: count !== null ? new Date() : c.executedAt } : c)),
    })),

  setSelectedPod: (pod) => set({ selectedPod: pod }),
  setLastComputeInfo: (info) => set({ lastComputeInfo: info, notebookComputeLoaded: true }),

  setKernel: (kernel) => set({ kernelRef: kernel }),
  setSession: (session) => set({ sessionRef: session }),
  setKernelStatus: (status) => set({ kernelStatus: status }),
  setKernelInfo: (info) => set({ kernelInfo: info }),
  setFocusedCell: (id) => set({ focusedCellId: id }),
  setNotebookPath: (path) => set({ notebookPath: path }),
  setNotebookId: (id) => set({ notebookId: id }),
  toggleLineNumbers: () => set((s) => ({ showLineNumbers: !s.showLineNumbers })),
  markClean: () => set({ isDirty: false }),
  setVariables: (vars) => set({ variables: vars }),
  setCells: (cells) => set({ cells, isDirty: false }),
  replaceCellSource: (id, source, type) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, source, type: type ?? c.type, pendingAgentEdit: undefined } : c)),
      isDirty: true,
      focusedCellId: id,
    })),
  appendToCellSource: (id, source) =>
    set((s) => ({
      cells: s.cells.map((c) =>
        c.id === id
          ? { ...c, source: c.source ? `${c.source.trimEnd()}\n\n${source}` : source }
          : c
      ),
      isDirty: true,
      focusedCellId: id,
    })),
  insertGeneratedCell: (type, source, afterId) => {
    const id = makeId();
    const cell: Cell = {
      id,
      type,
      source,
      outputs: [],
      executionCount: null,
      isRunning: false,
    };
    set((s) => {
      if (!afterId) return { cells: [...s.cells, cell], isDirty: true, focusedCellId: id };
      const idx = s.cells.findIndex((c) => c.id === afterId);
      if (idx === -1) return { cells: [...s.cells, cell], isDirty: true, focusedCellId: id };
      const cells = [...s.cells];
      cells.splice(idx + 1, 0, cell);
      return { cells, isDirty: true, focusedCellId: id };
    });
    return id;
  },
  proposeAgentCellEdit: ({ action, cellType, proposedSource, targetId, afterId, explanation }) => {
    if (action === 'insert_below') {
      const id = makeId();
      const cell: Cell = {
        id,
        type: cellType,
        source: proposedSource,
        committedSource: '',
        pendingSource: proposedSource,
        cellStatus: 'pending',
        pendingAgentEdit: {
          action,
          originalSource: '',
          proposedSource,
          cellType,
          explanation,
          createdCell: true,
        },
        outputs: [],
        executionCount: null,
        isRunning: false,
      };
      set((s) => {
        const idx = afterId ? s.cells.findIndex((c) => c.id === afterId) : -1;
        const cells = [...s.cells];
        if (idx === -1) cells.push(cell); else cells.splice(idx + 1, 0, cell);
        return { cells, focusedCellId: id, isDirty: true };
      });
      return id;
    }

    const state = get();
    let resolvedTargetId = targetId;
    if (!resolvedTargetId && state.cells.length > 0) {
      resolvedTargetId = state.cells[0].id;
    }
    if (!resolvedTargetId) return null;

    set((s) => ({
      cells: s.cells.map((cell) => {
        if (cell.id !== resolvedTargetId) return cell;
        const originalSource = cell.source;
        const normalizedProposedSource = action === 'append_to_focused' && originalSource
          ? `${originalSource.trimEnd()}\n\n${proposedSource}`
          : proposedSource;
        return {
          ...cell,
          type: cellType,
          source: normalizedProposedSource,
          committedSource: originalSource,
          pendingSource: normalizedProposedSource,
          cellStatus: 'pending',
          pendingAgentEdit: {
            action,
            originalSource,
            proposedSource: normalizedProposedSource,
            cellType,
            explanation,
            createdCell: false,
          },
        };
      }),
      focusedCellId: resolvedTargetId,
      isDirty: true,
    }));

    return resolvedTargetId;
  },
  acceptAgentCellEdit: (id) =>
    set((s) => ({
      cells: s.cells.map((cell) => {
        if (cell.id !== id || !cell.pendingAgentEdit) return cell;
        return {
          ...cell,
          type: cell.pendingAgentEdit.cellType,
          source: cell.pendingAgentEdit.proposedSource,
          committedSource: cell.pendingAgentEdit.proposedSource,
          pendingSource: undefined,
          cellStatus: 'clean',
          pendingAgentEdit: undefined,
          hasConfirmedSideEffects: undefined,
        };
      }),
      isDirty: true,
      focusedCellId: id,
    })),
  rejectAgentCellEdit: (id) =>
    set((s) => {
      const target = s.cells.find((cell) => cell.id === id);
      if (target?.pendingAgentEdit?.createdCell && s.cells.length > 1) {
        const idx = s.cells.findIndex((cell) => cell.id === id);
        const cells = s.cells.filter((cell) => cell.id !== id);
        return { cells, focusedCellId: cells[Math.min(idx, cells.length - 1)]?.id ?? null, isDirty: true };
      }
      return {
        cells: s.cells.map((cell) => {
          if (cell.id !== id || !cell.pendingAgentEdit) return cell;
          return {
            ...cell,
            source: cell.pendingAgentEdit.originalSource,
            committedSource: cell.pendingAgentEdit.originalSource,
            pendingSource: undefined,
            cellStatus: 'clean',
            pendingAgentEdit: undefined,
            hasConfirmedSideEffects: undefined,
          };
        }),
        focusedCellId: id,
        isDirty: true,
      };
    }),
  confirmSideEffects: (id) =>
    set((s) => ({
      cells: s.cells.map((c) => (c.id === id ? { ...c, hasConfirmedSideEffects: true } : c)),
    })),
});

export const useNotebookStore = create<NotebookStore>()(notebookStoreCreator);





