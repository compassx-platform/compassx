import { ChevronUp, ChevronDown, Trash2, Play, Minimize2, Maximize2, Check, X } from 'lucide-react';
import { useNotebookStore, type CellType } from '../../store/notebookStore';

interface Props {
  cellId: string;
  cellIndex: number;
  isRunning: boolean;
  onRun: () => void;
  executionCount?: number | null;
  executedAt?: Date;
}

const CELL_TYPES: CellType[] = ['code', 'markdown'];

export default function CellToolbar({ cellId, cellIndex, isRunning, onRun, executionCount, executedAt }: Props) {
  const cell = useNotebookStore((s) => s.cells.find((c) => c.id === cellId));
  const isCellCollapsed = useNotebookStore((s) => s.collapsedCells.has(cellId));
  const toggleCollapseCell = useNotebookStore((s) => s.toggleCollapseCell);
  const deleteCell = useNotebookStore((s) => s.deleteCell);
  const moveCellUp = useNotebookStore((s) => s.moveCellUp);
  const moveCellDown = useNotebookStore((s) => s.moveCellDown);
  const setCellType = useNotebookStore((s) => s.setCellType);
  const updateCellTitle = useNotebookStore((s) => s.updateCellTitle);

  if (!cell) return null;

  const executionLabel = isRunning ? '[*]' : executionCount != null ? `[${executionCount}]` : cell.type === 'code' ? '[ ]' : null;

  return (
    <div className="notebook-cell-toolbar">
      <div className="notebook-cell-toolbar-left">
        {executionLabel && (
          <span className="notebook-cell-exec-count-chip">{executionLabel}</span>
        )}
        <button
          onClick={onRun}
          disabled={isRunning}
          className={`notebook-cell-icon-btn ${cell.cellStatus === 'pending' ? 'is-suggested' : ''}`}
          title={cell.cellStatus === 'pending' ? 'Run suggested (Shift+Enter)' : 'Run cell (Shift+Enter)'}
        >
          <Play size={13} fill="currentColor" />
          {cell.cellStatus === 'pending' && <span style={{ marginLeft: '4px', fontWeight: 600 }}>Run suggested</span>}
        </button>
      </div>

      <div className="notebook-cell-toolbar-middle">
        <span className="notebook-cell-index-label">{cellIndex + 1}:</span>
        <input
          type="text"
          value={cell.title || ''}
          onChange={(e) => updateCellTitle(cellId, e.target.value)}
          placeholder={cell.type}
          className="notebook-cell-title-input"
        />
      </div>

      <div className="notebook-cell-toolbar-right">
        <select
          value={cell.type}
          onChange={(e) => setCellType(cellId, e.target.value as CellType)}
          className="notebook-cell-type-select"
        >
          {CELL_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <button
          onClick={() => toggleCollapseCell(cellId)}
          className="notebook-cell-icon-btn"
          title={isCellCollapsed ? 'Expand cell' : 'Collapse cell'}
        >
          {isCellCollapsed ? <Maximize2 size={13} /> : <Minimize2 size={13} />}
        </button>
        <button onClick={() => moveCellUp(cellId)} className="notebook-cell-icon-btn" title="Move up">
          <ChevronUp size={13} />
        </button>
        <button onClick={() => moveCellDown(cellId)} className="notebook-cell-icon-btn" title="Move down">
          <ChevronDown size={13} />
        </button>
        <button
          onClick={() => deleteCell(cellId)}
          className="notebook-cell-icon-btn notebook-cell-icon-btn-danger"
          title="Delete cell"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}
