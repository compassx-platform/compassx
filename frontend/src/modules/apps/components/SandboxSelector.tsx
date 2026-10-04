import React, { useState, useRef, useEffect } from 'react';
import {
  Layers,
  ChevronDown,
  Plus,
  Check,
  GitBranch,
  Loader2,
  FolderGit2,
} from 'lucide-react';
import type { DevWorkspace } from '../hooks/useApps';

export interface SandboxSelectorProps {
  appId: string;
  workspaces: DevWorkspace[];
  activeWorkspaceId?: string;
  onSelectWorkspace: (workspaceId: string) => void;
  onOpenNewSandboxModal: () => void;
  isSwitching?: boolean;
  disabled?: boolean;
}

export function SandboxSelector({
  workspaces,
  activeWorkspaceId,
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
      {/* ── Header Trigger Pill ── */}
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
          borderRadius: 8,
          fontSize: '0.74rem',
          fontWeight: 600,
          border: isOpen
            ? '1px solid rgba(99, 102, 241, 0.5)'
            : '1px solid rgba(255, 255, 255, 0.12)',
          background: isOpen
            ? 'rgba(99, 102, 241, 0.18)'
            : 'rgba(30, 41, 59, 0.7)',
          color: '#f8fafc',
          cursor: disabled || isSwitching ? 'not-allowed' : 'pointer',
          transition: 'all 0.15s ease',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
        }}
        onMouseEnter={(e) => {
          if (!disabled && !isSwitching) {
            e.currentTarget.style.background = 'rgba(99, 102, 241, 0.16)';
            e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.4)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = 'rgba(30, 41, 59, 0.7)';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.12)';
          }
        }}
      >
        {isSwitching ? (
          <Loader2 size={12} className="spin" style={{ color: '#818cf8' }} />
        ) : (
          <FolderGit2 size={13} style={{ color: '#818cf8' }} />
        )}

        <span style={{ color: '#94a3b8', fontWeight: 500 }}>Sandbox:</span>
        <span
          style={{
            color: '#ffffff',
            maxWidth: 130,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {activeName}
        </span>

        {/* Branch Tag */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            padding: '1px 6px',
            borderRadius: 6,
            background: 'rgba(99, 102, 241, 0.2)',
            color: '#a5b4fc',
            fontSize: '0.67rem',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            maxWidth: 110,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          <GitBranch size={9} />
          {activeBranch}
        </span>

        <ChevronDown
          size={12}
          style={{
            color: '#94a3b8',
            transform: isOpen ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.15s ease',
            marginLeft: 2,
          }}
        />
      </button>

      {/* ── Dropdown Menu ── */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 1000,
            width: 290,
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 10,
            boxShadow: '0 12px 30px -4px rgba(0, 0, 0, 0.5), 0 4px 10px -2px rgba(0, 0, 0, 0.3)',
            overflow: 'hidden',
            animation: 'fadeIn 0.12s ease-out',
          }}
        >
          {/* Dropdown Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              borderBottom: '1px solid #1e293b',
              background: '#090d16',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Layers size={13} style={{ color: '#818cf8' }} />
              <span style={{ fontSize: '0.74rem', fontWeight: 650, color: '#f1f5f9', letterSpacing: '0.02em' }}>
                Feature Sandboxes
              </span>
              <span
                style={{
                  fontSize: '0.66rem',
                  padding: '1px 5px',
                  borderRadius: 10,
                  background: '#1e293b',
                  color: '#94a3b8',
                }}
              >
                {workspaces.length}
              </span>
            </div>

            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenNewSandboxModal();
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                padding: '2px 7px',
                borderRadius: 5,
                border: 'none',
                background: 'linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)',
                color: '#ffffff',
                fontSize: '0.68rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
              title="Create a new isolated feature sandbox"
            >
              <Plus size={11} />
              <span>New</span>
            </button>
          </div>

          {/* Sandboxes List */}
          <div style={{ maxHeight: 240, overflowY: 'auto', padding: '4px' }}>
            {workspaces.length === 0 ? (
              <div style={{ padding: '16px 12px', textAlign: 'center', color: '#64748b', fontSize: '0.74rem' }}>
                No feature sandboxes yet.
              </div>
            ) : (
              workspaces.map((ws) => {
                const isActive = ws.id === activeWs?.id;
                const branchName = ws.git_branch || `dev/${ws.name}`;

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
                      background: isActive ? 'rgba(99, 102, 241, 0.16)' : 'transparent',
                      cursor: isActive ? 'default' : 'pointer',
                      transition: 'background 0.12s ease',
                      marginBottom: 2,
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span
                          style={{
                            fontSize: '0.78rem',
                            fontWeight: isActive ? 650 : 500,
                            color: isActive ? '#818cf8' : '#e2e8f0',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {ws.name}
                        </span>
                        {isActive && (
                          <span
                            style={{
                              fontSize: '0.62rem',
                              fontWeight: 700,
                              color: '#22c55e',
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}
                          >
                            ● ACTIVE
                          </span>
                        )}
                      </div>

                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                          fontSize: '0.68rem',
                          color: '#64748b',
                          marginTop: 2,
                          fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                        }}
                      >
                        <GitBranch size={10} style={{ flexShrink: 0 }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {branchName}
                        </span>
                      </div>
                    </div>

                    {/* Active Checkmark */}
                    {isActive && (
                      <div
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: '50%',
                          background: 'rgba(34, 197, 94, 0.18)',
                          color: '#22c55e',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          marginLeft: 8,
                        }}
                      >
                        <Check size={11} strokeWidth={2.8} />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Dropdown Footer */}
          <div
            style={{
              padding: '6px 10px',
              borderTop: '1px solid #1e293b',
              background: '#090d16',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: '0.66rem', color: '#64748b' }}>
              Instant Git worktree switching
            </span>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenNewSandboxModal();
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#818cf8',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                padding: '2px 4px',
              }}
            >
              + Create Sandbox
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
