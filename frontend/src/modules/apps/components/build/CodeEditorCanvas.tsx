import React, { useState, useEffect } from 'react';
import {
  X,
  ChevronLeft,
  ChevronRight,
  FolderTree,
  RotateCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkspaceFile } from '../../hooks/useApps';
import { FilesPanel } from '../files/FilesPanel';
import { FileViewer } from '../files/FileViewer';

interface CodeEditorCanvasProps {
  appId: string;
  appName?: string;
  workspaceId?: string;
  workspaceName?: string;
  files: WorkspaceFile[];
  isLoading?: boolean;
  onRefresh?: () => void;
  selectedFilePath: string | null;
  onSelectFilePath: (path: string | null) => void;
}

export function CodeEditorCanvas({
  appId,
  appName = 'app',
  workspaceId,
  workspaceName,
  files = [],
  isLoading = false,
  onRefresh,
  selectedFilePath,
  onSelectFilePath,
}: CodeEditorCanvasProps) {
  // Track open file tabs
  const [openFiles, setOpenFiles] = useState<string[]>(() => {
    const initial: string[] = [];
    if (files.some((f) => f.path.endsWith('.mcp.json'))) initial.push('.mcp.json');
    if (files.some((f) => f.path.endsWith('database.db'))) initial.push('database.db');
    if (files.some((f) => f.path.endsWith('package.json'))) initial.push('package.json');
    return initial;
  });

  const [isExplorerCollapsed, setIsExplorerCollapsed] = useState<boolean>(false);
  const [explorerWidth] = useState<number>(230);

  // Auto-open first prominent file or first available file if no files are open yet
  useEffect(() => {
    if (files.length > 0 && openFiles.length === 0 && !selectedFilePath) {
      const preferred =
        files.find((f) => f.name === 'package.json') ||
        files.find((f) => f.name === 'index.html') ||
        files.find((f) => f.name === 'mcp.json' || f.name === '.mcp.json') ||
        files.find((f) => f.name.endsWith('.py') && !f.name.startsWith('.')) ||
        files.find((f) => !f.name.startsWith('.'));
      if (preferred) {
        setOpenFiles([preferred.path]);
        onSelectFilePath(preferred.path);
      }
    }
  }, [files, openFiles.length, selectedFilePath, onSelectFilePath]);

  // When selectedFilePath changes, add to openFiles if not present
  useEffect(() => {
    if (selectedFilePath && !openFiles.includes(selectedFilePath)) {
      setOpenFiles((prev) => [...prev, selectedFilePath]);
    }
  }, [selectedFilePath]);

  const handleCloseTab = (path: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    const next = openFiles.filter((p) => p !== path);
    setOpenFiles(next);
    if (selectedFilePath === path) {
      onSelectFilePath(next.length > 0 ? next[next.length - 1] : null);
    }
  };

  const handleFileSelect = (path: string) => {
    if (!openFiles.includes(path)) {
      setOpenFiles((prev) => [...prev, path]);
    }
    onSelectFilePath(path);
  };

  const cleanAppId = appId.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/^-+|-+$/g, '');
  const activeSandboxName = (workspaceName || workspaceId || 'default').toLowerCase().replace(/[^a-zA-Z0-9_-]/g, '-').replace(/^-+|-+$/g, '');
  const workingFolderPath = `/workspaces/${cleanAppId}/${activeSandboxName}`;

  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        width: '100%',
        display: 'flex',
        background: '#ffffff',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* ── Sub-Pane 1: Left Explorer Pane ── */}
      {!isExplorerCollapsed ? (
        <div
          style={{
            width: `${explorerWidth}px`,
            minWidth: 180,
            maxWidth: 380,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            borderRight: '1px solid #e2e8f0',
            background: '#ffffff',
            flexShrink: 0,
            overflow: 'hidden',
          }}
        >
          {/* Explorer Header */}
          <div className="flex h-8 items-center justify-between px-3 border-b border-neutral-200 bg-white select-none shrink-0">
            <span className="text-[11px] font-semibold tracking-wider text-neutral-500 uppercase">
              Explorer
            </span>
            <div className="flex items-center gap-1.5 text-neutral-500">
              {onRefresh && (
                <button
                  type="button"
                  onClick={onRefresh}
                  disabled={isLoading}
                  title="Refresh files"
                  className="p-1 rounded text-neutral-400 hover:text-neutral-700 transition-colors cursor-pointer disabled:opacity-50"
                >
                  <RotateCw size={13} className={isLoading ? 'animate-spin' : ''} />
                </button>
              )}
              <button
                type="button"
                onClick={() => setIsExplorerCollapsed(true)}
                title="Collapse Explorer"
                className="p-1 rounded text-neutral-400 hover:text-neutral-700 transition-colors cursor-pointer"
              >
                <ChevronLeft size={14} />
              </button>
            </div>
          </div>

          {/* Files Tree */}
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
            <FilesPanel
              files={files}
              isLoading={isLoading}
              onRefresh={onRefresh}
              onFileSelect={handleFileSelect}
              selectedPath={selectedFilePath}
              workspaceName={activeSandboxName}
              workspacePath={workingFolderPath}
              cleanExplorerMode={true}
              showHidden={true}
            />
          </div>
        </div>
      ) : (
        /* Collapsed Explorer Rail */
        <div
          style={{
            width: 32,
            height: '100%',
            borderRight: '1px solid #e2e8f0',
            background: '#ffffff',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 8,
            gap: 6,
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            onClick={() => setIsExplorerCollapsed(false)}
            title="Expand Explorer"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 4,
            }}
          >
            <ChevronRight size={14} />
          </button>
          <FolderTree size={14} color="#94a3b8" />
        </div>
      )}

      {/* ── Sub-Pane 2: Right Editor Pane with Tabs ── */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          background: '#ffffff',
          overflow: 'hidden',
        }}
      >
        {/* Open Files Tabs Strip */}
        <div className="flex items-stretch h-8 border-b border-neutral-200 bg-[#f9fafb] overflow-x-auto shrink-0 select-none [&::-webkit-scrollbar]:hidden">
          {openFiles.map((path) => {
            const name = path.split('/').filter(Boolean).pop() ?? path;
            const isActive = selectedFilePath === path;

            return (
              <div
                key={path}
                onClick={() => onSelectFilePath(path)}
                className={cn(
                  'group flex items-center gap-2 h-full px-3 cursor-pointer text-[12px] font-sans transition-colors shrink-0 border-r border-neutral-200',
                  isActive
                    ? 'bg-white text-neutral-800 font-normal -mb-[1px] border-b border-b-white z-10'
                    : 'bg-[#fafafa] text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100/60'
                )}
                title={path}
              >
                <span className="max-w-[160px] truncate">
                  {name}
                </span>
                <button
                  type="button"
                  onClick={(e) => handleCloseTab(path, e)}
                  className="rounded p-0.5 text-neutral-400 hover:bg-neutral-200/70 hover:text-neutral-800 transition-colors cursor-pointer"
                  title={`Close ${name}`}
                >
                  <X size={11} />
                </button>
              </div>
            );
          })}
        </div>

        {/* Editor Body */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          {selectedFilePath ? (
            <FileViewer
              appId={appId}
              path={selectedFilePath}
              workspaceId={workspaceId}
              onClose={() => onSelectFilePath(null)}
              hideHeader={true}
            />
          ) : (
            <div
              style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#94a3b8',
                fontSize: '0.82rem',
                gap: 8,
              }}
            >
              <FolderTree size={28} color="#cbd5e1" />
              <span>Select a file from the explorer on the left to view and edit.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
