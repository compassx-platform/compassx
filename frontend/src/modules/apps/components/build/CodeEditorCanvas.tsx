import React, { useState, useEffect, useMemo } from 'react';
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
import { getFileIcon } from '../files/FolderTree';

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
  const [openFiles, setOpenFiles] = useState<string[]>([]);
  const [openPath, setOpenPath] = useState<string | null>(selectedFilePath);

  const [isExplorerCollapsed, setIsExplorerCollapsed] = useState<boolean>(false);
  const [explorerWidth] = useState<number>(230);

  const fallbackPath = useMemo(() => {
    const preferred =
      files.find((file) => file.name === 'README.md') ||
      files.find((file) => file.name === 'index.html') ||
      files.find((file) => file.name.endsWith('.py') && !file.name.startsWith('.')) ||
      files.find((file) => !file.name.startsWith('.') && !file.path.includes('/'));
    return preferred?.path ?? null;
  }, [files]);
  const knownPaths = useMemo(() => new Set(files.map((file) => file.path)), [files]);
  // Show a real file on the first paint. Waiting for an effect left a tab over an empty editor.
  const activePath = openPath && knownPaths.has(openPath) ? openPath : fallbackPath;
  const tabs = activePath && !openFiles.includes(activePath) ? [activePath, ...openFiles] : openFiles;

  const chooseFile = (path: string | null) => {
    setOpenPath(path);
    if (path && !openFiles.includes(path)) setOpenFiles((current) => [...current, path]);
    if (path !== selectedFilePath) onSelectFilePath(path);
  };

  useEffect(() => {
    if (selectedFilePath && knownPaths.has(selectedFilePath)) setOpenPath(selectedFilePath);
  }, [selectedFilePath, knownPaths]);

  const handleCloseTab = (path: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    const next = openFiles.filter((p) => p !== path);
    setOpenFiles(next);
    const nextPath = selectedFilePath === path || openPath === path
      ? (next.length > 0 ? next[next.length - 1] : null)
      : openPath;
    if (selectedFilePath === path || openPath === path) chooseFile(nextPath);
  };

  const handleFileSelect = (path: string) => {
    if (!openFiles.includes(path)) {
      setOpenFiles((prev) => [...prev, path]);
    }
    chooseFile(path);
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
              selectedPath={activePath}
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
        <div className="flex items-stretch h-8 border-b border-neutral-200 bg-[#f9fafb] overflow-x-auto shrink-0 select-none [&::-webkit-scrollbar]:h-1 [&::-webkit-scrollbar-thumb]:bg-neutral-300 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
          {tabs.map((path) => {
            const name = path.split('/').filter(Boolean).pop() ?? path;
            const isActive = activePath === path;
            const gitStatus = files.find((file) => file.path === path)?.git_status;
            const gitMark =
              gitStatus === 'modified' ? 'M'
              : gitStatus === 'untracked' ? 'U'
              : gitStatus === 'added' ? 'A'
              : gitStatus === 'deleted' ? 'D'
              : '';

            return (
              <div
                key={path}
                onClick={() => chooseFile(path)}
                className={cn(
                  'group flex items-center gap-1.5 h-full px-3 cursor-pointer text-[12px] font-sans transition-colors shrink-0 border-r border-neutral-200',
                  isActive
                    ? 'bg-white text-neutral-900 font-normal -mb-[1px] border-b border-b-white z-10'
                    : 'bg-[#fafafa] text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100/60'
                )}
                title={path}
              >
                {getFileIcon(name)}
                <span className="whitespace-nowrap select-none">
                  {name}
                </span>
                {gitMark && (
                  <span className="font-mono text-[10px] font-semibold text-amber-700" title={gitStatus || undefined}>
                    {gitMark}
                  </span>
                )}
                <button
                  type="button"
                  onClick={(e) => handleCloseTab(path, e)}
                  className="rounded p-0.5 text-neutral-400 hover:bg-neutral-200/70 hover:text-neutral-800 transition-colors cursor-pointer ml-1"
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
          {activePath ? (
            <FileViewer
              appId={appId}
              path={activePath}
              workspaceId={workspaceId}
              onClose={() => chooseFile(null)}
              hideHeader={true}
              gitStatus={files.find((file) => file.path === activePath)?.git_status ?? null}
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
