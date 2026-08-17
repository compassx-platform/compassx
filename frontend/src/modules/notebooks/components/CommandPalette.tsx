import { useState, useEffect, useRef, useCallback } from 'react';
import { useNotebookStore } from '../store/notebookStore';
import { useExecuteCell } from '../hooks/useExecuteCell';

interface Command {
  id: string;
  label: string;
  action: () => void;
}

interface Props {
  onClose: () => void;
}

export default function CommandPalette({ onClose }: Props) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const cells = useNotebookStore((s) => s.cells);
  const focusedCellId = useNotebookStore((s) => s.focusedCellId);
  const addCell = useNotebookStore((s) => s.addCell);
  const deleteCell = useNotebookStore((s) => s.deleteCell);
  const clearAllOutputs = useNotebookStore((s) => s.clearAllOutputs);
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const toggleLineNumbers = useNotebookStore((s) => s.toggleLineNumbers);
  const { executeCell } = useExecuteCell();

  const commands: Command[] = [
    { id: 'add-code', label: 'Add Code Cell Below', action: () => { addCell('code', focusedCellId ?? undefined); onClose(); } },
    { id: 'add-markdown', label: 'Add Markdown Cell Below', action: () => { addCell('markdown', focusedCellId ?? undefined); onClose(); } },
    { id: 'delete-cell', label: 'Delete Current Cell', action: () => { if (focusedCellId) deleteCell(focusedCellId); onClose(); } },
    { id: 'run-all', label: 'Run All Cells', action: async () => { onClose(); for (const c of cells) if (c.type === 'code') await executeCell(c.id, c.source); } },
    { id: 'interrupt', label: 'Interrupt Kernel', action: () => { kernelRef?.interrupt(); onClose(); } },
    { id: 'restart', label: 'Restart Kernel', action: () => { kernelRef?.restart(); onClose(); } },
    { id: 'clear-outputs', label: 'Clear All Outputs', action: () => { clearAllOutputs(); onClose(); } },
    { id: 'toggle-lines', label: 'Toggle Line Numbers', action: () => { toggleLineNumbers(); onClose(); } },
  ];

  const filtered = commands.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase()),
  );

  const [selected, setSelected] = useState(0);

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { setSelected(0); }, [query]);

  const run = useCallback(
    (idx: number) => { filtered[idx]?.action(); },
    [filtered],
  );

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); run(selected); }
    else if (e.key === 'Escape') onClose();
  }

  return (
    <div className="notebook-dialog-overlay" onClick={onClose}>
      <div className="notebook-command-palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="notebook-command-input"
          placeholder="Type a command…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKey}
        />
        <div className="notebook-command-list">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.id}
              className={`notebook-command-item ${i === selected ? 'is-selected' : ''}`}
              onClick={() => run(i)}
              onMouseEnter={() => setSelected(i)}
            >
              {cmd.label}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="notebook-command-empty">No commands match</div>
          )}
        </div>
      </div>
    </div>
  );
}
