import React, { useState, useRef, useEffect } from 'react';
import {
  ChevronDown,
  FolderGit2,
  Folder,
  FolderPlus,
  Loader2,
  GitBranch,
  GitMerge,
} from 'lucide-react';
import { useToast } from '@/lib/toast';
import { useSyncWorkspaceWithMain, type DevWorkspace } from '../hooks/useApps';

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
  const toast = useToast();
  const syncMutation = useSyncWorkspaceWithMain();
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

  const handleSyncWithMain = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!activeWs?.id || syncMutation.isPending) return;

    try {
      const res = await syncMutation.mutateAsync({
        appId,
        workspaceId: activeWs.id,
        baseBranch: baseBranch || 'main',
      });

      if (res.already_up_to_date) {
        toast.info(res.message || `Sandbox "${activeName}" is already up to date with remote ${baseBranch || 'main'}.`);
      } else if (res.conflict) {
        toast.error(
          res.message || `Merge conflict in: ${(res.conflicting_files || []).join(', ')}. Please resolve in editor.`
        );
      } else if (res.success) {
        toast.success(
          res.message || `Successfully merged latest commits from remote ${baseBranch || 'main'} into "${activeName}".`
        );
      } else {
        toast.error(res.error || res.message || 'Failed to sync with remote main.');
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Sync failed.');
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* ── Header Trigger Pill (Clean Light Theme) ── */}
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
          border: isOpen ? '1px solid #1B6EF3' : '1px solid #e2e8f0',
          background: isOpen ? '#f8fafc' : '#ffffff',
          color: '#0f172a',
          cursor: disabled || isSwitching ? 'not-allowed' : 'pointer',
          transition: 'all 0.15s ease',
          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
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
          <Loader2 size={12} className="spin" style={{ color: '#1B6EF3' }} />
        ) : (
          <FolderGit2 size={13} style={{ color: '#1B6EF3' }} />
        )}

        <span style={{ color: '#64748b', fontWeight: 500 }}>Sandbox:</span>
        <span
          style={{
            color: '#0f172a',
            fontWeight: 600,
            maxWidth: 220,
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
            borderRadius: 4,
            background: '#f1f5f9',
            color: '#475569',
            border: '1px solid #e2e8f0',
            fontSize: '0.67rem',
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            maxWidth: 160,
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
            color: '#64748b',
            transform: isOpen ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.15s ease',
            marginLeft: 2,
          }}
        />
      </button>

      {/* ── Dropdown Menu (Exact Match to User Reference Screenshot) ── */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 1000,
            width: 'max-content',
            minWidth: 420,
            maxWidth: 640,
            background: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: 10,
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04)',
            overflow: 'hidden',
            animation: 'fadeIn 0.12s ease-out',
            padding: '6px',
          }}
        >
          {/* Section Header: Recents */}
          <div
            style={{
              padding: '4px 8px 6px',
              fontSize: '0.74rem',
              fontWeight: 500,
              color: '#6b7280',
              userSelect: 'none',
            }}
          >
            Recents
          </div>

          {/* Sandboxes List */}
          <div style={{ maxHeight: 280, overflowY: 'auto', overflowX: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
            {workspaces.length === 0 ? (
              <div style={{ padding: '12px 8px', textAlign: 'center', color: '#9ca3af', fontSize: '0.75rem' }}>
                No feature sandboxes yet.
              </div>
            ) : (
              workspaces.map((ws) => {
                const isActive = ws.id === activeWs?.id;
                const pathDisplay = ws.folder_path
                  ? (ws.folder_path.startsWith('/workspaces') ? ws.folder_path : `/workspaces/${ws.folder_path}`)
                  : `/workspaces/${appId}/${ws.name}`;

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
                      padding: '6px 8px',
                      borderRadius: 6,
                      border: isActive ? '1.5px solid #111827' : '1.5px solid transparent',
                      background: isActive ? '#f3f4f6' : 'transparent',
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
                        overflowX: 'auto',
                      }}
                    >
                      <FolderGit2
                        size={14}
                        style={{
                          color: isActive ? '#111827' : '#6b7280',
                          flexShrink: 0,
                        }}
                      />
                      <span
                        title={pathDisplay}
                        style={{
                          fontSize: '0.77rem',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          fontWeight: isActive ? 600 : 400,
                          color: isActive ? '#111827' : '#374151',
                          whiteSpace: 'nowrap',
                          userSelect: 'text',
                        }}
                      >
                        {pathDisplay}
                      </span>
                    </div>

                    {/* Right active indicator / folder icon */}
                    <Folder
                      size={13}
                      style={{
                        color: isActive ? '#111827' : '#9ca3af',
                        flexShrink: 0,
                        opacity: isActive ? 1 : 0.4,
                      }}
                    />
                  </div>
                );
              })
            )}
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: '#f3f4f6', margin: '4px 0' }} />

          {/* Action Row: Sync active sandbox with remote main */}
          <div
            onClick={handleSyncWithMain}
            title={`Fetch and merge remote origin/${baseBranch || 'main'} into active sandbox '${activeName}'`}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 8px',
              borderRadius: 6,
              cursor: syncMutation.isPending ? 'not-allowed' : 'pointer',
              color: '#111827',
              fontSize: '0.78rem',
              fontWeight: 500,
              transition: 'background 0.12s ease',
              opacity: syncMutation.isPending ? 0.75 : 1,
            }}
            onMouseEnter={(e) => {
              if (!syncMutation.isPending) e.currentTarget.style.background = '#f9fafb';
            }}
            onMouseLeave={(e) => {
              if (!syncMutation.isPending) e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {syncMutation.isPending ? (
                <Loader2 size={14} className="spin" style={{ color: '#1B6EF3' }} />
              ) : (
                <GitMerge size={14} style={{ color: '#1B6EF3' }} />
              )}
              <span>
                {syncMutation.isPending
                  ? `Merging origin/${baseBranch || 'main'} into ${activeName}...`
                  : `Sync active sandbox with remote ${baseBranch || 'main'}`}
              </span>
            </div>
            <span
              style={{
                fontSize: '0.67rem',
                color: '#64748b',
                background: '#f1f5f9',
                padding: '1px 6px',
                borderRadius: 4,
                fontFamily: 'ui-monospace, SFMono-Regular, monospace',
              }}
            >
              merge origin/{baseBranch || 'main'}
            </span>
          </div>

          {/* Action Row: Open / New Sandbox */}
          <div
            onClick={() => {
              setIsOpen(false);
              onOpenNewSandboxModal();
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 8px',
              borderRadius: 6,
              cursor: 'pointer',
              color: '#111827',
              fontSize: '0.78rem',
              fontWeight: 500,
              transition: 'background 0.12s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f9fafb';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <FolderPlus size={14} style={{ color: '#4b5563' }} />
            <span>Open new sandbox</span>
          </div>
        </div>
      )}
    </div>
  );
}
