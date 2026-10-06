import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowDownAZ,
  ArrowDownUp,
  ArrowDownWideNarrow,
  ChevronsDownUp,
  ChevronsUpDown,
  Clock,
  Eye,
  EyeOff,
  File,
  FileType,
  Loader2,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkspaceFile } from '../../hooks/useApps';
import { FolderTree, getFileIcon, type ChangedSort } from './FolderTree';
import { CopyPathButton } from './CopyPathButton';
import { formatBytes } from './fileStatusUtils';

const SORT_OPTIONS: { value: ChangedSort; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: 'alpha', label: 'Filename', icon: ArrowDownAZ },
  { value: 'recent', label: 'Last edited', icon: Clock },
  { value: 'size', label: 'Size', icon: ArrowDownWideNarrow },
  { value: 'type', label: 'Type', icon: FileType },
];

interface SortSelectorProps {
  sort: ChangedSort;
  onChange: (next: ChangedSort) => void;
}

function SortSelector({ sort, onChange }: SortSelectorProps) {
  const [open, setOpen] = useState(false);
  const active = SORT_OPTIONS.find((o) => o.value === sort) ?? SORT_OPTIONS[0];

  return (
    <div className="relative shrink-0 flex items-center">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={`Sort: ${active.label}`}
        title={`Sort files (${active.label})`}
        className="inline-flex items-center gap-1 text-[12px] font-mono text-neutral-700 hover:text-neutral-900 transition-colors cursor-pointer px-1 py-1 rounded hover:bg-neutral-100"
      >
        <span className="text-neutral-600 font-mono text-[12px] select-none">Sort:</span>
        <ArrowDownAZ className="size-3.5 text-neutral-700" strokeWidth={1.75} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded border border-neutral-200 bg-white p-1 shadow-lg font-mono">
            <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
              Sort Files
            </div>
            {SORT_OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  onChange(value);
                  setOpen(false);
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[11px] transition-colors',
                  sort === value
                    ? 'bg-neutral-100 text-neutral-950 font-semibold'
                    : 'text-neutral-700 hover:bg-neutral-50'
                )}
              >
                <Icon className="size-3.5 shrink-0 text-neutral-500" />
                <span className="flex-1">{label}</span>
                {sort === value && <span className="text-neutral-900 text-xs">✓</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

interface HiddenFilesToggleProps {
  showHidden: boolean;
  onToggle: () => void;
  hiddenCount: number;
}

function HiddenFilesToggle({ showHidden, onToggle, hiddenCount }: HiddenFilesToggleProps) {
  const hasHidden = hiddenCount > 0 && !showHidden;
  const label = showHidden
    ? 'Hide hidden files'
    : hasHidden
    ? `${hiddenCount} file${hiddenCount === 1 ? '' : 's'} in hidden directories. Click to show.`
    : 'Show hidden files';

  return (
    <button
      type="button"
      onClick={onToggle}
      title={label}
      aria-label={label}
      className={cn(
        'inline-flex size-7 items-center justify-center rounded transition-colors shrink-0',
        hasHidden
          ? 'text-amber-600 hover:bg-neutral-100 hover:text-amber-700'
          : showHidden
          ? 'bg-neutral-200 text-neutral-900'
          : 'text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800'
      )}
    >
      {showHidden ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
    </button>
  );
}

export interface FilesPanelProps {
  files?: WorkspaceFile[];
  isLoading?: boolean;
  onRefresh?: () => void;
  onFileSelect: (path: string) => void;
  selectedPath?: string | null;
  onClose?: () => void;
  workspaceName?: string;
  workspacePath?: string;
  cleanExplorerMode?: boolean;
  externalSearchQuery?: string;
  showHidden?: boolean;
  onToggleHidden?: () => void;
}

export function FilesPanel({
  files = [],
  isLoading = false,
  onFileSelect,
  selectedPath,
  workspaceName,
  workspacePath,
  cleanExplorerMode = false,
  externalSearchQuery,
  showHidden: controlledShowHidden,
  onToggleHidden: controlledToggleHidden,
}: FilesPanelProps) {
  const [internalSearchQuery, setInternalSearchQuery] = useState('');
  const searchQuery = externalSearchQuery !== undefined ? externalSearchQuery : internalSearchQuery;
  const setSearchQuery = setInternalSearchQuery;
  const [internalShowHidden, setInternalShowHidden] = useState(true);
  const showHidden = controlledShowHidden !== undefined ? controlledShowHidden : internalShowHidden;
  const setShowHidden = controlledToggleHidden
    ? () => controlledToggleHidden()
    : (val: boolean | ((prev: boolean) => boolean)) => {
        if (typeof val === 'function') {
          setInternalShowHidden(val);
        } else {
          setInternalShowHidden(val);
        }
      };
  const [sort, setSort] = useState<ChangedSort>('alpha');
  // Collapsed by default — empty Set
  const [openPaths, setOpenPaths] = useState<Set<string>>(() => new Set<string>());

  const folderName = workspaceName || 'app';
  const folderPath = workspacePath || `/workspaces/${folderName}`;

  const hiddenCount = useMemo(() => {
    return files.filter((f) => {
      const clean = (f.path || '').replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
      const parts = clean.split('/').filter(Boolean);
      return parts.some((p) => p.startsWith('.'));
    }).length;
  }, [files]);

  const visibleFiles = useMemo(() => {
    if (showHidden) return files;
    return files.filter((f) => {
      const clean = (f.path || '').replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
      const parts = clean.split('/').filter(Boolean);
      return !parts.some((p) => p.startsWith('.'));
    });
  }, [files, showHidden]);

  // Collect all unique directory paths for Expand All
  const allDirPaths = useMemo(() => {
    const dirs = new Set<string>();
    for (const file of visibleFiles) {
      const clean = (file.path || '').replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
      const parts = clean.split('/').filter(Boolean);
      let current = '';
      for (let i = 0; i < parts.length - 1; i++) {
        current = current ? `${current}/${parts[i]}` : parts[i];
        dirs.add(current);
      }
    }
    return dirs;
  }, [visibleFiles]);

  // Auto-expand top-level directories on initial load
  useEffect(() => {
    if (openPaths.size === 0 && visibleFiles.length > 0) {
      const topDirs = new Set<string>();
      for (const file of visibleFiles) {
        const clean = (file.path || '').replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
        const parts = clean.split('/').filter(Boolean);
        if (parts.length > 1) {
          topDirs.add(parts[0]);
        }
      }
      if (topDirs.size > 0) {
        setOpenPaths(topDirs);
      }
    }
  }, [visibleFiles, openPaths.size]);

  const handleTogglePath = useCallback((path: string) => {
    setOpenPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleExpandAll = useCallback(() => {
    setOpenPaths(new Set(allDirPaths));
  }, [allDirPaths]);

  const handleCollapseAll = useCallback(() => {
    setOpenPaths(new Set());
  }, []);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase().trim();
    return visibleFiles.filter((f) => f.path.toLowerCase().includes(q));
  }, [visibleFiles, searchQuery]);

  return (
    <div className="flex h-full w-full min-h-0 flex-col overflow-hidden bg-white text-neutral-800 font-sans">
      {!cleanExplorerMode && (
        <>
          {/* Row 2: Working folder bar */}
          <div className="flex h-9.5 shrink-0 items-center justify-between px-3.5 border-b border-neutral-100 bg-white">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="font-semibold text-[13px] text-neutral-900 shrink-0">Working folder</span>
              <span
                className="font-mono text-[12px] text-indigo-600/90 truncate cursor-pointer hover:underline"
                title={folderPath}
              >
                {folderPath}
              </span>
            </div>

            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={handleExpandAll}
                className="inline-flex size-7 items-center justify-center rounded text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
                title="Expand all folders"
                aria-label="Expand all folders"
              >
                <ChevronsUpDown className="size-3.5 text-neutral-600" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={handleCollapseAll}
                className="inline-flex size-7 items-center justify-center rounded text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
                title="Collapse all folders"
                aria-label="Collapse all folders"
              >
                <ChevronsDownUp className="size-3.5 text-neutral-600" strokeWidth={1.5} />
              </button>
              <CopyPathButton path={folderPath} label="Copy working folder path" />
              <HiddenFilesToggle
                showHidden={showHidden}
                onToggle={() => setShowHidden(!showHidden)}
                hiddenCount={hiddenCount}
              />
            </div>
          </div>

          {/* Row 3: Search & Sort bar */}
          <div className="shrink-0 px-3.5 py-2.5 border-b border-neutral-100 bg-white" onClick={(e) => e.stopPropagation()}>
            <div className="flex min-w-0 flex-1 items-center gap-2.5">
              {/* Pill Search Input */}
              <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full border border-neutral-200 bg-white px-3.5 py-1.5 shadow-2xs focus-within:border-neutral-500">
                <Search className="size-3.5 text-neutral-400 shrink-0" strokeWidth={1.75} />
                <input
                  aria-label="Search"
                  className="min-w-0 flex-1 bg-transparent font-mono text-[12.5px] leading-tight text-neutral-900 outline-none placeholder:text-neutral-400"
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search"
                  type="search"
                  value={searchQuery}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="cursor-pointer text-neutral-400 hover:text-neutral-700"
                    title="Clear search"
                  >
                    <X className="size-3" />
                  </button>
                )}
              </div>

              {/* Filter Sliders Button */}
              <button
                type="button"
                title="Filter files"
                aria-label="Filter files"
                className="inline-flex size-7 items-center justify-center rounded text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-colors shrink-0"
              >
                <SlidersHorizontal className="size-3.5" strokeWidth={1.5} />
              </button>

              {/* Sort: selector button */}
              <SortSelector sort={sort} onChange={setSort} />
            </div>
          </div>
        </>
      )}

      {/* Row 4: File Tree / Search Results Body */}
      <section className="min-h-0 flex-1 overflow-y-auto px-1 pb-3 pt-1 bg-white [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-neutral-300 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
        {isLoading && files.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-neutral-400">
            <Loader2 className="size-5 animate-spin text-neutral-500" />
            <span className="text-xs font-mono">Loading workspace files...</span>
          </div>
        ) : searchQuery.trim() ? (
          /* Search Results */
          <div>
            <div className="px-3.5 py-1 text-[11px] text-neutral-400 font-mono">
              {searchResults.length} {searchResults.length === 1 ? 'result' : 'results'} for "{searchQuery}"
            </div>
            {searchResults.length === 0 ? (
              <div className="px-3.5 py-8 text-center text-xs text-neutral-400 font-mono">
                No files found matching "{searchQuery}"
              </div>
            ) : (
              <div className="flex flex-col gap-0.5">
                {searchResults.map((file) => {
                  const isSelected = selectedPath === file.path;
                  const bytes = file.bytes ?? file.size ?? null;
                  const parts = file.path.split('/');
                  const fileName = parts.pop() ?? file.path;
                  const dirPrefix = parts.length > 0 ? parts.join('/') + '/' : '';

                  return (
                    <div
                      key={file.path}
                      className={cn(
                        'group flex w-full min-w-0 items-center gap-1.5 py-[3px] pr-2 transition-colors cursor-pointer select-none',
                        isSelected
                          ? 'bg-[#e0f2fe] text-neutral-900'
                          : 'hover:bg-neutral-50 text-neutral-700'
                      )}
                      style={{ paddingLeft: '12px' }}
                      onClick={() => onFileSelect(file.path)}
                    >
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left outline-none"
                        onClick={(e) => {
                          e.stopPropagation();
                          onFileSelect(file.path);
                        }}
                      >
                        {getFileIcon(fileName)}
                        <span className="min-w-0 flex-1 truncate text-[12px] leading-normal font-sans" title={file.path}>
                          {dirPrefix && (
                            <span className="text-neutral-400 text-xs mr-0.5">{dirPrefix}</span>
                          )}
                          <span className={isSelected ? 'text-neutral-900 font-normal' : 'text-neutral-800'}>
                            {fileName}
                          </span>
                        </span>
                      </button>

                      {/* Right Meta Column: show file size only on hover, alongside hover Copy button */}
                      <div className="flex shrink-0 items-center justify-end gap-1.5">
                        {bytes !== null && (
                          <span className="text-[11px] font-mono text-neutral-400 tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                            {formatBytes(bytes)}
                          </span>
                        )}
                        <CopyPathButton path={file.path} revealOnHover />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : files.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-neutral-400">
            <span className="text-xs font-mono">No files found in workspace root.</span>
          </div>
        ) : (
          <FolderTree
            files={visibleFiles}
            onFileSelect={onFileSelect}
            selectedPath={selectedPath}
            showHidden={showHidden}
            sort={sort}
            openPaths={openPaths}
            onTogglePath={handleTogglePath}
          />
        )}
      </section>
    </div>
  );
}
