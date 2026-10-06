import React from 'react';
import {
  RotateCw,
  ExternalLink,
  Loader2,
  Square,
  SquareTerminal,
} from 'lucide-react';

export type CanvasViewMode = 'preview' | 'code';

interface BrowserToolbarProps {
  viewMode: CanvasViewMode;
  onViewModeChange: (mode: CanvasViewMode) => void;
  previewUrl: string;
  route: string;
  onRouteChange: (route: string) => void;
  onReload: () => void;
  isReloading?: boolean;
  onDeploy: () => void;
  isDeploying?: boolean;
  isCanvasMaximized: boolean;
  onToggleCanvasMaximized: () => void;
  onToggleOutputCollapsed?: () => void;
  isOutputCollapsed?: boolean;
  disabled?: boolean;
}

export function BrowserToolbar({
  viewMode,
  onViewModeChange,
  previewUrl,
  route,
  onRouteChange,
  onReload,
  isReloading = false,
  onDeploy,
  isDeploying = false,
  isCanvasMaximized,
  onToggleCanvasMaximized,
  onToggleOutputCollapsed,
  isOutputCollapsed = false,
  disabled = false,
}: BrowserToolbarProps) {
  const fullPreviewUrl = previewUrl ? `${previewUrl}${route.startsWith('/') ? route : `/${route}`}` : '';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 12px',
        background: '#ffffff',
        borderBottom: '1px solid #e2e8f0',
        minHeight: 46,
        height: 46,
        gap: 10,
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {/* Left: View Mode Segmented Box ([ Preview | Code ]) */}
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'stretch',
          background: '#ffffff',
          borderRadius: 6,
          border: '1px solid #d1d5db',
          overflow: 'hidden',
          height: 28,
        }}
      >
        <button
          type="button"
          onClick={() => onViewModeChange('preview')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 12px',
            border: 'none',
            background: viewMode === 'preview' ? '#e0f2fe' : 'transparent',
            color: '#0f172a',
            fontSize: '0.78rem',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            if (viewMode !== 'preview') e.currentTarget.style.background = '#f8fafc';
          }}
          onMouseLeave={(e) => {
            if (viewMode !== 'preview') e.currentTarget.style.background = 'transparent';
          }}
        >
          Preview
        </button>

        {/* Separator Divider */}
        <div style={{ width: 1, background: '#d1d5db', alignSelf: 'stretch' }} />

        <button
          type="button"
          onClick={() => onViewModeChange('code')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 12px',
            border: 'none',
            background: viewMode === 'code' ? '#e0f2fe' : 'transparent',
            color: '#0f172a',
            fontSize: '0.78rem',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            if (viewMode !== 'code') e.currentTarget.style.background = '#f8fafc';
          }}
          onMouseLeave={(e) => {
            if (viewMode !== 'code') e.currentTarget.style.background = 'transparent';
          }}
        >
          Code
        </button>
      </div>

      {/* Center: In-App Browser Address Bar (only when in Preview mode) */}
      {viewMode === 'preview' && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            flex: 1,
            maxWidth: 480,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            padding: '2px 8px',
            gap: 6,
            minWidth: 160,
          }}
        >
          {/* Route input */}
          <span style={{ fontSize: '0.76rem', color: '#94a3b8', fontFamily: 'monospace' }}>
            {previewUrl ? new URL(previewUrl).origin : 'localhost'}
          </span>
          <input
            type="text"
            value={route}
            onChange={(e) => onRouteChange(e.target.value)}
            placeholder="/"
            disabled={disabled}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontSize: '0.76rem',
              color: '#0f172a',
              fontFamily: 'monospace',
              minWidth: 40,
            }}
          />

          {/* Reload Button (moved to right) */}
          <button
            type="button"
            onClick={onReload}
            disabled={disabled || isReloading}
            title="Reload preview"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: disabled ? 'not-allowed' : 'pointer',
              padding: 2,
              borderRadius: 4,
            }}
          >
            <RotateCw size={13} className={isReloading ? 'animate-spin text-blue-600' : ''} />
          </button>

          {/* Open in External Tab */}
          {fullPreviewUrl && (
            <a
              href={fullPreviewUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Open preview in new window"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#64748b',
                padding: 2,
                borderRadius: 4,
                textDecoration: 'none',
              }}
            >
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      )}

      {/* Right: Output Drawer toggle & Primary Deploy Button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Toggle Output Drawer with hover tooltip (Clean ghost button) */}
        {onToggleOutputCollapsed && (
          <div className="relative group">
            <button
              type="button"
              onClick={onToggleOutputCollapsed}
              title={isOutputCollapsed ? 'Show preview output' : 'Hide preview output'}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: !isOutputCollapsed ? '#e0f2fe' : 'transparent',
                border: 'none',
                borderRadius: 4,
                width: 28,
                height: 28,
                color: !isOutputCollapsed ? '#0284c7' : '#52525b',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (isOutputCollapsed) {
                  e.currentTarget.style.background = '#f4f4f5';
                  e.currentTarget.style.color = '#18181b';
                }
              }}
              onMouseLeave={(e) => {
                if (isOutputCollapsed) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#52525b';
                }
              }}
            >
              <SquareTerminal size={16} strokeWidth={1.75} />
            </button>
            <div className="absolute right-0 top-full mt-1.5 hidden group-hover:flex items-center whitespace-nowrap rounded bg-neutral-900 px-2 py-1 text-[11px] font-sans text-white shadow-md z-50 pointer-events-none">
              {isOutputCollapsed ? 'Show preview output' : 'Hide preview output'}
            </div>
          </div>
        )}

        {/* Deploy Button */}
        <button
          type="button"
          onClick={onDeploy}
          disabled={disabled || isDeploying}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0284c7',
            border: 'none',
            borderRadius: 6,
            color: '#ffffff',
            padding: '5px 14px',
            fontSize: '0.78rem',
            fontWeight: 500,
            cursor: disabled || isDeploying ? 'not-allowed' : 'pointer',
            opacity: disabled || isDeploying ? 0.7 : 1,
            boxShadow: '0 1px 2px rgba(2, 132, 199, 0.2)',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => {
            if (!disabled && !isDeploying) e.currentTarget.style.background = '#0369a1';
          }}
          onMouseLeave={(e) => {
            if (!disabled && !isDeploying) e.currentTarget.style.background = '#0284c7';
          }}
        >
          {isDeploying ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <Loader2 size={12} className="animate-spin" />
              <span>Deploying...</span>
            </div>
          ) : (
            <span>Deploy</span>
          )}
        </button>
      </div>
    </div>
  );
}
