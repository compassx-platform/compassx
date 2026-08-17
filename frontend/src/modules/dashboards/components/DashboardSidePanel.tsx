/**
 * DashboardSidePanel — common right-side panel wrapper component.
 * Ensures consistent width (320px), border-left, and layout across
 * Dashboard Settings and Widget Configuration panels.
 */

import React from 'react';

interface Props {
  width?: number;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export default function DashboardSidePanel({ width = 320, children, className, style }: Props) {
  return (
    <div
      className={`dashboard-side-panel ${className ?? ''}`}
      style={{
        width,
        flexShrink: 0,
        height: '100%',
        background: 'var(--color-surface)',
        borderLeft: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        boxSizing: 'border-box',
        ...style,
      }}
    >
      {children}
    </div>
  );
}
