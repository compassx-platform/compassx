import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  Maximize2,
  Minimize2,
  ChevronRight,
  BookOpen,
  FileCode,
  FileText,
  BarChart2,
  Check,
  Loader2,
} from 'lucide-react';
import { ChangeRecord } from './DiffSummaryCard';
import { AssetChip, AssetObjectType } from './AssetChip';
import NotebookPage from '@/modules/notebooks/pages/NotebookPage';
import { useNotebookStore } from '@/modules/notebooks/store/notebookStore';
import api from '@/lib/api';

export interface WorkspacePanelItem {
  id?: string;
  type: 'notebook' | 'diff' | 'document' | 'visualization';
  title?: string;
  fullName?: string;
  objectType?: AssetObjectType | string;
  notebookPath?: string;
  changeRecord?: ChangeRecord | null;
  documentContent?: string;
  visualizationData?: any;
}

interface AgentWorkspacePanelProps {
  activeItem?: WorkspacePanelItem | null;
  width?: number;
  onWidthChange?: (width: number) => void;
  onClose?: () => void;
  onCollapse?: () => void;
  agentId?: number | null;
  sessionId?: number | null;
  onStatusChange?: (changeId: string, newStatus: 'accepted' | 'rejected') => void;
}

// ── LCS Diff helpers for code/text files ──
interface DiffLine {
  type: 'add' | 'del' | 'ctx';
  text: string;
  oldLineNumber?: number;
  newLineNumber?: number;
}

function computeLCSDiff(beforeText: string | null, afterText: string | null): DiffLine[] {
  const beforeLines = (beforeText ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const afterLines = (afterText ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');

  if (beforeText === null || beforeText === undefined || beforeText === '') {
    return afterLines.map((line, idx) => ({
      type: 'add',
      text: line,
      newLineNumber: idx + 1,
    }));
  }
  if (afterText === null || afterText === undefined || afterText === '') {
    return beforeLines.map((line, idx) => ({
      type: 'del',
      text: line,
      oldLineNumber: idx + 1,
    }));
  }

  const n = beforeLines.length;
  const m = afterLines.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (beforeLines[i - 1] === afterLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const result: DiffLine[] = [];
  let i = n;
  let j = m;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && beforeLines[i - 1] === afterLines[j - 1]) {
      result.unshift({ type: 'ctx', text: beforeLines[i - 1], oldLineNumber: i, newLineNumber: j });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'add', text: afterLines[j - 1], newLineNumber: j });
      j--;
    } else {
      result.unshift({ type: 'del', text: beforeLines[i - 1], oldLineNumber: i });
      i--;
    }
  }
  return result;
}

const CodeDiffView: React.FC<{ before: string | null; after: string | null; fullName?: string }> = ({
  before,
  after,
}) => {
  const lines = computeLCSDiff(before, after);
  return (
    <div
      style={{
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: '0.78rem',
        lineHeight: 1.6,
        background: '#0d1117',
        color: '#e6edf3',
        height: '100%',
        overflow: 'auto',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          {lines.map((line, idx) => {
            const isAdd = line.type === 'add';
            const isDel = line.type === 'del';
            const bg = isAdd ? 'rgba(46,160,67,0.15)' : isDel ? 'rgba(248,81,73,0.15)' : 'transparent';
            const lineNumColor = isAdd ? '#3fb950' : isDel ? '#f85149' : '#484f58';
            const sign = isAdd ? '+' : isDel ? '-' : ' ';
            return (
              <tr key={idx} style={{ background }}>
                <td
                  style={{
                    width: 44,
                    padding: '0 8px',
                    textAlign: 'right',
                    color: lineNumColor,
                    userSelect: 'none',
                    borderRight: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  {line.oldLineNumber ?? ''}
                </td>
                <td
                  style={{
                    width: 44,
                    padding: '0 8px',
                    textAlign: 'right',
                    color: lineNumColor,
                    userSelect: 'none',
                    borderRight: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  {line.newLineNumber ?? ''}
                </td>
                <td
                  style={{
                    width: 20,
                    padding: '0 4px',
                    textAlign: 'center',
                    color: isAdd ? '#3fb950' : isDel ? '#f85149' : 'transparent',
                    userSelect: 'none',
                    fontWeight: 600,
                  }}
                >
                  {sign}
                </td>
                <td style={{ padding: '0 12px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {line.text}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export const AgentWorkspacePanel: React.FC<AgentWorkspacePanelProps> = ({
  activeItem,
  width: controlledWidth = 620,
  onWidthChange,
  onClose,
  onCollapse,
  agentId,
  sessionId,
  onStatusChange,
}) => {
  const [width, setWidth] = useState<number>(controlledWidth);
  const [isMaximized, setIsMaximized] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<string>(activeItem?.changeRecord?.status || 'clean');
  const [actioning, setActioning] = useState(false);
  const prevWidthRef = useRef<number>(controlledWidth);

  useEffect(() => {
    if (controlledWidth && !isDragging) {
      setWidth(controlledWidth);
    }
  }, [controlledWidth, isDragging]);

  useEffect(() => {
    if (activeItem?.changeRecord?.status) {
      setStatus(activeItem.changeRecord.status);
    }
  }, [activeItem]);

  // ── Drag to resize ──
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    const startX = e.clientX;
    const startWidth = width;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const delta = startX - moveEvent.clientX; // dragging left increases right panel width
      const nextWidth = Math.max(340, Math.min(window.innerWidth - 380, startWidth + delta));
      setWidth(nextWidth);
      onWidthChange?.(nextWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [width, onWidthChange]);

  // ── Maximize toggle ──
  const toggleMaximize = useCallback(() => {
    if (!isMaximized) {
      prevWidthRef.current = width;
      const maxWidth = Math.max(800, window.innerWidth - 380);
      setWidth(maxWidth);
      setIsMaximized(true);
    } else {
      setWidth(prevWidthRef.current);
      setIsMaximized(false);
    }
  }, [isMaximized, width]);

  // ── Approve / Reject actions ──
  const handleAction = async (action: 'accept' | 'reject') => {
    if (action === 'accept') {
      useNotebookStore.getState().acceptAllAgentEdits();
    } else {
      useNotebookStore.getState().rejectAllAgentEdits();
    }
    const changeId = activeItem?.changeRecord?.change_id;
    if (!changeId || !agentId || !sessionId) return;
    setActioning(true);
    try {
      const res = await api.post(
        `/agents/${agentId}/sessions/${sessionId}/changes/${changeId}/${action}`
      );
      if (res.status === 200) {
        const nextStatus = action === 'accept' ? 'accepted' : 'rejected';
        setStatus(nextStatus);
        onStatusChange?.(changeId, nextStatus);
      }
    } catch (err) {
      console.error(`Failed to ${action} change:`, err);
    } finally {
      setActioning(false);
    }
  };

  const isNotebook =
    activeItem?.type === 'notebook' ||
    activeItem?.objectType === 'notebook' ||
    activeItem?.fullName?.endsWith('.ipynb') ||
    activeItem?.notebookPath?.endsWith('.ipynb') ||
    activeItem?.fullName?.startsWith('workspace.notebooks.');

  const isPending = status === 'pending_review';
  const rec = activeItem?.changeRecord;

  return (
    <div
      data-testid="agent-workspace-panel"
      className="agent-workspace-panel"
      style={{
        width: isMaximized ? '100%' : `${width}px`,
        maxWidth: isMaximized ? '100%' : 'calc(100vw - 380px)',
        minWidth: 340,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: isMaximized ? 'absolute' : 'relative',
        top: 0,
        right: 0,
        bottom: 0,
        zIndex: isMaximized ? 300 : 20,
        background: '#ffffff',
        borderLeft: '1px solid var(--color-border, #e2e8f0)',
        boxShadow: isMaximized ? '0 10px 30px rgba(0,0,0,0.15)' : '-2px 0 8px rgba(0,0,0,0.02)',
        userSelect: isDragging ? 'none' : 'auto',
        transition: isDragging ? 'none' : 'width 0.15s ease',
      }}
    >
      {/* ── Left Resize Drag Handle ── */}
      {!isMaximized && (
        <div
          onMouseDown={handleMouseDown}
          style={{
            position: 'absolute',
            top: 0,
            left: -3,
            width: 6,
            height: '100%',
            cursor: 'col-resize',
            zIndex: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Drag to resize workspace panel"
          onMouseEnter={(e) => {
            const line = e.currentTarget.querySelector('.panel-resizer-line') as HTMLElement;
            if (line && !isDragging) line.style.background = '#2563eb';
          }}
          onMouseLeave={(e) => {
            const line = e.currentTarget.querySelector('.panel-resizer-line') as HTMLElement;
            if (line && !isDragging) line.style.background = 'transparent';
          }}
        >
          <div
            className="panel-resizer-line"
            style={{
              width: 2,
              height: '100%',
              background: isDragging ? '#2563eb' : 'transparent',
              transition: 'background 0.15s ease',
            }}
          />
        </div>
      )}

      {/* ── Panel Header ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
          gap: 10,
          flexShrink: 0,
          minHeight: 46,
        }}
      >
        {/* Left info: Icon, Name/AssetChip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
          {isNotebook ? (
            <BookOpen size={16} color="#0284c7" style={{ flexShrink: 0 }} />
          ) : activeItem?.type === 'visualization' || activeItem?.objectType === 'dashboard' ? (
            <BarChart2 size={16} color="#8b5cf6" style={{ flexShrink: 0 }} />
          ) : activeItem?.type === 'document' ? (
            <FileText size={16} color="#10b981" style={{ flexShrink: 0 }} />
          ) : (
            <FileCode size={16} color="#6366f1" style={{ flexShrink: 0 }} />
          )}

          {activeItem?.fullName ? (
            <span
              style={{
                fontSize: '0.82rem',
                fontWeight: 600,
                color: '#1e293b',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={activeItem.fullName}
            >
              {activeItem.fullName}
            </span>
          ) : (
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#1e293b' }}>
              {activeItem?.title || 'Workspace Panel'}
            </span>
          )}
        </div>

        {/* Right controls: Expand/Collapse & Close */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>

          {/* Maximize / Restore */}
          <button
            type="button"
            onClick={toggleMaximize}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 4,
              color: '#64748b',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title={isMaximized ? 'Restore panel size' : 'Maximize panel'}
          >
            {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>

          {/* Collapse */}
          <button
            type="button"
            onClick={onCollapse || onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 4,
              color: '#64748b',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title="Collapse panel"
          >
            <ChevronRight size={16} />
          </button>

          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 4,
              color: '#64748b',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title="Close panel"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* ── Panel Content Body ── */}
      <div
        style={{
          flex: 1,
          height: '100%',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          background: isNotebook ? '#ffffff' : '#0d1117',
        }}
      >
        {!activeItem ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#64748b',
              fontSize: '0.85rem',
              padding: 24,
              textAlign: 'center',
              gap: 8,
              background: '#ffffff',
            }}
          >
            <BookOpen size={36} style={{ opacity: 0.3 }} />
            <div>Workspace Panel</div>
            <div style={{ fontSize: '0.76rem', color: '#94a3b8', maxWidth: 280 }}>
              Click any file, notebook, or dashboard in the changes dock to view, edit, or run it here.
            </div>
          </div>
        ) : isNotebook ? (
          <div style={{ flex: 1, height: '100%', overflow: 'hidden' }}>
            <NotebookPage
              notebookPath={activeItem.notebookPath || activeItem.fullName || 'notebooks/untitled.ipynb'}
              beforeContent={rec?.before_content}
              afterContent={rec?.after_content}
              embedded={true}
            />
          </div>
        ) : activeItem.type === 'diff' || rec ? (
          <div style={{ flex: 1, height: '100%', overflow: 'hidden' }}>
            <CodeDiffView
              before={rec?.before_content ?? null}
              after={rec?.after_content ?? null}
              fullName={activeItem.fullName}
            />
          </div>
        ) : activeItem.type === 'document' ? (
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: 20,
              color: '#1e293b',
              background: '#ffffff',
              fontSize: '0.88rem',
              lineHeight: 1.6,
            }}
          >
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
              {activeItem.documentContent}
            </pre>
          </div>
        ) : (
          <div style={{ flex: 1, padding: 20, color: '#94a3b8' }}>
            Preview not available for this item.
          </div>
        )}
      </div>
    </div>
  );
};
export default AgentWorkspacePanel;
