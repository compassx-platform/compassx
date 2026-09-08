import React from 'react';

interface AgentBadgeProps {
  name: string;
  color?: string | null;
  depth?: number;
  size?: 'sm' | 'xs';
}

export function AgentBadge({
  name,
  color,
  depth = 0,
  size = 'sm',
}: AgentBadgeProps) {
  const bg = color ?? '#6366f1';
  const fontSize = size === 'xs' ? '0.62rem' : '0.68rem';
  const padding = size === 'xs' ? '1px 5px' : '2px 7px';
  return (
    <span
      title={`Invocation depth: ${depth}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        background: `${bg}22`,
        border: `1px solid ${bg}55`,
        color: bg,
        borderRadius: 99,
        fontSize,
        fontWeight: 600,
        padding,
        letterSpacing: '0.01em',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: bg,
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      {name}
      {depth > 0 && (
        <span style={{ opacity: 0.6, fontSize: '0.58rem' }}>·{depth}</span>
      )}
    </span>
  );
}
export default AgentBadge;
