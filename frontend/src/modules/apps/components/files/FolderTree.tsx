import React, { memo, useCallback, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, File } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkspaceFile } from '../../hooks/useApps';
import { CopyPathButton } from './CopyPathButton';
import { formatBytes } from './fileStatusUtils';

export type ChangedSort = 'alpha' | 'recent' | 'size' | 'type';

// Indentation parameters: BASE_PAD = 14px matches px-3.5 of the top rows
const INDENT_STEP = 16;
const BASE_PAD = 14;
const GUIDE_OFFSET = 7;
const indentFor = (depth: number) => depth * INDENT_STEP + BASE_PAD;

function IndentGuides({ depth }: { depth: number }) {
  if (depth <= 0) return null;
  return (
    <>
      {Array.from({ length: depth }, (_, level) => indentFor(level) + GUIDE_OFFSET).map((left) => (
        <span
          key={left}
          aria-hidden
          className="pointer-events-none absolute top-0 bottom-0 w-px bg-neutral-200"
          style={{ left: `${left}px` }}
        />
      ))}
    </>
  );
}

export interface FileNode {
  type: 'file';
  name: string;
  file: WorkspaceFile;
}

export interface DirNode {
  type: 'dir';
  name: string;
  path: string;
  children: TreeNode[];
  modifiedAt?: number | null;
}

export type TreeNode = FileNode | DirNode;

function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
}

function compareTreeNodes(sort: ChangedSort) {
  return (a: TreeNode, b: TreeNode): number => {
    // Directories always grouped ahead of files
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;

    if (sort === 'recent') {
      const aTime = a.type === 'file' ? (a.file.modified_at ?? 0) : (a.modifiedAt ?? 0);
      const bTime = b.type === 'file' ? (b.file.modified_at ?? 0) : (b.modifiedAt ?? 0);
      if (aTime !== bTime) return bTime - aTime;
    } else if (sort === 'size') {
      const aSize = a.type === 'file' ? (a.file.bytes ?? a.file.size ?? 0) : 0;
      const bSize = b.type === 'file' ? (b.file.bytes ?? b.file.size ?? 0) : 0;
      if (aSize !== bSize) return bSize - aSize;
    } else if (sort === 'type') {
      if (a.type === 'file' && b.type === 'file') {
        const ae = fileExtension(a.name);
        const be = fileExtension(b.name);
        if (ae !== be) return ae.localeCompare(be);
      }
    }
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  };
}

export function buildTree(files: WorkspaceFile[], sort: ChangedSort = 'alpha'): TreeNode[] {
  const root: DirNode = { type: 'dir', name: '', path: '', children: [] };

  for (const file of files) {
    const parts = file.path.replace(/\\/g, '/').split('/');
    let node = root;

    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      let dir = node.children.find((c): c is DirNode => c.type === 'dir' && c.name === part);
      if (!dir) {
        dir = { type: 'dir', name: part, path: parts.slice(0, i + 1).join('/'), children: [] };
        node.children.push(dir);
      }
      node = dir;
    }
    node.children.push({ type: 'file', name: parts[parts.length - 1], file });
  }

  const compare = compareTreeNodes(sort);
  function sortTree(node: DirNode) {
    node.children.sort(compare);
    for (const child of node.children) {
      if (child.type === 'dir') sortTree(child);
    }
  }
  sortTree(root);

  return root.children;
}

interface TreeItemProps {
  node: TreeNode;
  depth: number;
  openPaths: Set<string>;
  onTogglePath: (path: string) => void;
  onFileSelect: (path: string) => void;
  selectedPath?: string | null;
  showHidden: boolean;
  onSelectFolder?: (path: string) => void;
}

const TreeItem = memo(function TreeItem({
  node,
  depth,
  openPaths,
  onTogglePath,
  onFileSelect,
  selectedPath,
  showHidden,
  onSelectFolder,
}: TreeItemProps) {
  if (!showHidden && node.name.startsWith('.')) {
    return null;
  }

  if (node.type === 'file') {
    const isSelected = selectedPath === node.file.path;
    const bytes = node.file.bytes ?? node.file.size ?? null;

    return (
      <li className="list-none">
        <div
          className={cn(
            'group relative flex w-full min-w-0 items-center gap-1.5 py-[2px] pr-3.5 transition-colors cursor-pointer select-none rounded-[2px]',
            isSelected
              ? 'border border-neutral-900 bg-white'
              : 'border border-transparent hover:bg-neutral-100/70'
          )}
          style={{ paddingLeft: `${indentFor(depth)}px` }}
          onClick={() => onFileSelect(node.file.path)}
        >
          <IndentGuides depth={depth} />

          <button
            type="button"
            className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left outline-none"
            onClick={(e) => {
              e.stopPropagation();
              onFileSelect(node.file.path);
            }}
          >
            {/* Outline Document Icon matching user's image */}
            <File className="size-3.5 text-neutral-600 shrink-0" strokeWidth={1.5} />
            <span
              className={cn(
                'min-w-0 flex-1 truncate font-mono text-[12px] leading-5',
                isSelected ? 'text-neutral-950 font-semibold' : 'text-neutral-800'
              )}
              title={node.file.path}
            >
              {node.name}
            </span>
          </button>

          {/* Right Meta Column: show file size only on hover, alongside hover Copy button */}
          <div className="flex shrink-0 items-center justify-end gap-1.5">
            {bytes !== null && (
              <span className="text-[11px] font-mono text-neutral-400 tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                {formatBytes(bytes)}
              </span>
            )}
            <CopyPathButton path={node.file.path} revealOnHover />
          </div>
        </div>
      </li>
    );
  }

  const isOpen = openPaths.has(node.path);
  const isSelected = selectedPath === node.path;

  return (
    <li className="list-none">
      <div
        className={cn(
          'group relative flex w-full min-w-0 items-center gap-1.5 py-[2px] pr-3.5 transition-colors cursor-pointer select-none rounded-[2px]',
          isSelected
            ? 'border border-neutral-900 bg-white'
            : 'border border-transparent hover:bg-neutral-100/70'
        )}
        style={{ paddingLeft: `${indentFor(depth)}px` }}
        onClick={() => {
          onTogglePath(node.path);
          onSelectFolder?.(node.path);
        }}
      >
        <IndentGuides depth={depth} />

        <button
          type="button"
          className="group/folder flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left outline-none"
          onClick={(e) => {
            e.stopPropagation();
            onTogglePath(node.path);
            onSelectFolder?.(node.path);
          }}
          aria-expanded={isOpen}
        >
          {/* Chevron only — no folder icon matching user's image */}
          {isOpen ? (
            <ChevronDown className="size-3.5 text-neutral-600 shrink-0" strokeWidth={1.5} />
          ) : (
            <ChevronRight className="size-3.5 text-neutral-600 shrink-0" strokeWidth={1.5} />
          )}
          <span
            className={cn(
              'min-w-0 flex-1 truncate font-mono text-[12px] leading-5',
              isSelected ? 'text-neutral-950 font-semibold' : 'text-neutral-800'
            )}
          >
            {node.name}/
          </span>
        </button>

        <div className="flex shrink-0 items-center justify-end">
          <CopyPathButton path={node.path} label="Copy folder path" revealOnHover />
        </div>
      </div>

      {isOpen && (
        <ul className="m-0 p-0">
          {node.children.map((child) => (
            <TreeItem
              key={child.type === 'dir' ? child.path : child.file.path}
              node={child}
              depth={depth + 1}
              openPaths={openPaths}
              onTogglePath={onTogglePath}
              onFileSelect={onFileSelect}
              selectedPath={selectedPath}
              showHidden={showHidden}
              onSelectFolder={onSelectFolder}
            />
          ))}
        </ul>
      )}
    </li>
  );
});

export interface FolderTreeProps {
  files: WorkspaceFile[];
  onFileSelect: (path: string) => void;
  selectedPath?: string | null;
  showHidden?: boolean;
  sort?: ChangedSort;
  openPaths?: Set<string>;
  onTogglePath?: (path: string) => void;
}

export function FolderTree({
  files,
  onFileSelect,
  selectedPath,
  showHidden = false,
  sort = 'alpha',
  openPaths: controlledOpenPaths,
  onTogglePath: controlledTogglePath,
}: FolderTreeProps) {
  // Collapsed by default — empty Set
  const [internalOpenPaths, setInternalOpenPaths] = useState<Set<string>>(() => new Set<string>());

  const openPaths = controlledOpenPaths ?? internalOpenPaths;

  const [selectedFolderPath, setSelectedFolderPath] = useState<string | null>(null);

  const tree = useMemo(() => {
    return buildTree(files, sort);
  }, [files, sort]);

  const togglePath = useCallback(
    (path: string) => {
      if (controlledTogglePath) {
        controlledTogglePath(path);
      } else {
        setInternalOpenPaths((prev) => {
          const next = new Set(prev);
          if (next.has(path)) {
            next.delete(path);
          } else {
            next.add(path);
          }
          return next;
        });
      }
    },
    [controlledTogglePath]
  );

  const activeSelected = selectedPath ?? selectedFolderPath;

  return (
    <ul className="flex flex-col select-none font-mono text-neutral-800 m-0 p-0 bg-white">
      {tree.map((node) => (
        <TreeItem
          key={node.type === 'dir' ? node.path : node.file.path}
          node={node}
          depth={0}
          openPaths={openPaths}
          onTogglePath={togglePath}
          onFileSelect={onFileSelect}
          selectedPath={activeSelected}
          showHidden={showHidden}
          onSelectFolder={setSelectedFolderPath}
        />
      ))}
    </ul>
  );
}
