import { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useNotebookStore } from '../../store/notebookStore';
import CellToolbar from './CellToolbar';
import AgentEditDiff from './AgentEditDiff';

interface Props {
  cellId: string;
  cellIndex: number;
}

export default function MarkdownCell({ cellId, cellIndex }: Props) {
  const cell = useNotebookStore((s) => s.cells.find((c) => c.id === cellId));
  const updateCellSource = useNotebookStore((s) => s.updateCellSource);
  const [editing, setEditing] = useState(!cell?.source);

  const startEdit = useCallback(() => setEditing(true), []);
  const stopEdit = useCallback(() => setEditing(false), []);

  const isCellCollapsed = useNotebookStore((s) => s.collapsedCells.has(cellId));

  if (!cell) return null;

  return (
    <div className="notebook-cell notebook-cell-markdown">
      <CellToolbar cellId={cellId} cellIndex={cellIndex} isRunning={false} onRun={stopEdit} />
      <div className="notebook-cell-body">
        {isCellCollapsed && (
          <div
            className="notebook-collapsed-cell-hint"
            onClick={() => useNotebookStore.getState().toggleCollapseCell(cellId)}
            title="Click to expand markdown cell"
          >
            <em>Markdown cell collapsed</em>
          </div>
        )}
        <div style={{ display: isCellCollapsed ? 'none' : 'block' }}>
          {editing ? (
            <textarea
              autoFocus
              className="notebook-markdown-editor"
              value={cell.source}
              onChange={(e) => updateCellSource(cellId, e.target.value)}
              onBlur={stopEdit}
              onKeyDown={(e) => {
                if (e.key === 'Escape') stopEdit();
                if (e.key === 'Enter' && e.shiftKey) { e.preventDefault(); stopEdit(); }
              }}
            />
          ) : (
            <div
              className="notebook-markdown-preview"
              onDoubleClick={startEdit}
            >
              {cell.source ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{cell.source}</ReactMarkdown>
              ) : (
                <em className="notebook-markdown-placeholder" onDoubleClick={startEdit}>
                  Double-click to edit markdown
                </em>
              )}
            </div>
          )}
          {cell.pendingAgentEdit && <AgentEditDiff cellId={cellId} proposal={cell.pendingAgentEdit} />}
        </div>
      </div>
    </div>
  );
}
