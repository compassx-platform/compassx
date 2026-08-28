import React from 'react';
import { GitBranch } from 'lucide-react';

interface HandoffCardProps {
  toolResult?: Record<string, unknown> | null;
}

export function HandoffCard({ toolResult }: HandoffCardProps) {
  const content = (toolResult?.content as string) ?? '';
  const meta = toolResult?.metadata as Record<string, unknown> | undefined;
  const invokedAgent = meta?.invoked_agent as string | undefined;
  const invokedBy = meta?.invoked_by as string | undefined;
  const task = meta?.task as string | undefined;

  return (
    <div
      style={{
        margin: '4px 0 12px',
        padding: '8px 12px',
        border: '1px dashed var(--color-border)',
        borderRadius: 8,
        background: 'var(--color-surface-hover)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        fontSize: '0.78rem',
        color: 'var(--color-text-muted)',
      }}
    >
      <GitBranch size={13} style={{ marginTop: 1, flexShrink: 0, opacity: 0.7 }} />
      <div>
        <div style={{ fontWeight: 500, color: 'var(--color-text)' }}>{content || 'Agent handoff'}</div>
        {invokedBy && invokedAgent && (
          <div style={{ marginTop: 2 }}>
            <span>{invokedBy}</span>
            <span style={{ margin: '0 4px', opacity: 0.5 }}>→</span>
            <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>{invokedAgent}</span>
          </div>
        )}
        {task && (
          <div style={{ marginTop: 3, fontStyle: 'italic', opacity: 0.75 }}>
            "{task.slice(0, 120)}{task.length > 120 ? '…' : ''}"
          </div>
        )}
      </div>
    </div>
  );
}
export default HandoffCard;
