import { useState, useEffect, useCallback } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Plus } from 'lucide-react';
import { useNotebookStore } from '../store/notebookStore';
import { useKernel } from '../hooks/useKernel';
import NotebookToolbar from './Toolbar/NotebookToolbar';
import CodeCell from './Cell/CodeCell';
import MarkdownCell from './Cell/MarkdownCell';
import CommandPalette from './CommandPalette';
import VariableExplorer from './VariableExplorer';
import ConnectComputeModal from './ConnectComputeModal';

interface Props {
  notebookPath?: string;
  isLoading?: boolean;
  onDelete?: () => void;
}

function NotebookSkeleton() {
  return (
    <div className="notebook-skeleton-wrapper">
      {[1, 2, 3].map((n) => (
        <div key={n} className="notebook-skeleton-card">
          <div className="notebook-skeleton-toolbar">
            <div className="notebook-skeleton-chip" style={{ width: 28, height: 16 }} />
            <div className="notebook-skeleton-chip" style={{ width: 22, height: 16 }} />
            <div className="notebook-skeleton-chip" style={{ width: 140, height: 16, margin: '0 auto' }} />
            <div className="notebook-skeleton-chip" style={{ width: 44, height: 16 }} />
            <div className="notebook-skeleton-chip" style={{ width: 18, height: 16 }} />
            <div className="notebook-skeleton-chip" style={{ width: 18, height: 16 }} />
          </div>
          <div className="notebook-skeleton-editor">
            <div className="notebook-skeleton-line" style={{ width: '45%' }} />
            <div className="notebook-skeleton-line" style={{ width: '70%' }} />
            <div className="notebook-skeleton-line" style={{ width: '30%' }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Sortable cell wrapper ──────────────────────────────────────────────────
function SortableCell({ id, children }: { id: string; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    position: 'relative',
  };
  return (
    <div ref={setNodeRef} style={style}>
      <button
        className="notebook-drag-handle"
        {...attributes}
        {...listeners}
        title="Drag to reorder"
      >
        <GripVertical size={14} />
      </button>
      {children}
    </div>
  );
}

// ── Main Notebook ──────────────────────────────────────────────────────────
export default function Notebook({ notebookPath = 'notebooks/untitled.ipynb', isLoading = false, onDelete }: Props) {
  const { showConnectModal, dismissConnectModal, connectToDefault } = useKernel(notebookPath);

  const cells = useNotebookStore((s) => s.cells);
  const addCell = useNotebookStore((s) => s.addCell);
  const reorderCells = useNotebookStore((s) => s.reorderCells);
  const focusedCellId = useNotebookStore((s) => s.focusedCellId);
  const setFocusedCell = useNotebookStore((s) => s.setFocusedCell);

  // Guarantee at least 1 blank code cell is present in loaded notebook
  useEffect(() => {
    if (!isLoading && cells.length === 0) {
      addCell('code');
    }
  }, [isLoading, cells.length, addCell]);

  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showVariableExplorer, setShowVariableExplorer] = useState(false);

  // Cmd+Shift+P → command palette
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'p') {
        e.preventDefault();
        setShowCommandPalette((v) => !v);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Arrow key navigation between cells (when editor not focused)
  const navigateCell = useCallback(
    (dir: 'up' | 'down') => {
      const idx = cells.findIndex((c) => c.id === focusedCellId);
      if (idx === -1) return;
      const next = dir === 'up' ? cells[idx - 1] : cells[idx + 1];
      if (next) setFocusedCell(next.id);
    },
    [cells, focusedCellId, setFocusedCell],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Only navigate when focus is NOT inside a CodeMirror editor
      if ((e.target as HTMLElement)?.closest('.cm-editor')) return;
      if (e.key === 'ArrowUp') navigateCell('up');
      if (e.key === 'ArrowDown') navigateCell('down');
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigateCell]);

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const ids = cells.map((c) => c.id);
    const oldIdx = ids.indexOf(active.id as string);
    const newIdx = ids.indexOf(over.id as string);
    reorderCells(arrayMove(ids, oldIdx, newIdx));
  }

  return (
    <div className="notebook-container">
      <NotebookToolbar notebookPath={notebookPath} onDelete={onDelete} />

      <div className="notebook-body">
        <div className="notebook-scroll-area">
          <div className="notebook-cells">
            {isLoading ? (
              <NotebookSkeleton />
            ) : (
              <>
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  <SortableContext items={cells.map((c) => c.id)} strategy={verticalListSortingStrategy}>
                    {cells.map((cell, index) => (
                      <div key={cell.id}>
                        <SortableCell id={cell.id}>
                          {cell.type === 'code' ? (
                            <CodeCell cellId={cell.id} cellIndex={index} />
                          ) : (
                            <MarkdownCell cellId={cell.id} cellIndex={index} />
                          )}
                        </SortableCell>
                        <div className="notebook-add-cell-divider">
                          <div className="notebook-add-cell-actions">
                            <button
                              className="notebook-add-cell-pill"
                              onClick={() => addCell('code', cell.id)}
                              title="Add Code cell below"
                            >
                              <Plus size={13} /> <span>Code</span>
                            </button>
                            <button
                              className="notebook-add-cell-pill"
                              onClick={() => addCell('markdown', cell.id)}
                              title="Add Text cell below"
                            >
                              <Plus size={13} /> <span>Text</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </SortableContext>
                </DndContext>

                {cells.length === 0 && (
                  <div className="notebook-add-cell-divider notebook-add-cell-divider--empty">
                    <div className="notebook-add-cell-actions">
                      <button className="notebook-add-cell-pill" onClick={() => addCell('code')}>
                        <Plus size={13} /> <span>Code</span>
                      </button>
                      <button className="notebook-add-cell-pill" onClick={() => addCell('markdown')}>
                        <Plus size={13} /> <span>Text</span>
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {showVariableExplorer && (
          <VariableExplorer onClose={() => setShowVariableExplorer(false)} />
        )}
      </div>

      <div className="notebook-footer">
        <button
          className="notebook-toolbar-btn"
          onClick={() => setShowVariableExplorer((v) => !v)}
          title="Variable Explorer"
        >
          {'{x}'} Variables
        </button>
        <span className="notebook-shortcut-hint">Cmd+Shift+P — command palette</span>
      </div>

      {showCommandPalette && (
        <CommandPalette onClose={() => setShowCommandPalette(false)} />
      )}

      {showConnectModal && (
        <ConnectComputeModal
          onConnectDefault={connectToDefault}
          onSelectCompute={() => {
            dismissConnectModal();
            // Focus the PodSelector so user can pick a compute
            const selector = document.querySelector<HTMLSelectElement>('.notebook-pod-select');
            if (selector) {
              selector.focus();
              selector.click();
            }
          }}
          onDismiss={dismissConnectModal}
        />
      )}
    </div>
  );
}
