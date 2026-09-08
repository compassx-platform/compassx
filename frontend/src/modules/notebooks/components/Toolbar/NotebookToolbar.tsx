import { useState, useRef, useEffect } from 'react';
import { Play, RotateCcw, Square, Trash2, Plus, Hash, CalendarClock, MoreVertical, Check, X } from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import api from '@/lib/api';
import { useNotebookStore } from '../../store/notebookStore';
import { useExecuteCell } from '../../hooks/useExecuteCell';
import KernelStatus from './KernelStatus';
import PodSelector from './PodSelector';
import RestartDialog from './RestartDialog';
import ScheduleDialog from '../ScheduleDialog';

export default function NotebookToolbar({ notebookPath, onDelete }: { notebookPath?: string; onDelete?: () => void }) {
  const cells = useNotebookStore((s) => s.cells);
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const addCell = useNotebookStore((s) => s.addCell);
  const clearAllOutputs = useNotebookStore((s) => s.clearAllOutputs);
  const toggleLineNumbers = useNotebookStore((s) => s.toggleLineNumbers);
  const showLineNumbers = useNotebookStore((s) => s.showLineNumbers);
  const isDirty = useNotebookStore((s) => s.isDirty);
  const acceptAllAgentEdits = useNotebookStore((s) => s.acceptAllAgentEdits);
  const rejectAllAgentEdits = useNotebookStore((s) => s.rejectAllAgentEdits);
  const { executeCell } = useExecuteCell();
  const navigate = useScopedNavigate();

  const pendingCells = cells.filter((c) => c.cellStatus === 'pending' || !!c.pendingAgentEdit);

  const [showRestartDialog, setShowRestartDialog] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  async function runAll() {
    for (const cell of cells) {
      if (cell.type === 'code') {
        await executeCell(cell.id, cell.source);
      }
    }
  }

  function interrupt() {
    kernelRef?.interrupt();
  }

  function doRestart() {
    kernelRef?.restart();
    setShowRestartDialog(false);
  }

  const displayName = notebookPath
    ? notebookPath.split('/').pop()?.replace(/\.ipynb$/i, '')
    : 'notebook';

  async function handleDeleteNotebook() {
    if (!notebookPath) return;
    setIsDeleting(true);
    try {
      await api.delete(`/notebook/files/${notebookPath}`);
      if (onDelete) {
        onDelete();
      } else {
        navigate('/notebooks');
      }
    } catch (err) {
      console.error('[notebook] Failed to delete notebook:', err);
    } finally {
      setIsDeleting(false);
      setShowDeleteConfirm(false);
      setShowMenu(false);
    }
  }

  return (
    <>
      <div className="notebook-toolbar">
        <div className="notebook-toolbar-left">
          <button onClick={runAll} className="notebook-toolbar-btn" title="Run All">
            <Play size={14} /> <span>Run All</span>
          </button>
          <button onClick={interrupt} className="notebook-toolbar-btn" title="Interrupt">
            <Square size={14} /> <span>Interrupt</span>
          </button>
          <button
            onClick={() => setShowRestartDialog(true)}
            className="notebook-toolbar-btn"
            title="Restart Kernel"
          >
            <RotateCcw size={14} /> <span>Restart</span>
          </button>
          <button onClick={clearAllOutputs} className="notebook-toolbar-btn" title="Clear All Outputs">
            <Trash2 size={14} /> <span>Clear</span>
          </button>
          <button onClick={() => addCell('code')} className="notebook-toolbar-btn" title="Add Cell">
            <Plus size={14} /> <span>Add Cell</span>
          </button>
          <button
            onClick={toggleLineNumbers}
            className={`notebook-toolbar-btn ${showLineNumbers ? 'is-active' : ''}`}
            title="Toggle line numbers"
          >
            <Hash size={14} />
          </button>

          {pendingCells.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8, paddingLeft: 8, borderLeft: '1px solid var(--color-border, #e5e7eb)' }}>
              <button
                type="button"
                onClick={() => acceptAllAgentEdits()}
                className="notebook-toolbar-btn"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  background: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  color: '#16a34a',
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  padding: '3px 8px',
                  borderRadius: 4,
                }}
                title="Approve and apply all proposed cell edits"
              >
                <Check size={12} />
                <span>Approve all ({pendingCells.length})</span>
              </button>

              <button
                type="button"
                onClick={() => rejectAllAgentEdits()}
                className="notebook-toolbar-btn"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  color: '#dc2626',
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  padding: '3px 8px',
                  borderRadius: 4,
                }}
                title="Reject and revert all proposed cell edits"
              >
                <X size={12} />
                <span>Reject all ({pendingCells.length})</span>
              </button>
            </div>
          )}
        </div>
        <div className="notebook-toolbar-right">
          {isDirty && <span className="notebook-dirty-indicator" title="Unsaved changes">●</span>}

          {notebookPath && (
            <div className="notebook-actions-menu-wrapper" ref={menuRef}>
              <button
                className="notebook-toolbar-btn notebook-actions-menu-btn"
                onClick={() => setShowMenu((v) => !v)}
                title="Notebook options"
              >
                <MoreVertical size={14} />
              </button>

              {showMenu && (
                <div className="notebook-actions-popover-menu">
                  <button
                    type="button"
                    className="notebook-actions-menu-item notebook-actions-menu-item-danger"
                    onClick={() => {
                      setShowMenu(false);
                      setShowDeleteConfirm(true);
                    }}
                  >
                    <Trash2 size={13} />
                    <span>Delete notebook</span>
                  </button>
                </div>
              )}
            </div>
          )}

          <PodSelector />
          {notebookPath && (
            <button
              className="notebook-toolbar-btn"
              onClick={() => setShowSchedule(true)}
              title="Schedule notebook"
            >
              <CalendarClock size={14} /> <span>Schedule</span>
            </button>
          )}
          <KernelStatus />
        </div>
      </div>

      {showDeleteConfirm && (
        <div className="notebook-dialog-overlay">
          <div className="notebook-dialog">
            <h3 className="notebook-dialog-title">Delete Notebook</h3>
            <p className="notebook-dialog-body">
              Are you sure you want to delete <strong>{displayName}</strong>? This action cannot be undone.
            </p>
            <div className="notebook-dialog-actions">
              <button
                className="notebook-toolbar-btn"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                className="notebook-toolbar-btn notebook-toolbar-btn-danger"
                onClick={handleDeleteNotebook}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showRestartDialog && (
        <RestartDialog onConfirm={doRestart} onCancel={() => setShowRestartDialog(false)} />
      )}
      {showSchedule && notebookPath && (
        <ScheduleDialog notebookPath={notebookPath} onClose={() => setShowSchedule(false)} />
      )}
    </>
  );
}
