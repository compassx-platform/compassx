import { useNotebookStore } from '../store/notebookStore';
import { X } from 'lucide-react';

interface Props {
  onClose: () => void;
}

export default function VariableExplorer({ onClose }: Props) {
  const variables = useNotebookStore((s) => s.variables);

  return (
    <div className="notebook-variable-explorer">
      <div className="notebook-variable-header">
        <span>Variables</span>
        <button className="notebook-toolbar-btn" onClick={onClose}><X size={12} /></button>
      </div>
      <div className="notebook-variable-list">
        {variables.length === 0 ? (
          <div className="notebook-variable-empty">No variables yet. Run a cell to populate.</div>
        ) : (
          variables.map((v) => (
            <div key={v} className="notebook-variable-item">
              <code>{v}</code>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
