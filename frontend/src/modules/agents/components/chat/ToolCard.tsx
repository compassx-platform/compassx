import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { HandoffCard } from './HandoffCard';

interface ToolCardProps {
  toolName: string;
  toolResult?: Record<string, unknown> | null;
}

export function ToolCard({ toolName, toolResult }: ToolCardProps) {
  if (toolName === 'invoke_agent' && toolResult?.source === 'system') {
    return <HandoffCard toolResult={toolResult} />;
  }

  const args = (toolResult?.args ?? (toolResult as any)?.arguments) as Record<string, unknown> | undefined;
  const ok = toolResult?.ok !== false;
  const error = toolResult?.error;
  const result = toolResult && 'result' in toolResult ? toolResult.result : (args !== undefined ? undefined : toolResult);
  const [open, setOpen] = useState(false);

  // Format arguments summary (e.g. query/file/asset/step_id)
  const argSummary = args
    ? (args.query ?? args.filename ?? args.path ?? args.name ?? args.asset_id ?? args.prompt ?? args.step_id ?? args.command ?? '')
    : '';

  return (
    <div style={{ margin: '3px 0 3px 0', color: '#6b7280', fontSize: '0.82rem', minWidth: 0, maxWidth: '100%' }}>
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          cursor: 'pointer',
          userSelect: 'none',
          maxWidth: '100%',
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}>
          {open ? <ChevronDown size={12} color="#6b7280" /> : <ChevronRight size={12} color="#6b7280" />}
        </span>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {toolName} {argSummary ? <span style={{ opacity: 0.85 }}>({String(argSummary)})</span> : null}
        </span>
      </div>
      {open && (
        <div style={{ marginTop: 6, paddingLeft: 18, fontSize: '0.75rem', fontFamily: 'monospace', color: '#4b5563', minWidth: 0, maxWidth: '100%' }}>
          <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 6, marginTop: 4, minWidth: 0, maxWidth: '100%' }}>
            {args && Object.keys(args).length > 0 ? (
              <div style={{ marginBottom: 6, minWidth: 0, maxWidth: '100%' }}>
                <div style={{ fontWeight: 600, fontSize: '0.7rem', color: '#9ca3af', textTransform: 'uppercase', marginBottom: 2 }}>Input</div>
                <pre
                  style={{
                    margin: 0,
                    maxHeight: 320,
                    width: '100%',
                    maxWidth: '100%',
                    boxSizing: 'border-box',
                    overflowY: 'auto',
                    overflowX: 'auto',
                    background: 'rgba(0,0,0,0.03)',
                    padding: '6px 8px',
                    borderRadius: 4,
                    scrollbarWidth: 'thin',
                    whiteSpace: 'pre',
                  }}
                >
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            ) : null}
            {result != null ? (
              <div style={{ marginTop: args && Object.keys(args).length > 0 ? 6 : 0, minWidth: 0, maxWidth: '100%' }}>
                <div style={{ borderTop: args && Object.keys(args).length > 0 ? '1px dashed #e5e7eb' : 'none', paddingTop: args && Object.keys(args).length > 0 ? 6 : 0, marginBottom: 2, fontWeight: 600, fontSize: '0.7rem', color: '#9ca3af', textTransform: 'uppercase' }}>Result</div>
                <pre
                  style={{
                    margin: 0,
                    maxHeight: 480,
                    width: '100%',
                    maxWidth: '100%',
                    boxSizing: 'border-box',
                    overflowY: 'auto',
                    overflowX: 'auto',
                    background: 'rgba(0,0,0,0.03)',
                    padding: '6px 8px',
                    borderRadius: 4,
                    scrollbarWidth: 'thin',
                    whiteSpace: 'pre',
                  }}
                >
                  {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                </pre>
              </div>
            ) : null}
            {error ? (
              <div style={{ marginTop: 6, minWidth: 0, maxWidth: '100%' }}>
                <div style={{ fontWeight: 600, fontSize: '0.7rem', color: '#ef4444', textTransform: 'uppercase', marginBottom: 2 }}>Error</div>
                <pre
                  style={{
                    margin: 0,
                    maxHeight: 320,
                    width: '100%',
                    maxWidth: '100%',
                    boxSizing: 'border-box',
                    overflowY: 'auto',
                    overflowX: 'auto',
                    background: 'rgba(239,68,68,0.08)',
                    color: '#dc2626',
                    padding: '6px 8px',
                    borderRadius: 4,
                    scrollbarWidth: 'thin',
                    whiteSpace: 'pre',
                  }}
                >
                  {String(error)}
                </pre>
              </div>
            ) : null}
            {!args && result == null && !error && (
              <div style={{ fontStyle: 'italic', opacity: 0.6, padding: '2px 0' }}>Executing tool...</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
export default ToolCard;
