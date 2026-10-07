import React, { memo, useCallback, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  FileArchive,
  Image as ImageIcon,
  Database,
  Lock,
  Settings,
  GitBranch,
  Boxes,
  KeyRound,
  BookOpen,
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

// VS Code Seti Theme Python Icon (Crisp vector interlocking snakes)
function PythonIcon({ className = 'size-3.5 shrink-0' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M7.92 1C5.6 1 4.75 1.95 4.75 3.12v1.28h3.2v.45H3.5C2.18 4.85 1 5.75 1 7.22c0 1.62.97 2.45 2.27 2.45h1.16v-1.4c0-1.42 1.25-2.67 2.67-2.67h3.19c1.17 0 2.14-.97 2.14-2.14V2.14C12.43 1.02 11.23 1 7.92 1zm-1.83 1.02a.65.65 0 1 1 0 1.3.65.65 0 0 1 0-1.3z"
        fill="#519aba"
      />
      <path
        d="M8.08 15c2.32 0 3.17-.95 3.17-2.12v-1.28h-3.2v-.45h4.45c1.32 0 2.5-.9 2.5-2.37 0-1.62-.97-2.45-2.27-2.45h-1.16v1.4c0 1.42-1.25 2.67-2.67 2.67H5.7c-1.17 0-2.14.97-2.14 2.14v1.32C3.57 14.98 4.77 15 8.08 15zm1.83-1.02a.65.65 0 1 1 0-1.3.65.65 0 0 1 0 1.3z"
        fill="#519aba"
      />
    </svg>
  );
}

// VS Code Seti Theme 3-Line Document Icon (for backup, temp, log, and text files)
function LinesDocumentIcon({ className = 'size-3.5 shrink-0' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="3.5" width="12" height="1.4" rx="0.4" fill="#94a3b8" />
      <rect x="2" y="7.3" width="12" height="1.4" rx="0.4" fill="#94a3b8" />
      <rect x="2" y="11.1" width="8" height="1.4" rx="0.4" fill="#94a3b8" />
    </svg>
  );
}

function ReactIcon({ className = 'size-3.5 shrink-0' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="12" cy="12" rx="10" ry="4.2" stroke="#519aba" strokeWidth="1.6" />
      <ellipse cx="12" cy="12" rx="10" ry="4.2" stroke="#519aba" strokeWidth="1.6" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4.2" stroke="#519aba" strokeWidth="1.6" transform="rotate(120 12 12)" />
      <circle cx="12" cy="12" r="2" fill="#519aba" />
    </svg>
  );
}

export function getFileIcon(name: string) {
  const lower = name.toLowerCase();

  // 1. Exact special file names
  if (lower === '.gitignore' || lower === '.gitattributes' || lower === '.gitmodules') {
    return <GitBranch className="size-3.5 text-[#f34f29] shrink-0" strokeWidth={1.75} />;
  }

  if (lower.startsWith('.env')) {
    return <KeyRound className="size-3.5 text-[#eab308] shrink-0" strokeWidth={1.75} />;
  }

  if (
    lower === 'dockerfile' ||
    lower.startsWith('dockerfile.') ||
    lower === '.dockerignore' ||
    lower.startsWith('docker-compose')
  ) {
    return <Boxes className="size-3.5 text-[#0db7ed] shrink-0" strokeWidth={1.75} />;
  }

  if (
    lower === 'package-lock.json' ||
    lower === 'pnpm-lock.yaml' ||
    lower === 'yarn.lock' ||
    lower === 'poetry.lock' ||
    lower === 'gemfile.lock'
  ) {
    return <Lock className="size-3.5 text-[#64748b] shrink-0" strokeWidth={1.75} />;
  }

  if (
    lower.includes('.config.') ||
    lower === 'tsconfig.json' ||
    lower === 'jsconfig.json' ||
    lower === '.eslintrc' ||
    lower === '.prettierrc' ||
    lower.startsWith('.eslintrc.') ||
    lower.startsWith('.prettierrc.')
  ) {
    return <Settings className="size-3.5 text-[#6366f1] shrink-0" strokeWidth={1.75} />;
  }

  if (lower === 'package.json') {
    return (
      <span className="font-mono text-[9px] font-bold text-[#cb3837] leading-none shrink-0 w-3.5 text-center select-none">
        JS
      </span>
    );
  }

  if (lower === 'requirements.txt' || lower === 'pyproject.toml' || lower === 'pipfile' || lower === 'setup.py') {
    return <PythonIcon className="size-3.5 shrink-0" />;
  }

  if (lower.startsWith('readme') || lower === 'license' || lower.startsWith('changelog')) {
    return <BookOpen className="size-3.5 text-[#519aba] shrink-0" strokeWidth={1.75} />;
  }

  // 2. Backup, swap, temp, and multi-dot backup files (matches VS Code Seti ≡ document icon)
  if (
    lower.endsWith('.bak') ||
    lower.includes('.bak.') ||
    lower.includes('.presteer') ||
    lower.includes('.prephase') ||
    lower.endsWith('.old') ||
    lower.endsWith('.orig') ||
    lower.endsWith('.tmp') ||
    lower.endsWith('.swp') ||
    lower.endsWith('~')
  ) {
    return <LinesDocumentIcon className="size-3.5 shrink-0" />;
  }

  // 3. Shell scripts: VS Code Seti bold green $
  if (
    lower.endsWith('.sh') ||
    lower.endsWith('.bash') ||
    lower.endsWith('.zsh') ||
    lower.endsWith('.fish') ||
    lower.endsWith('.ksh') ||
    lower.endsWith('.csh') ||
    lower.endsWith('.ps1') ||
    lower.endsWith('.cmd') ||
    lower.endsWith('.bat') ||
    lower.startsWith('.bashrc') ||
    lower.startsWith('.zshrc')
  ) {
    return (
      <span className="font-mono text-[13px] font-bold text-[#22c55e] leading-none shrink-0 w-3.5 text-center select-none">
        $
      </span>
    );
  }

  // 4. Extension-based matching
  const ext = fileExtension(lower);

  if (ext === 'tsx') {
    return <ReactIcon className="size-3.5 shrink-0" />;
  }

  if (ext === 'ts') {
    return (
      <span className="font-mono text-[9px] font-bold text-[#519aba] leading-none shrink-0 w-3.5 text-center select-none">
        TS
      </span>
    );
  }

  if (ext === 'jsx') {
    return <ReactIcon className="size-3.5 shrink-0" />;
  }

  if (['js', 'mjs', 'cjs'].includes(ext)) {
    return (
      <span className="font-mono text-[9px] font-bold text-[#cbcb41] leading-none shrink-0 w-3.5 text-center select-none">
        JS
      </span>
    );
  }

  if (['py', 'pyw', 'pyc', 'pyd', 'ipynb'].includes(ext)) {
    return <PythonIcon className="size-3.5 shrink-0" />;
  }

  if (['html', 'htm'].includes(ext)) {
    return (
      <span className="font-mono text-[10px] font-bold text-[#e34c26] leading-none shrink-0 w-3.5 text-center select-none">
        &lt;&gt;
      </span>
    );
  }

  if (ext === 'css') {
    return (
      <span className="font-mono text-[11px] font-bold text-[#563d7c] leading-none shrink-0 w-3.5 text-center select-none">
        #
      </span>
    );
  }

  if (['scss', 'sass', 'less'].includes(ext)) {
    return (
      <span className="font-mono text-[11px] font-bold text-[#c6538c] leading-none shrink-0 w-3.5 text-center select-none">
        #
      </span>
    );
  }

  if (ext === 'json') {
    return (
      <span className="font-mono text-[11px] font-bold text-[#cbcb41] leading-none shrink-0 w-3.5 text-center select-none">
        &#123;&#125;
      </span>
    );
  }

  if (['yaml', 'yml'].includes(ext)) {
    return (
      <span className="font-mono text-[8.5px] font-bold text-[#cb171e] leading-none shrink-0 w-3.5 text-center select-none">
        YML
      </span>
    );
  }

  if (['md', 'mdx', 'markdown'].includes(ext)) {
    return (
      <span className="font-mono text-[9px] font-bold text-[#519aba] leading-none shrink-0 w-3.5 text-center select-none">
        M↓
      </span>
    );
  }

  if (['sql', 'sqlite', 'db', 'duckdb', 'prisma'].includes(ext)) {
    return <Database className="size-3.5 text-[#e38c00] shrink-0" strokeWidth={1.75} />;
  }

  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'ico', 'bmp', 'svg'].includes(ext)) {
    return <ImageIcon className="size-3.5 text-[#a074c4] shrink-0" strokeWidth={1.75} />;
  }

  if (['csv', 'tsv', 'xlsx', 'xls'].includes(ext)) {
    return <FileSpreadsheet className="size-3.5 text-[#207245] shrink-0" strokeWidth={1.75} />;
  }

  if (['zip', 'tar', 'gz', 'tgz', '7z', 'rar'].includes(ext)) {
    return <FileArchive className="size-3.5 text-[#cc3e44] shrink-0" strokeWidth={1.75} />;
  }

  if (['txt', 'log'].includes(ext)) {
    return <LinesDocumentIcon className="size-3.5 shrink-0" />;
  }

  return <LinesDocumentIcon className="size-3.5 shrink-0" />;
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
          {node.file.git_status && (
            <span
              style={{
                fontSize: '0.66rem',
                fontWeight: 700,
                fontFamily: 'monospace',
                padding: '0 4px',
                borderRadius: 3,
                marginLeft: 4,
                flexShrink: 0,
                background:
                  node.file.git_status === 'modified'
                    ? '#fef3c7'
                    : node.file.git_status === 'untracked'
                    ? '#dcfce7'
                    : node.file.git_status === 'added'
                    ? '#e0f2fe'
                    : '#f1f5f9',
                color:
                  node.file.git_status === 'modified'
                    ? '#d97706'
                    : node.file.git_status === 'untracked'
                    ? '#16a34a'
                    : node.file.git_status === 'added'
                    ? '#0284c7'
                    : '#64748b',
              }}
              title={`Git status: ${node.file.git_status}`}
            >
              {node.file.git_status === 'modified'
                ? 'M'
                : node.file.git_status === 'untracked'
                ? 'U'
                : node.file.git_status === 'added'
                ? 'A'
                : node.file.git_status.slice(0, 1).toUpperCase()}
            </span>
          )}
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
