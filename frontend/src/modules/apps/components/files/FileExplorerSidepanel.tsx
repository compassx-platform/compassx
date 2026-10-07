import React, { useEffect, useState } from 'react';
import {
  Maximize2,
  Minimize2,
  Plus,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkspaceFile } from '../../hooks/useApps';
import { FilesPanel } from './FilesPanel';
import { FileViewer } from './FileViewer';
import { getFileIcon } from './FolderTree';

export interface FileExplorerSidepanelProps {
  appId: string;
  appName?: string;
  workspaceId?: string;
  workspaceName?: string;
  files: WorkspaceFile[];
  isLoading?: boolean;
  onRefresh?: () => void;
  selectedFilePath: string | null;
  onSelectFilePath: (path: string | null) => void;
  onClose?: () => void;
  isMaximized?: boolean;
  onToggleMaximized?: () => void;
}

export function FileExplorerSidepanel({
  appId,
  appName = 'app',
  workspaceId,
  workspaceName,
  files = [],
  isLoading = false,
  onRefresh,
  selectedFilePath,
  onSelectFilePath,
  onClose,
  isMaximized = false,
  onToggleMaximized,
}: FileExplorerSidepanelProps) {
  // Track open file tabs (e.g. .mcp.json, database.db, etc.)
  const [openFiles, setOpenFiles] = useState<string[]>(() => {
    const initial: string[] = [];
    if (files.some((f) => f.path.endsWith('.mcp.json'))) initial.push('.mcp.json');
    if (files.some((f) => f.path.endsWith('database.db'))) initial.push('database.db');
    return initial;
  });

  // Whenever a new file is selected, ensure it's in the open tabs
  useEffect(() => {
    if (selectedFilePath && !openFiles.includes(selectedFilePath)) {
      setOpenFiles((prev) => [...prev, selectedFilePath]);
    }
  }, [selectedFilePath]);

  const handleCloseTab = (path: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setOpenFiles((prev) => prev.filter((p) => p !== path));
    if (selectedFilePath === path) {
      const remaining = openFiles.filter((p) => p !== path);
      onSelectFilePath(remaining.length > 0 ? remaining[remaining.length - 1] : null);
    }
  };

  // Construct working folder path like: /workspaces/app-512a55f7eb854d7c/gnmi
  const cleanAppId = appId.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/^-+|-+$/g, '');
  const activeSandboxName = (workspaceName || workspaceId || 'default').toLowerCase().replace(/[^a-zA-Z0-9_-]/g, '-').replace(/^-+|-+$/g, '');
  const workingFolderPath = `/workspaces/${cleanAppId}/${activeSandboxName}`;

  return (
    <div className="flex h-full w-full min-h-0 flex-col overflow-hidden bg-white text-neutral-800 font-mono">
      {/* Row 1: Top Tab Strip [open tabs: .mcp.json | database.db | +] ... [fullscreen] */}
      <div className="flex h-9.5 shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-3.5">
        {/* Left: Open File Tabs Strip */}
        <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto [scrollbar-width:none]">
          {openFiles.map((path) => {
            const name = path.split('/').pop() ?? path;
            const isActive = selectedFilePath === path;

            return (
              <div
                key={path}
                onClick={() => onSelectFilePath(path)}
                className={cn(
                  'group relative flex h-[26px] shrink-0 cursor-pointer items-center gap-1.5 rounded px-2.5 text-[12px] font-mono transition-colors select-none',
                  isActive
                    ? 'bg-neutral-100 text-neutral-950 border border-neutral-300 font-medium shadow-2xs'
                    : 'text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900 border border-transparent'
                )}
                title={path}
              >
                {getFileIcon(name)}
                <span className="whitespace-nowrap">{name}</span>
                <button
                  type="button"
                  onClick={(e) => handleCloseTab(path, e)}
                  className="ml-0.5 inline-flex size-4 items-center justify-center rounded text-neutral-400 opacity-60 hover:opacity-100 hover:bg-neutral-200 hover:text-neutral-800 transition-all"
                  title={`Close ${name}`}
                >
                  <X className="size-3" />
                </button>
              </div>
            );
          })}

          {/* "+" Button to browse tree / add file */}
          <button
            type="button"
            onClick={() => onSelectFilePath(null)}
            className="inline-flex size-6 items-center justify-center rounded text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800 transition-colors ml-0.5 shrink-0"
            title="Browse folder tree (+)"
          >
            <Plus className="size-3.5" />
          </button>
        </div>

        {/* Right: Maximize / Fullscreen toggle */}
        <div className="flex shrink-0 items-center gap-1 ml-2">
          {onToggleMaximized && (
            <button
              type="button"
              onClick={onToggleMaximized}
              className="inline-flex size-7 items-center justify-center rounded text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
              title={isMaximized ? 'Exit fullscreen' : 'Fullscreen'}
            >
              {isMaximized ? (
                <Minimize2 className="size-3.5" />
              ) : (
                <Maximize2 className="size-3.5" />
              )}
            </button>
          )}

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="inline-flex size-7 items-center justify-center rounded text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
              title="Close panel"
            >
              <X className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Body */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {selectedFilePath ? (
          <FileViewer
            appId={appId}
            path={selectedFilePath}
            workspaceId={workspaceId}
            onClose={() => onSelectFilePath(null)}
          />
        ) : (
          <FilesPanel
            files={files}
            isLoading={isLoading}
            onRefresh={onRefresh}
            onFileSelect={(path) => onSelectFilePath(path)}
            selectedPath={selectedFilePath}
            onClose={onClose}
            workspaceName={activeSandboxName}
            workspacePath={workingFolderPath}
          />
        )}
      </div>
    </div>
  );
}
