import { Loader2 } from 'lucide-react';
import type { RunState, TaskRunState, JobStatus } from '../lib/jobsTypes';

type AnyState = RunState | TaskRunState | JobStatus | string;

const CONFIG: Record<string, { label: string; bg: string; color: string }> = {
  success:         { label: 'Success',       bg: 'rgba(34,197,94,0.12)',  color: '#16a34a' },
  failed:          { label: 'Failed',        bg: 'rgba(239,68,68,0.12)',  color: '#dc2626' },
  running:         { label: 'Running',       bg: 'rgba(59,130,246,0.14)', color: '#2563eb' },
  queued:          { label: 'Queued',        bg: 'rgba(156,163,175,0.15)',color: '#6b7280' },
  up_for_retry:    { label: 'Retry',         bg: 'rgba(245,158,11,0.12)', color: '#d97706' },
  cancelled:       { label: 'Cancelled',     bg: 'rgba(107,114,128,0.1)', color: '#6b7280' },
  upstream_failed: { label: 'Upstream fail', bg: 'rgba(239,68,68,0.08)',  color: '#ef4444' },
  skipped:         { label: 'Skipped',       bg: 'rgba(156,163,175,0.1)', color: '#9ca3af' },
  active:          { label: 'Active',        bg: 'rgba(34,197,94,0.12)',  color: '#16a34a' },
  paused:          { label: 'Paused',        bg: 'rgba(245,158,11,0.12)', color: '#d97706' },
  archived:        { label: 'Archived',      bg: 'rgba(156,163,175,0.12)',color: '#6b7280' },
};

interface Props {
  state: AnyState;
  size?: 'sm' | 'md' | 'lg';
  showDot?: boolean;
  iconOnly?: boolean;
}

export default function StatusPill({ state, size = 'md', showDot = true, iconOnly = false }: Props) {
  const cfg = CONFIG[state] ?? { label: state, bg: 'rgba(156,163,175,0.1)', color: '#6b7280' };
  const pad = size === 'sm' ? '2px 7px' : size === 'lg' ? '5px 14px' : '3px 10px';
  const fs  = size === 'sm' ? '0.68rem'  : size === 'lg' ? '0.85rem'  : '0.73rem';
  const iconSize = size === 'sm' ? 10 : size === 'lg' ? 14 : 12;

  const isRunning = state === 'running';

  if (iconOnly) {
    const boxSize = size === 'sm' ? 18 : size === 'lg' ? 24 : 20;
    const dotSize = size === 'sm' ? 6 : size === 'lg' ? 8 : 7;
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: boxSize,
          height: boxSize,
          borderRadius: '50%',
          background: cfg.bg,
          color: cfg.color,
          flexShrink: 0,
        }}
      >
        {isRunning ? (
          <Loader2 size={size === 'sm' ? 10 : 12} className="spin" style={{ color: cfg.color }} />
        ) : (
          <span
            style={{
              width: dotSize,
              height: dotSize,
              borderRadius: '50%',
              background: cfg.color,
            }}
          />
        )}
      </span>
    );
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: pad,
        borderRadius: 4,
        background: cfg.bg,
        color: cfg.color,
        fontSize: fs,
        fontWeight: 600,
        whiteSpace: 'nowrap',
      }}
    >
      {isRunning ? (
        <Loader2 size={iconSize} className="spin" style={{ color: cfg.color, flexShrink: 0 }} />
      ) : (
        showDot && (
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: cfg.color,
              flexShrink: 0,
            }}
          />
        )
      )}
      {cfg.label}
    </span>
  );
}
