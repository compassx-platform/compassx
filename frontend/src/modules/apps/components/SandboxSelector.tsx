import React, { useState, useRef, useEffect } from 'react';
import {
  ChevronDown,
  FolderGit2,
  FolderPlus,
  Loader2,
  GitBranch,
  Check,
} from 'lucide-react';
import type { DevWorkspace } from '../hooks/useApps';

export interface SandboxSelectorProps {
  appId: string;
  workspaces: DevWorkspace[];
  activeWorkspaceId?: string;
  baseBranch?: string;
  onSelectWorkspace: (workspaceId: string) => void;
  onOpenNewSandboxModal: () => void;
  isSwitching?: boolean;
  disabled?: boolean;
}

export function SandboxSelector({
  appId,
  workspaces,
  activeWorkspaceId,
  baseBranch = 'main',
  onSelectWorkspace,
  onOpenNewSandboxModal,
  isSwitching = false,
  disabled = false,
}: SandboxSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Resolve currently active workspace
  const activeWs =
    workspaces.find((w) => w.id === activeWorkspaceId || (w.status === 'active' && !activeWorkspaceId)) ||
    workspaces.find((w) => w.status === 'active') ||
    workspaces[0];

  const activeName = activeWs?.name || 'default';
  const activeBranch = activeWs?.git_branch || `dev/${activeName}`;

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* ── Header Trigger Pill (Clean Minimalist Theme) ── */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled || isSwitching}
        title={`Active Sandbox: ${activeName} (${activeBranch}). Click to switch or create.`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 10px',
          borderRadius: 6,
          fontSize: '0.75rem',
          border: isOpen ? '1px solid #94a3b8' : '1px solid #e2e8f0',
          background: isOpen ? '#f8fafc' : '#ffffff',
          color: '#0f172a',
          cursor: disabled || isSwitching ? 'not-allowed' : 'pointer',
          transition: 'all 0.15s ease',
          height: 28,
        }}
        onMouseEnter={(e) => {
          if (!disabled && !isSwitching && !isOpen) {
            e.currentTarget.style.background = '#f8fafc';
            e.currentTarget.style.borderColor = '#cbd5e1';
          }
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = '#ffffff';
            e.currentTarget.style.borderColor = '#e2e8f0';
          }
        }}
      >
        {isSwitching ? (
          <Loader2 size={13} className="spin text-sky-600" />
        ) : (
          <GitBranch size={13} className="text-neutral-500 shrink-0" />
        )}

        <span
          style={{
            color: '#0f172a',
            fontWeight: 500,
            maxWidth: 180,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {activeName}
        </span>

        <span style={{ color: '#94a3b8', fontSize: '0.72rem', userSelect: 'none' }}>/</span>

        <span
          style={{
            color: '#64748b',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            fontSize: '0.71rem',
            maxWidth: 160,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {activeBranch}
        </span>

        <ChevronDown
          size={12}
          style={{
            color: '#94a3b8',
            transform: isOpen ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.15s ease',
            marginLeft: 1,
            flexShrink: 0,
          }}
        />
      </button>

      {/* ── Dropdown Menu (Clean Minimalist Theme) ── */}
      {isOpen && (
        <div
          className="bg-white"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 9999,
            width: 'max-content',
            minWidth: 300,
            maxWidth: 440,
            backgroundColor: '#ffffff',
            border: '1px solid #d1d5db',
            borderRadius: 8,
            boxShadow: '0 10px 30px -4px rgba(0, 0, 0, 0.16), 0 4px 10px -2px rgba(0, 0, 0, 0.08)',
            overflow: 'hidden',
            padding: '6px',
            opacity: 1,
          }}
        >
          {/* Top Action Row: Open / New Sandbox */}
          <div
            onClick={() => {
              setIsOpen(false);
              onOpenNewSandboxModal();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '7px 8px',
              borderRadius: 6,
              cursor: 'pointer',
              color: '#0f172a',
              fontSize: '0.78rem',
              fontWeight: 500,
              transition: 'background 0.12s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <FolderPlus size={14} style={{ color: '#0284c7' }} />
            <span>New Sandbox</span>
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: '#f1f5f9', margin: '4px 0' }} />

          {/* Section Header: Sandboxes */}
          <div
            style={{
              padding: '4px 8px 6px',
              fontSize: '0.7rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: '#94a3b8',
              userSelect: 'none',
            }}
          >
            Sandboxes
          </div>

          {/* Sandboxes List */}
          <div style={{ maxHeight: 260, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
            {workspaces.length === 0 ? (
              <div style={{ padding: '12px 8px', textAlign: 'center', color: '#9ca3af', fontSize: '0.75rem' }}>
                No sandboxes found.
              </div>
            ) : (
              workspaces.map((ws) => {
                const isActive = ws.id === activeWs?.id || (ws.status === 'active' && !activeWorkspaceId);
                const wsName = ws.name || 'default';
                const branchName = ws.git_branch || (ws.name === 'default' ? (baseBranch || 'main') : `dev/${ws.name}`);

                return (
                  <div
                    key={ws.id}
                    onClick={() => {
                      if (!isActive && !isSwitching) {
                        setIsOpen(false);
                        onSelectWorkspace(ws.id);
                      }
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '7px 10px',
                      borderRadius: 6,
                      border: isActive ? '1px solid #e2e8f0' : '1px solid transparent',
                      background: isActive ? '#f8fafc' : 'transparent',
                      cursor: isActive ? 'default' : 'pointer',
                      transition: 'all 0.12s ease',
                      gap: 8,
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = '#f9fafb';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        minWidth: 0,
                        flex: 1,
                      }}
                    >
                      <FolderGit2
                        size={14}
                        style={{
                          color: isActive ? '#1B6EF3' : '#6b7280',
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          fontSize: '0.82rem',
                          fontWeight: isActive ? 600 : 500,
                          color: isActive ? '#0f172a' : '#374151',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {wsName}
                      </span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          color: '#64748b',
                          background: '#f1f5f9',
                          padding: '1px 6px',
                          borderRadius: 4,
                          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                          flexShrink: 0,
                        }}
                      >
                        {branchName}
                      </span>
                    </div>

                    {/* Right active indicator */}
                    {isActive && (
                      <Check
                        size={14}
                        style={{
                          color: '#1B6EF3',
                          flexShrink: 0,
                        }}
                      />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
