import React, { memo, useCallback, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Folder,
  File,
  FileCode,
  FileText,
  Image as ImageIcon,
  Braces,
  Hash,
  Code2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkspaceFile } from '../../hooks/useApps';
import { CopyPathButton } from './CopyPathButton';
import { formatBytes } from './fileStatusUtils';

export type ChangedSort = 'alpha' | 'recent' | 'size' | 'type';

// Indentation parameters: BASE_PAD = 10px matches clean explorer padding
const INDENT_STEP = 14;
const BASE_PAD = 8;
const GUIDE_OFFSET = 6;
const indentFor = (depth: number) => depth * INDENT_STEP + BASE_PAD;

export function getFileIcon(name: string) {
  const ext = fileExtension(name);
  if (['png', 'jpg', 'jpeg', 'svg', 'gif', 'webp', 'ico'].includes(ext)) {
    return <ImageIcon className="size-3.5 text-emerald-600/90 shrink-0" strokeWidth={1.5} />;
  }
  if (ext === 'json') {
    return (
      <span className="font-mono text-[10.5px] font-semibold text-sky-600/90 leading-none shrink-0 w-3.5 text-center">
        &#123;&#125;
      </span>
    );
  }
  if (['ts', 'tsx', 'js', 'jsx'].includes(ext)) {
    return <FileCode className="size-3.5 text-sky-600/90 shrink-0" strokeWidth={1.5} />;
  }
  if (['html', 'htm'].includes(ext)) {
    return <Code2 className="size-3.5 text-sky-600/90 shrink-0" strokeWidth={1.5} />;
  }
  if (['css', 'scss', 'less'].includes(ext)) {
    return <Hash className="size-3.5 text-slate-500 shrink-0" strokeWidth={1.5} />;
  }
  if (['md', 'markdown'].includes(ext)) {
    return (
      <span className="font-mono text-[9.5px] font-semibold text-slate-500 leading-none shrink-0 w-3.5 text-center">
        M↓
      </span>
    );
  }
  if (['yaml', 'yml'].includes(ext)) {
    return (
      <span className="font-mono text-[9.5px] font-semibold text-slate-500 leading-none shrink-0 w-3.5 text-center">
        [ ]
      </span>
    );
  }
  return <File className="size-3.5 text-neutral-400 shrink-0" strokeWidth={1.5} />;
}

function IndentGuides(_: { depth: number }) {
  return null;
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
    const cleanPath = (file.path || '').replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '');
    if (!cleanPath) continue;
    const parts = cleanPath.split('/').filter(Boolean);
    if (parts.length === 0) continue;
    let node = root;

    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      const dirPath = parts.slice(0, i + 1).join('/');
      let dir = node.children.find((c): c is DirNode => c.type === 'dir' && c.name === part);
      if (!dir) {
        dir = { type: 'dir', name: part, path: dirPath, children: [] };
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

    return (
      <li className="list-none">
        <div
          className={cn(
            'group flex w-full min-w-0 items-center gap-1.5 py-[3px] pr-2 transition-colors cursor-pointer select-none',
            isSelected
              ? 'bg-[#e0f2fe] text-neutral-900'
              : 'hover:bg-neutral-50 text-neutral-700'
          )}
          style={{ paddingLeft: `${depth * 16 + 24}px` }}
          onClick={() => onFileSelect(node.file.path)}
        >
          {getFileIcon(node.name)}
          <span
            className="min-w-0 flex-1 truncate text-[12.5px] leading-normal font-sans"
            title={node.file.path}
          >
            {node.name}
          </span>
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
          'group flex w-full min-w-0 items-center gap-1 py-[3px] pr-2 transition-colors cursor-pointer select-none',
          isSelected
            ? 'bg-[#e0f2fe] text-neutral-900'
            : 'hover:bg-neutral-50 text-neutral-700'
        )}
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        onClick={() => {
          onTogglePath(node.path);
          onSelectFolder?.(node.path);
        }}
      >
        {isOpen ? (
          <ChevronDown className="size-3 text-neutral-500 shrink-0" strokeWidth={1.75} />
        ) : (
          <ChevronRight className="size-3 text-neutral-500 shrink-0" strokeWidth={1.75} />
        )}
        <Folder className="size-3.5 text-[#d97706] fill-[#fef3c7] shrink-0" strokeWidth={1.5} />
        <span className="min-w-0 flex-1 truncate text-[12.5px] leading-normal font-sans">
          {node.name}
        </span>
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
  showHidden = true,
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
    <ul className="flex flex-col select-none text-neutral-800 m-0 py-1 px-0 bg-white">
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
