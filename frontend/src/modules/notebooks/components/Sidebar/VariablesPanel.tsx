import React from 'react';
import { Braces, RefreshCw, Copy, Check } from 'lucide-react';
import { useNotebookStore } from '../../store/notebookStore';
import type { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';

export default function VariablesPanel() {
  const variables = useNotebookStore((s) => s.variables);
  const setVariables = useNotebookStore((s) => s.setVariables);
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);
  const [copiedVar, setCopiedVar] = React.useState<string | null>(null);

  function refreshVariables() {
    const kernel = kernelRef as IKernelConnection | null;
    if (!kernel) return;
    const future = kernel.requestExecute({ code: '%who_ls', store_history: false, silent: true });
    const vars: string[] = [];
    future.onIOPub = (msg) => {
      if (msg.header.msg_type === 'execute_result') {
        const data = (msg.content as Record<string, unknown>).data as Record<string, string>;
        const plain = data?.['text/plain'] ?? '';
        const matches = plain.match(/'([^']+)'/g);
        if (matches) vars.push(...matches.map((m) => m.replace(/'/g, '')));
      }
    };
    future.done.then(() => setVariables(vars));
  }

  function handleCopy(name: string) {
    navigator.clipboard.writeText(name);
    setCopiedVar(name);
    setTimeout(() => setCopiedVar(null), 1500);
  }

  return (
    <div className="notebook-variables-panel">
      <div className="notebook-sidebar-section-header">
        <span className="notebook-sidebar-count">{variables.length} active variable{variables.length === 1 ? '' : 's'}</span>
        <button
          type="button"
          className="notebook-sidebar-icon-btn"
          onClick={refreshVariables}
          disabled={!kernelRef || kernelStatus === 'dead'}
          title="Refresh variables"
        >
          <RefreshCw size={12} />
        </button>
      </div>

      {variables.length === 0 ? (
        <div className="notebook-sidebar-empty">
          <Braces size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
          <span>No variables defined in current kernel session. Execute cells defining variables to inspect them here.</span>
        </div>
      ) : (
        <div className="notebook-variables-list">
          {variables.map((varName) => (
            <div key={varName} className="notebook-variable-item">
              <span className="notebook-variable-name">{varName}</span>
              <button
                type="button"
                className="notebook-variable-copy-btn"
                onClick={() => handleCopy(varName)}
                title="Copy variable name"
              >
                {copiedVar === varName ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
