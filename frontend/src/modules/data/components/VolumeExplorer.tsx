import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import {
  Folder,
  FolderPlus,
  File,
  FileText,
  FileSpreadsheet,
  FileCode,
  FileCode2,
  Database,
  Image as ImageIcon,
  FileArchive,
  ChevronLeft,
  Search,
  Upload,
  Download,
  Trash2,
  Pencil,
  Copy,
  Check,
  RefreshCw,
  Eye,
  X,
  Star,
  Table as TableIcon,
  Layers,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Loader2,
} from 'lucide-react';
import api from '@/lib/api';
import { useToast } from '@/lib/toast';
import { OwnerName } from '@/modules/governance';
import { PageTabs } from '@/components/common/PageTabs';
import ConfirmDialog from '@/components/common/ConfirmDialog';

export interface CatalogVolume {
  id: string;
  schema_id: string;
  name: string;
  description?: string | null;
  storage_location?: string | null;
  owner: string;
  created_by: string;
  created_at: string;
  catalog?: string;
  schema_name?: string;
}

export interface VolumeFileInfo {
  file_path: string;
  file_name: string;
  size_bytes: number;
  content_type: string;
  last_modified: string;
  uploaded_by?: string;
}

export type VolumeNavigationTarget =
  | { kind: 'root' }
  | { kind: 'catalog'; catalog: string }
  | { kind: 'schema'; catalog: string; schema: string }
  | { kind: 'volume'; catalog: string; schema: string; volume: string };

export interface VolumeExplorerProps {
  volume: CatalogVolume;
  catalog: string;
  schema: string;
  canModify: boolean;
  canManage: boolean;
  onNavigate: (nav: VolumeNavigationTarget) => void;
  renderPermissionsTab: (selection: { kind: 'volume'; catalog: string; schema: string; volume: string }) => React.ReactNode;
  isFavorite?: boolean;
  onToggleFavorite?: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  if (i < 0) return '0 B';
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + (sizes[i] || 'B');
}

function formatDate(dateString: string): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
}

function getFileTypeInfo(filePath: string, isDir: boolean) {
  if (isDir) {
    return {
      icon: Folder,
      color: '#0284c7', // Sky blue
      bgColor: '#e0f2fe',
      label: 'Directory',
      badge: 'DIR',
      previewType: 'none' as const,
    };
  }

  const clean = filePath.toLowerCase().split('?')[0];
  const ext = clean.includes('.') ? clean.split('.').pop() || '' : '';

  switch (ext) {
    case 'csv':
    case 'tsv':
    case 'psv':
      return {
        icon: FileSpreadsheet,
        color: '#10b981', // Emerald
        bgColor: '#d1fae5',
        label: `${ext.toUpperCase()} file`,
        badge: ext.toUpperCase(),
        previewType: 'csv' as const,
      };
    case 'parquet':
    case 'orc':
    case 'avro':
    case 'delta':
      return {
        icon: Layers,
        color: '#06b6d4', // Cyan
        bgColor: '#cffafe',
        label: `${ext.toUpperCase()} dataset`,
        badge: ext.toUpperCase(),
        previewType: 'parquet' as const,
      };
    case 'json':
    case 'jsonl':
    case 'ndjson':
      return {
        icon: FileCode2,
        color: '#f59e0b', // Amber
        bgColor: '#fef3c7',
        label: 'JSON document',
        badge: 'JSON',
        previewType: 'json' as const,
      };
    case 'py':
    case 'ipynb':
      return {
        icon: FileCode,
        color: '#3b82f6', // Blue
        bgColor: '#dbeafe',
        label: ext === 'ipynb' ? 'Jupyter Notebook' : 'Python script',
        badge: ext.toUpperCase(),
        previewType: 'code' as const,
      };
    case 'sql':
      return {
        icon: Database,
        color: '#8b5cf6', // Violet
        bgColor: '#ede9fe',
        label: 'SQL query',
        badge: 'SQL',
        previewType: 'code' as const,
      };
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'svg':
    case 'gif':
    case 'webp':
    case 'bmp':
    case 'ico':
      return {
        icon: ImageIcon,
        color: '#6366f1', // Indigo
        bgColor: '#e0e7ff',
        label: `${ext.toUpperCase()} image`,
        badge: 'IMG',
        previewType: 'image' as const,
      };
    case 'md':
    case 'markdown':
    case 'txt':
    case 'log':
    case 'yaml':
    case 'yml':
    case 'xml':
    case 'html':
    case 'css':
    case 'js':
    case 'ts':
    case 'tsx':
    case 'jsx':
    case 'sh':
    case 'bash':
    case 'env':
    case 'conf':
    case 'ini':
      return {
        icon: FileText,
        color: '#64748b', // Slate
        bgColor: '#f1f5f9',
        label: `${ext.toUpperCase()} text`,
        badge: ext.toUpperCase(),
        previewType: 'code' as const,
      };
    case 'zip':
    case 'tar':
    case 'gz':
    case 'tgz':
    case '7z':
    case 'rar':
      return {
        icon: FileArchive,
        color: '#d97706', // Orange-amber
        bgColor: '#fef3c7',
        label: 'Archive file',
        badge: 'ZIP',
        previewType: 'binary' as const,
      };
    case 'pdf':
      return {
        icon: FileText,
        color: '#ef4444', // Red
        bgColor: '#fee2e2',
        label: 'PDF document',
        badge: 'PDF',
        previewType: 'binary' as const,
      };
    default:
      return {
        icon: File,
        color: '#94a3b8',
        bgColor: '#f8fafc',
        label: ext ? `${ext.toUpperCase()} file` : 'File',
        badge: ext ? ext.slice(0, 4).toUpperCase() : 'FILE',
        previewType: 'binary' as const,
      };
  }
}

// Simple CSV parser for preview table
function parseCsvPreview(text: string, maxRows = 50): { headers: string[]; rows: string[][] } {
  const lines = text.trim().split(/\r\n|\n/).filter(line => line.trim().length > 0);
  if (lines.length === 0) return { headers: [], rows: [] };

  const parseLine = (line: string): string[] => {
    const result: string[] = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if ((char === ',' || char === '\t') && !inQuotes) {
        result.push(cur);
        cur = '';
      } else {
        cur += char;
      }
    }
    result.push(cur);
    return result;
  };

  const headers = parseLine(lines[0]);
  const rows: string[][] = [];
  for (let i = 1; i < Math.min(lines.length, maxRows + 1); i++) {
    rows.push(parseLine(lines[i]));
  }
  return { headers, rows };
}

// ── Component ─────────────────────────────────────────────────────────────────

export const VolumeExplorer: React.FC<VolumeExplorerProps> = ({
  volume,
  catalog,
  schema,
  canModify,
  canManage,
  onNavigate,
  renderPermissionsTab,
  isFavorite = false,
  onToggleFavorite,
}) => {
  const toast = useToast();
  const queryClient = useQueryClient();

  // State
  const [currentPath, setCurrentPath] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'files' | 'details' | 'permissions'>('files');
  const [sortField, setSortField] = useState<'name' | 'size' | 'last_modified' | 'type'>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Preview drawer state
  const [previewFile, setPreviewFile] = useState<VolumeFileInfo | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [previewTab, setPreviewTab] = useState<'preview' | 'code_snippet' | 'raw'>('preview');

  // Modals state
  const [showCreateDirModal, setShowCreateDirModal] = useState(false);
  const [newDirName, setNewDirName] = useState('');
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [fileToRename, setFileToRename] = useState<VolumeFileInfo | null>(null);
  const [newName, setNewName] = useState('');
  const [fileToDelete, setFileToDelete] = useState<VolumeFileInfo | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [copiedFqn, setCopiedFqn] = useState<string | null>(null);
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fullVolumePath = `/Volumes/${catalog}/${schema}/${volume.name}`;
  const currentDirectoryDisplay = `${fullVolumePath}${currentPath ? '/' + currentPath.replace(/\/$/, '') : ''}`;

  // 1. Fetch Volume Files
  const volumeFilesQuery = useQuery({
    queryKey: ['uc-volume-files', volume.id],
    queryFn: () => api.get<VolumeFileInfo[]>(`/catalog/volumes/${volume.id}/files`).then(r => r.data),
    enabled: !!volume.id,
  });

  // 2. Mutations
  const uploadMutation = useMutation({
    mutationFn: async ({ file, subPath }: { file: File; subPath: string }) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.post<VolumeFileInfo>(`/catalog/volumes/${volume.id}/files`, formData, {
        params: { sub_path: subPath },
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then(r => r.data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files', volume.id] });
      toast.success(`Uploaded "${data.file_name}"`);
    },
    onError: (err: unknown) => {
      const msg = axios.isAxiosError(err) ? (err.response?.data as { detail?: string })?.detail : undefined;
      toast.error(msg || 'Failed to upload file');
    },
  });

  const createDirectoryMutation = useMutation({
    mutationFn: async ({ dirName, subPath }: { dirName: string; subPath: string }) => {
      return api.post<VolumeFileInfo>(`/catalog/volumes/${volume.id}/directories`, { dir_name: dirName }, {
        params: { sub_path: subPath },
      }).then(r => r.data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files', volume.id] });
      setShowCreateDirModal(false);
      setNewDirName('');
      toast.success(`Created directory "${data.file_name}"`);
    },
    onError: (err: unknown) => {
      const msg = axios.isAxiosError(err) ? (err.response?.data as { detail?: string })?.detail : undefined;
      toast.error(msg || 'Failed to create directory');
    },
  });

  const renameMutation = useMutation({
    mutationFn: async ({ oldPath, newName }: { oldPath: string; newName: string }) => {
      return api.post<VolumeFileInfo>(`/catalog/volumes/${volume.id}/files/rename`, {
        old_path: oldPath,
        new_name: newName,
      }).then(r => r.data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files', volume.id] });
      setShowRenameModal(false);
      setFileToRename(null);
      setNewName('');
      if (previewFile && previewFile.file_path === fileToRename?.file_path) {
        setPreviewFile(data);
      }
      toast.success('Item renamed successfully');
    },
    onError: (err: unknown) => {
      const msg = axios.isAxiosError(err) ? (err.response?.data as { detail?: string })?.detail : undefined;
      toast.error(msg || 'Failed to rename item');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (filePath: string) => {
      return api.delete(`/catalog/volumes/${volume.id}/files`, {
        params: { file_path: filePath },
      });
    },
    onSuccess: (_, filePath) => {
      queryClient.invalidateQueries({ queryKey: ['uc-volume-files', volume.id] });
      if (previewFile?.file_path === filePath) {
        setPreviewFile(null);
      }
      setFileToDelete(null);
      toast.success('Deleted successfully');
    },
    onError: (err: unknown) => {
      const msg = axios.isAxiosError(err) ? (err.response?.data as { detail?: string })?.detail : undefined;
      toast.error(msg || 'Failed to delete item');
    },
  });

  // Direct download helper
  const handleDownload = async (file: VolumeFileInfo) => {
    try {
      const res = await api.get(`/catalog/volumes/${volume.id}/files/download`, {
        params: { file_path: file.file_path },
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', file.file_name.replace(/\/$/, ''));
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded ${file.file_name}`);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) ? (err.response?.data as { detail?: string })?.detail : undefined;
      toast.error(msg || 'Download failed');
    }
  };

  // Preview content fetcher
  useEffect(() => {
    let activeImageUrl: string | null = null;

    if (!previewFile) {
      setPreviewContent(null);
      setPreviewImageUrl(null);
      return;
    }

    const isDir = previewFile.file_path.endsWith('/') || previewFile.content_type === 'application/x-directory';
    if (isDir) return;

    const info = getFileTypeInfo(previewFile.file_path, false);
    if (info.previewType === 'image') {
      setPreviewLoading(true);
      api.get(`/catalog/volumes/${volume.id}/files/download`, {
        params: { file_path: previewFile.file_path },
        responseType: 'blob',
      })
        .then(res => {
          const url = URL.createObjectURL(new Blob([res.data]));
          activeImageUrl = url;
          setPreviewImageUrl(url);
        })
        .catch(() => toast.error('Failed to load image preview'))
        .finally(() => setPreviewLoading(false));
    } else if (info.previewType === 'csv' || info.previewType === 'json' || info.previewType === 'code') {
      setPreviewLoading(true);
      api.get(`/catalog/volumes/${volume.id}/files/download`, {
        params: { file_path: previewFile.file_path },
        responseType: 'text',
      })
        .then(res => {
          setPreviewContent(typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2));
        })
        .catch(() => {
          setPreviewContent('Unable to preview content for this file.');
        })
        .finally(() => setPreviewLoading(false));
    } else {
      setPreviewContent(null);
    }

    return () => {
      if (activeImageUrl) {
        URL.revokeObjectURL(activeImageUrl);
      }
    };
  }, [previewFile, volume.id, toast]);

  // Aggregate and filter current directory items
  const currentLevelItems = useMemo(() => {
    const rawFiles = volumeFilesQuery.data || [];
    const itemsMap = new Map<string, VolumeFileInfo>();

    rawFiles.forEach((file) => {
      if (!file.file_path.startsWith(currentPath)) return;

      const relative = file.file_path.substring(currentPath.length);
      if (relative === '' || relative === '.keep') return;

      const parts = relative.split('/');

      if (parts.length > 1 || (parts.length === 1 && file.file_path.endsWith('/'))) {
        const dirName = parts[0];
        const dirPath = currentPath + dirName + '/';
        if (!itemsMap.has(dirPath)) {
          itemsMap.set(dirPath, {
            file_path: dirPath,
            file_name: dirName + '/',
            size_bytes: 0,
            content_type: 'application/x-directory',
            last_modified: file.last_modified,
            uploaded_by: file.uploaded_by,
          });
        }
      } else {
        itemsMap.set(file.file_path, file);
      }
    });

    return Array.from(itemsMap.values());
  }, [volumeFilesQuery.data, currentPath]);

  // Filter and sort items
  const displayItems = useMemo(() => {
    let list = currentLevelItems;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((f) => f.file_name.toLowerCase().includes(q));
    }

    return [...list].sort((a, b) => {
      const aIsDir = a.file_path.endsWith('/') || a.content_type === 'application/x-directory';
      const bIsDir = b.file_path.endsWith('/') || b.content_type === 'application/x-directory';

      // Always keep folders first
      if (aIsDir && !bIsDir) return -1;
      if (!aIsDir && bIsDir) return 1;

      let comparison = 0;
      if (sortField === 'name') {
        comparison = a.file_name.localeCompare(b.file_name);
      } else if (sortField === 'size') {
        comparison = a.size_bytes - b.size_bytes;
      } else if (sortField === 'last_modified') {
        comparison = new Date(a.last_modified).getTime() - new Date(b.last_modified).getTime();
      } else if (sortField === 'type') {
        const typeA = getFileTypeInfo(a.file_path, aIsDir).label;
        const typeB = getFileTypeInfo(b.file_path, bIsDir).label;
        comparison = typeA.localeCompare(typeB);
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [currentLevelItems, searchQuery, sortField, sortOrder]);

  const stats = useMemo(() => {
    let foldersCount = 0;
    let filesCount = 0;
    let totalSize = 0;
    currentLevelItems.forEach(item => {
      if (item.file_path.endsWith('/') || item.content_type === 'application/x-directory') {
        foldersCount++;
      } else {
        filesCount++;
        totalSize += item.size_bytes;
      }
    });
    return { foldersCount, filesCount, totalSize, totalItems: currentLevelItems.length };
  }, [currentLevelItems]);

  // Handle Drag and drop upload
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (canModify) setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
    if (!canModify) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    files.forEach(file => {
      uploadMutation.mutate({ file, subPath: currentPath });
    });
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    files.forEach(file => {
      uploadMutation.mutate({ file, subPath: currentPath });
    });
    e.target.value = '';
  };

  const handleSort = (field: 'name' | 'size' | 'last_modified' | 'type') => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const handleCopyText = (text: string, type: 'path' | 'fqn') => {
    navigator.clipboard.writeText(text);
    if (type === 'fqn') {
      setCopiedFqn(text);
      setTimeout(() => setCopiedFqn(null), 2000);
    } else {
      setCopiedPath(text);
      setTimeout(() => setCopiedPath(null), 2000);
    }
    toast.success(`Copied ${type === 'path' ? 'volume path' : 'FQN'} to clipboard`);
  };

  const pathParts = currentPath.split('/').filter(Boolean);

  const tabs = [
    { value: 'files', label: 'Files' },
    { value: 'details', label: 'Details' },
    { value: 'permissions', label: 'Permissions' },
  ] as const;

  return (
    <div className="dbx-volume-explorer-container uc-panel">
      {/* ── 1. Databricks Header ───────────────────────────────────────────── */}
      <div className="dbx-volume-header">
        {/* Breadcrumb row */}
        <div className="dbx-header-breadcrumbs">
          <button
            type="button"
            className="dbx-breadcrumb-item"
            onClick={() => onNavigate({ kind: 'root' })}
          >
            Catalog Explorer
          </button>
          <span className="dbx-breadcrumb-sep">&gt;</span>
          <button
            type="button"
            className="dbx-breadcrumb-item"
            onClick={() => onNavigate({ kind: 'catalog', catalog })}
          >
            {catalog}
          </button>
          <span className="dbx-breadcrumb-sep">&gt;</span>
          <button
            type="button"
            className="dbx-breadcrumb-item"
            onClick={() => onNavigate({ kind: 'schema', catalog, schema })}
          >
            {schema}
          </button>
          <span className="dbx-breadcrumb-sep">&gt;</span>
          <span className="dbx-breadcrumb-current">{volume.name}</span>
        </div>

        {/* Title and Top Actions Bar */}
        <div className="dbx-header-title-row">
          <div className="dbx-header-title-group">
            <div className="dbx-volume-icon-badge">
              <Folder size={20} className="text-primary" />
            </div>
            <h1 className="dbx-volume-title">{volume.name}</h1>
            <span className="dbx-volume-tag">MANAGED VOLUME</span>

            {/* Copy FQN / Path */}
            <button
              type="button"
              className="uc-icon-btn"
              onClick={() => handleCopyText(`${catalog}.${schema}.${volume.name}`, 'fqn')}
              title="Copy Full Name"
            >
              {copiedFqn ? <Check size={14} style={{ color: 'var(--color-success, #10b981)' }} /> : <Copy size={14} />}
            </button>

            {/* Favorite Star */}
            {onToggleFavorite && (
              <button
                type="button"
                className="uc-icon-btn"
                onClick={onToggleFavorite}
                title="Toggle Favorite"
              >
                <Star
                  size={14}
                  fill={isFavorite ? '#eab308' : 'none'}
                  stroke={isFavorite ? '#eab308' : 'currentColor'}
                />
              </button>
            )}
          </div>

          {/* Quick Actions in Header */}
          <div className="dbx-header-actions">
            {canModify && (
              <>
                <button
                  type="button"
                  className="btn-primary flex items-center gap-1.5"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadMutation.isPending}
                >
                  {uploadMutation.isPending ? (
                    <Loader2 size={14} className="spin" />
                  ) : (
                    <Upload size={14} />
                  )}
                  Upload to this volume
                </button>

                <button
                  type="button"
                  className="btn-secondary flex items-center gap-1.5"
                  onClick={() => {
                    setNewDirName('');
                    setShowCreateDirModal(true);
                  }}
                  disabled={createDirectoryMutation.isPending}
                >
                  <FolderPlus size={14} />
                  Create directory
                </button>
              </>
            )}

            <button
              type="button"
              className="btn-secondary flex items-center gap-1.5"
              onClick={() => volumeFilesQuery.refetch()}
              title="Refresh files"
            >
              <RefreshCw size={14} className={volumeFilesQuery.isFetching ? 'spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileInputChange}
      />

      {/* ── 2. Navigation Tabs (Files | Details | Permissions) ───────────────── */}
      <PageTabs tabs={tabs} value={activeTab} onChange={setActiveTab} />

      {/* ── 3. Files Tab (Databricks File Explorer) ─────────────────────────── */}
      {activeTab === 'files' && (
        <div className="dbx-volume-body-layout">
          {/* Main Table Card Area */}
          <div
            className={`dbx-volume-card ${isDraggingOver ? 'dbx-drag-active' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {/* Databricks Path / Breadcrumb Bar */}
            <div className="dbx-path-navigation-bar">
              <div className="dbx-path-crumbs-group">
                {/* Back / Up button */}
                <button
                  type="button"
                  className="dbx-path-up-btn"
                  disabled={!currentPath}
                  onClick={() => {
                    if (!currentPath) return;
                    const parts = currentPath.split('/').filter(Boolean);
                    parts.pop();
                    setCurrentPath(parts.length ? parts.join('/') + '/' : '');
                    setSearchQuery('');
                  }}
                  title={currentPath ? 'Go up one directory level' : 'Root directory'}
                >
                  <ChevronLeft size={16} />
                </button>

                {/* Breadcrumbs */}
                <div className="dbx-path-crumbs">
                  <span className="dbx-path-prefix">/Volumes</span>
                  <span className="dbx-path-slash">/</span>
                  <span
                    className="dbx-path-segment"
                    onClick={() => onNavigate({ kind: 'catalog', catalog })}
                  >
                    {catalog}
                  </span>
                  <span className="dbx-path-slash">/</span>
                  <span
                    className="dbx-path-segment"
                    onClick={() => onNavigate({ kind: 'schema', catalog, schema })}
                  >
                    {schema}
                  </span>
                  <span className="dbx-path-slash">/</span>
                  <span
                    className={`dbx-path-segment ${!currentPath ? 'dbx-path-active' : ''}`}
                    onClick={() => {
                      setCurrentPath('');
                      setSearchQuery('');
                    }}
                  >
                    {volume.name}
                  </span>

                  {pathParts.map((part, idx) => {
                    const pathToPart = pathParts.slice(0, idx + 1).join('/') + '/';
                    const isLast = idx === pathParts.length - 1;
                    return (
                      <React.Fragment key={pathToPart}>
                        <span className="dbx-path-slash">/</span>
                        <span
                          className={`dbx-path-segment ${isLast ? 'dbx-path-active' : ''}`}
                          onClick={() => {
                            if (!isLast) {
                              setCurrentPath(pathToPart);
                              setSearchQuery('');
                            }
                          }}
                        >
                          {part}
                        </span>
                      </React.Fragment>
                    );
                  })}
                </div>

                {/* Copy path button */}
                <button
                  type="button"
                  className="dbx-path-copy-btn"
                  onClick={() => handleCopyText(currentDirectoryDisplay, 'path')}
                  title="Copy volume path"
                >
                  {copiedPath === currentDirectoryDisplay ? (
                    <Check size={13} style={{ color: 'var(--color-success, #10b981)' }} />
                  ) : (
                    <Copy size={13} />
                  )}
                </button>
              </div>

              {/* Path Bar Right: Quick search & item stats */}
              <div className="dbx-path-toolbar-group">
                <div className="dbx-search-wrapper">
                  <Search size={14} className="dbx-search-icon" />
                  <input
                    type="text"
                    placeholder="Filter files and directories..."
                    className="dbx-search-input"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      className="dbx-search-clear"
                      onClick={() => setSearchQuery('')}
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>

                <div className="dbx-items-count-badge">
                  {stats.totalItems} {stats.totalItems === 1 ? 'item' : 'items'}
                </div>
              </div>
            </div>

            {/* Drag and Drop Overlay Indicator */}
            {isDraggingOver && (
              <div className="dbx-dropzone-overlay">
                <div className="dbx-dropzone-content">
                  <Upload size={36} className="text-primary" />
                  <h3>Drop files here to upload</h3>
                  <p>Uploading to <code>{currentDirectoryDisplay}</code></p>
                </div>
              </div>
            )}

            {/* Databricks File Explorer Table */}
            <div className="dbx-table-container">
              <table className="dbx-file-table">
                <thead>
                  <tr>
                    <th
                      className="dbx-th dbx-th-name"
                      onClick={() => handleSort('name')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Name</span>
                        {sortField === 'name' ? (
                          sortOrder === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />
                        ) : (
                          <ArrowUpDown size={13} className="opacity-40" />
                        )}
                      </div>
                    </th>
                    <th
                      className="dbx-th dbx-th-size"
                      onClick={() => handleSort('size')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Size</span>
                        {sortField === 'size' ? (
                          sortOrder === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />
                        ) : (
                          <ArrowUpDown size={13} className="opacity-40" />
                        )}
                      </div>
                    </th>
                    <th
                      className="dbx-th dbx-th-type"
                      onClick={() => handleSort('type')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Type</span>
                        {sortField === 'type' ? (
                          sortOrder === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />
                        ) : (
                          <ArrowUpDown size={13} className="opacity-40" />
                        )}
                      </div>
                    </th>
                    <th
                      className="dbx-th dbx-th-date"
                      onClick={() => handleSort('last_modified')}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>Last modified</span>
                        {sortField === 'last_modified' ? (
                          sortOrder === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />
                        ) : (
                          <ArrowUpDown size={13} className="opacity-40" />
                        )}
                      </div>
                    </th>
                    <th className="dbx-th dbx-th-actions">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {volumeFilesQuery.isLoading ? (
                    <tr>
                      <td colSpan={5} className="dbx-empty-cell">
                        <div className="flex flex-col items-center justify-center py-12 gap-3">
                          <Loader2 size={24} className="spin text-primary" />
                          <p className="text-sm text-subtle">Loading volume contents...</p>
                        </div>
                      </td>
                    </tr>
                  ) : displayItems.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="dbx-empty-cell">
                        <div className="dbx-empty-state-card">
                          <div className="dbx-empty-icon-circle">
                            <Folder size={28} className="text-subtle" />
                          </div>
                          <h3 className="dbx-empty-title">
                            {searchQuery ? 'No matching files or folders' : 'This folder is empty'}
                          </h3>
                          <p className="dbx-empty-subtitle">
                            {searchQuery
                              ? `No items found matching "${searchQuery}".`
                              : 'Upload files or create directories to organize your unstructured data in this volume.'}
                          </p>
                          {canModify && !searchQuery && (
                            <div className="dbx-empty-actions">
                              <button
                                type="button"
                                className="btn-primary flex items-center gap-1.5"
                                onClick={() => fileInputRef.current?.click()}
                              >
                                <Upload size={14} /> Upload files
                              </button>
                              <button
                                type="button"
                                className="btn-secondary flex items-center gap-1.5"
                                onClick={() => {
                                  setNewDirName('');
                                  setShowCreateDirModal(true);
                                }}
                              >
                                <FolderPlus size={14} /> Create directory
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    displayItems.map((item) => {
                      const isDir = item.file_path.endsWith('/') || item.content_type === 'application/x-directory';
                      const cleanName = isDir ? item.file_name.replace(/\/$/, '') : item.file_name;
                      const typeInfo = getFileTypeInfo(item.file_path, isDir);
                      const IconComponent = typeInfo.icon;
                      const isSelected = previewFile?.file_path === item.file_path;

                      return (
                        <tr
                          key={item.file_path}
                          className={`dbx-file-row ${isSelected ? 'dbx-row-selected' : ''}`}
                          onClick={() => {
                            if (isDir) {
                              setCurrentPath(item.file_path);
                              setSearchQuery('');
                            } else {
                              setPreviewFile(item);
                              setPreviewTab('preview');
                            }
                          }}
                        >
                          {/* File / Folder Name */}
                          <td className="dbx-td-name">
                            <div className="flex items-center gap-3">
                              <div
                                className="dbx-file-icon-box"
                                style={{
                                  backgroundColor: typeInfo.bgColor,
                                  color: typeInfo.color,
                                }}
                              >
                                <IconComponent size={16} />
                              </div>
                              <span className={`dbx-file-name ${isDir ? 'dbx-dir-name' : ''}`}>
                                {cleanName}
                              </span>
                            </div>
                          </td>

                          {/* Size */}
                          <td className="dbx-td-size">
                            {isDir ? (
                              <span className="text-subtle">—</span>
                            ) : (
                              formatBytes(item.size_bytes)
                            )}
                          </td>

                          {/* Type */}
                          <td className="dbx-td-type">
                            <span
                              className="dbx-type-badge"
                              style={{
                                color: typeInfo.color,
                                backgroundColor: typeInfo.bgColor,
                              }}
                            >
                              {typeInfo.label}
                            </span>
                          </td>

                          {/* Last Modified */}
                          <td className="dbx-td-date">
                            <span title={new Date(item.last_modified).toISOString()}>
                              {formatDate(item.last_modified)}
                            </span>
                          </td>

                          {/* Actions */}
                          <td className="dbx-td-actions" onClick={(e) => e.stopPropagation()}>
                            <div className="dbx-row-action-buttons">
                              {!isDir && (
                                <>
                                  <button
                                    type="button"
                                    className="dbx-action-btn"
                                    onClick={() => handleDownload(item)}
                                    title="Download file"
                                  >
                                    <Download size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="dbx-action-btn"
                                    onClick={() => {
                                      setPreviewFile(item);
                                      setPreviewTab('preview');
                                    }}
                                    title="Preview file"
                                  >
                                    <Eye size={14} />
                                  </button>
                                </>
                              )}

                              <button
                                type="button"
                                className="dbx-action-btn"
                                onClick={() => handleCopyText(`${fullVolumePath}/${item.file_path.replace(/\/$/, '')}`, 'path')}
                                title="Copy volume path"
                              >
                                <Copy size={14} />
                              </button>

                              {canModify && (
                                <>
                                  <button
                                    type="button"
                                    className="dbx-action-btn"
                                    onClick={() => {
                                      setFileToRename(item);
                                      setNewName(cleanName);
                                      setShowRenameModal(true);
                                    }}
                                    title="Rename"
                                  >
                                    <Pencil size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    className="dbx-action-btn dbx-action-btn-danger"
                                    onClick={() => setFileToDelete(item)}
                                    title="Delete"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── 4. Databricks File Preview & Inspection Drawer ─────────────── */}
          {previewFile && (
            <div className="dbx-preview-drawer">
              {/* Drawer Header */}
              <div className="dbx-preview-header">
                <div className="flex items-center gap-2.5 min-w-0">
                  {(() => {
                    const info = getFileTypeInfo(previewFile.file_path, false);
                    const Icon = info.icon;
                    return (
                      <div
                        className="dbx-file-icon-box"
                        style={{ backgroundColor: info.bgColor, color: info.color }}
                      >
                        <Icon size={18} />
                      </div>
                    );
                  })()}
                  <div className="min-w-0">
                    <h3 className="dbx-preview-filename" title={previewFile.file_name}>
                      {previewFile.file_name}
                    </h3>
                    <div className="flex items-center gap-2 text-xs text-subtle">
                      <span>{formatBytes(previewFile.size_bytes)}</span>
                      <span>•</span>
                      <span>{getFileTypeInfo(previewFile.file_path, false).label}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    className="dbx-preview-action-btn"
                    onClick={() => handleDownload(previewFile)}
                    title="Download"
                  >
                    <Download size={14} />
                    <span>Download</span>
                  </button>
                  <button
                    type="button"
                    className="dbx-preview-action-btn"
                    onClick={() => handleCopyText(`${fullVolumePath}/${previewFile.file_path}`, 'path')}
                    title="Copy full path"
                  >
                    <Copy size={14} />
                    <span>Copy Path</span>
                  </button>
                  {canModify && (
                    <button
                      type="button"
                      className="dbx-preview-action-btn text-danger"
                      onClick={() => setFileToDelete(previewFile)}
                      title="Delete file"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                  <button
                    type="button"
                    className="dbx-preview-close-btn"
                    onClick={() => setPreviewFile(null)}
                    title="Close preview"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* Drawer Content */}
              <div className="dbx-preview-body">
                {/* File Metadata Card */}
                <div className="dbx-preview-metadata-card">
                  <div className="dbx-meta-item">
                    <span className="dbx-meta-label">Full Path</span>
                    <span className="dbx-meta-value dbx-code-text">
                      {fullVolumePath}/{previewFile.file_path}
                    </span>
                  </div>
                  <div className="dbx-meta-item">
                    <span className="dbx-meta-label">Size</span>
                    <span className="dbx-meta-value">{formatBytes(previewFile.size_bytes)}</span>
                  </div>
                  <div className="dbx-meta-item">
                    <span className="dbx-meta-label">Content Type</span>
                    <span className="dbx-meta-value">{previewFile.content_type || 'application/octet-stream'}</span>
                  </div>
                  <div className="dbx-meta-item">
                    <span className="dbx-meta-label">Last Modified</span>
                    <span className="dbx-meta-value">{formatDate(previewFile.last_modified)}</span>
                  </div>
                  {previewFile.uploaded_by && (
                    <div className="dbx-meta-item">
                      <span className="dbx-meta-label">Uploaded By</span>
                      <span className="dbx-meta-value">{previewFile.uploaded_by}</span>
                    </div>
                  )}
                </div>

                {/* Preview Tabs / Views */}
                {(() => {
                  const info = getFileTypeInfo(previewFile.file_path, false);

                  if (previewLoading) {
                    return (
                      <div className="dbx-preview-loader">
                        <Loader2 size={24} className="spin text-primary" />
                        <p>Loading preview...</p>
                      </div>
                    );
                  }

                  if (info.previewType === 'image' && previewImageUrl) {
                    return (
                      <div className="dbx-image-preview-container">
                        <img
                          src={previewImageUrl}
                          alt={previewFile.file_name}
                          className="dbx-preview-image"
                        />
                      </div>
                    );
                  }

                  if (info.previewType === 'csv' && previewContent) {
                    const parsed = parseCsvPreview(previewContent, 50);
                    return (
                      <div className="dbx-csv-preview-wrapper">
                        <div className="dbx-preview-tab-row">
                          <button
                            type="button"
                            className={`dbx-subtab-btn ${previewTab === 'preview' ? 'is-active' : ''}`}
                            onClick={() => setPreviewTab('preview')}
                          >
                            <TableIcon size={14} /> Table Preview (first 50 rows)
                          </button>
                          <button
                            type="button"
                            className={`dbx-subtab-btn ${previewTab === 'raw' ? 'is-active' : ''}`}
                            onClick={() => setPreviewTab('raw')}
                          >
                            <FileText size={14} /> Raw CSV
                          </button>
                        </div>

                        {previewTab === 'preview' ? (
                          <div className="dbx-csv-table-scroll">
                            <table className="dbx-csv-table">
                              <thead>
                                <tr>
                                  <th className="dbx-csv-th-index">#</th>
                                  {parsed.headers.map((h, i) => (
                                    <th key={i} className="dbx-csv-th">{h}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {parsed.rows.map((row, rIdx) => (
                                  <tr key={rIdx}>
                                    <td className="dbx-csv-td-index">{rIdx + 1}</td>
                                    {row.map((cell, cIdx) => (
                                      <td key={cIdx} className="dbx-csv-td">{cell}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <pre className="dbx-code-preview-block">
                            <code>{previewContent}</code>
                          </pre>
                        )}
                      </div>
                    );
                  }

                  if ((info.previewType === 'json' || info.previewType === 'code') && previewContent) {
                    return (
                      <div className="dbx-code-preview-wrapper">
                        <div className="dbx-code-header">
                          <span className="text-xs text-subtle font-mono">
                            {previewContent.split('\n').length} lines
                          </span>
                          <button
                            type="button"
                            className="dbx-copy-code-btn"
                            onClick={() => handleCopyText(previewContent, 'path')}
                          >
                            <Copy size={13} /> Copy code
                          </button>
                        </div>
                        <pre className="dbx-code-preview-block">
                          <code>{previewContent}</code>
                        </pre>
                      </div>
                    );
                  }

                  if (info.previewType === 'parquet') {
                    const pySparkSnippet = `# Read this volume file in Spark / Databricks\ndf = spark.read.parquet("${fullVolumePath}/${previewFile.file_path}")\ndisplay(df)`;
                    const duckDbSnippet = `# Read this volume file in DuckDB\nimport duckdb\n\ndf = duckdb.read_parquet("${fullVolumePath}/${previewFile.file_path}").df()\nprint(df.head())`;
                    const sqlSnippet = `-- Query volume file in SQL Warehouse\nSELECT * \nFROM read_parquet('${fullVolumePath}/${previewFile.file_path}')\nLIMIT 10;`;

                    return (
                      <div className="dbx-parquet-guide-card">
                        <div className="dbx-guide-banner">
                          <Layers size={18} className="text-primary" />
                          <div>
                            <h4 className="font-semibold text-sm">Parquet Dataset</h4>
                            <p className="text-xs text-subtle">
                              Parquet is a binary columnar format. Use one of the code snippets below to query this file.
                            </p>
                          </div>
                        </div>

                        <div className="dbx-snippet-section">
                          <div className="dbx-snippet-header">
                            <span className="text-xs font-semibold">Python (PySpark)</span>
                            <button
                              type="button"
                              className="dbx-copy-code-btn"
                              onClick={() => handleCopyText(pySparkSnippet, 'path')}
                            >
                              <Copy size={12} /> Copy
                            </button>
                          </div>
                          <pre className="dbx-code-preview-block">
                            <code>{pySparkSnippet}</code>
                          </pre>
                        </div>

                        <div className="dbx-snippet-section mt-3">
                          <div className="dbx-snippet-header">
                            <span className="text-xs font-semibold">DuckDB / Python</span>
                            <button
                              type="button"
                              className="dbx-copy-code-btn"
                              onClick={() => handleCopyText(duckDbSnippet, 'path')}
                            >
                              <Copy size={12} /> Copy
                            </button>
                          </div>
                          <pre className="dbx-code-preview-block">
                            <code>{duckDbSnippet}</code>
                          </pre>
                        </div>

                        <div className="dbx-snippet-section mt-3">
                          <div className="dbx-snippet-header">
                            <span className="text-xs font-semibold">SQL Warehouse</span>
                            <button
                              type="button"
                              className="dbx-copy-code-btn"
                              onClick={() => handleCopyText(sqlSnippet, 'path')}
                            >
                              <Copy size={12} /> Copy
                            </button>
                          </div>
                          <pre className="dbx-code-preview-block">
                            <code>{sqlSnippet}</code>
                          </pre>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div className="dbx-binary-info-card">
                      <div className="flex flex-col items-center justify-center py-8 gap-3 text-center">
                        <File size={32} className="text-subtle" />
                        <div>
                          <h4 className="font-semibold text-sm">Binary file</h4>
                          <p className="text-xs text-subtle max-w-sm mt-1">
                            A preview is not directly available in the browser for this file format. You can download the file to inspect it locally.
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn-primary flex items-center gap-1.5 mt-2"
                          onClick={() => handleDownload(previewFile)}
                        >
                          <Download size={14} /> Download File
                        </button>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── 5. Details Tab ──────────────────────────────────────────────────── */}
      {activeTab === 'details' && (
        <div className="uc-tab-content">
          <div className="uc-detail-card" style={{ padding: '20px' }}>
            <div className="uc-detail-title" style={{ fontSize: '15px', fontWeight: 600, marginBottom: '16px' }}>
              Volume Metadata & Storage
            </div>
            <div className="uc-key-values" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
              <div>
                <span>Volume Name</span>
                <strong>{volume.name}</strong>
              </div>
              <div>
                <span>Catalog</span>
                <strong>{catalog}</strong>
              </div>
              <div>
                <span>Schema</span>
                <strong>{schema}</strong>
              </div>
              <div>
                <span>Type</span>
                <strong>MANAGED</strong>
              </div>
              <div>
                <span>ID</span>
                <strong className="font-mono text-xs">{volume.id}</strong>
              </div>
              <div>
                <span>Storage Location</span>
                <strong className="font-mono text-xs break-all">
                  {volume.storage_location || `${catalog}/${schema}/volumes/${volume.name}/`}
                </strong>
              </div>
              <div>
                <span>Owner</span>
                <div className="flex items-center gap-2">
                  <strong>
                    <OwnerName
                      securableType="volume"
                      name={`${catalog}.${schema}.${volume.name}`}
                      fallback={volume.owner || '—'}
                    />
                  </strong>
                  {canManage && (
                    <button
                      type="button"
                      className="gov-link-btn"
                      onClick={() => setActiveTab('permissions')}
                    >
                      Manage
                    </button>
                  )}
                </div>
              </div>
              <div>
                <span>Created By</span>
                <strong>{volume.created_by || '—'}</strong>
              </div>
              <div>
                <span>Created At</span>
                <strong>{formatDate(volume.created_at)}</strong>
              </div>
              <div>
                <span>Total Items</span>
                <strong>{stats.totalItems} ({stats.foldersCount} folders, {stats.filesCount} files)</strong>
              </div>
              <div>
                <span>Total Size</span>
                <strong>{formatBytes(stats.totalSize)}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 6. Permissions Tab ──────────────────────────────────────────────── */}
      {activeTab === 'permissions' && renderPermissionsTab({ kind: 'volume', catalog, schema, volume: volume.name })}

      {/* ── 7. Modals: Create Directory Modal ───────────────────────────────── */}
      {showCreateDirModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateDirModal(false)} style={{ zIndex: 10000 }}>
          <div
            className="modal-panel"
            onClick={(e) => e.stopPropagation()}
            style={{ width: 'min(440px, calc(100vw - 2rem))', borderRadius: '10px' }}
          >
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2">
                <FolderPlus size={18} className="text-primary" />
                <h3 className="font-semibold text-sm">Create directory</h3>
              </div>
              <button
                type="button"
                className="uc-icon-btn"
                onClick={() => setShowCreateDirModal(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!newDirName.trim()) return;
                createDirectoryMutation.mutate({
                  dirName: newDirName.trim(),
                  subPath: currentPath,
                });
              }}
              className="p-4 flex flex-col gap-4"
            >
              <div>
                <label className="text-xs font-semibold text-subtle block mb-1">
                  Location
                </label>
                <div className="text-xs font-mono bg-subtle p-2 rounded border break-all">
                  {currentDirectoryDisplay}/
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-subtle block mb-1">
                  Directory name *
                </label>
                <input
                  type="text"
                  autoFocus
                  placeholder="e.g. raw_data, exports, 2026-09"
                  className="uc-input w-full"
                  value={newDirName}
                  onChange={(e) => setNewDirName(e.target.value)}
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateDirModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary flex items-center gap-1.5"
                  disabled={!newDirName.trim() || createDirectoryMutation.isPending}
                >
                  {createDirectoryMutation.isPending && <Loader2 size={14} className="spin" />}
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 8. Modals: Rename Modal ─────────────────────────────────────────── */}
      {showRenameModal && fileToRename && (
        <div className="modal-backdrop" onClick={() => setShowRenameModal(false)} style={{ zIndex: 10000 }}>
          <div
            className="modal-panel"
            onClick={(e) => e.stopPropagation()}
            style={{ width: 'min(440px, calc(100vw - 2rem))', borderRadius: '10px' }}
          >
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2">
                <Pencil size={18} className="text-primary" />
                <h3 className="font-semibold text-sm">
                  Rename {fileToRename.file_path.endsWith('/') ? 'directory' : 'file'}
                </h3>
              </div>
              <button
                type="button"
                className="uc-icon-btn"
                onClick={() => setShowRenameModal(false)}
              >
                <X size={16} />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!newName.trim() || newName.trim() === fileToRename.file_name.replace(/\/$/, '')) {
                  setShowRenameModal(false);
                  return;
                }
                renameMutation.mutate({
                  oldPath: fileToRename.file_path,
                  newName: newName.trim(),
                });
              }}
              className="p-4 flex flex-col gap-4"
            >
              <div>
                <label className="text-xs font-semibold text-subtle block mb-1">
                  New name *
                </label>
                <input
                  type="text"
                  autoFocus
                  className="uc-input w-full"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowRenameModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary flex items-center gap-1.5"
                  disabled={!newName.trim() || renameMutation.isPending}
                >
                  {renameMutation.isPending && <Loader2 size={14} className="spin" />}
                  Rename
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 9. Modals: Delete Confirmation Dialog ───────────────────────────── */}
      {fileToDelete && (
        <ConfirmDialog
          title={`Delete ${fileToDelete.file_path.endsWith('/') ? 'directory' : 'file'}`}
          message={`Are you sure you want to permanently delete "${fileToDelete.file_name}" from volume "${volume.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          isDestructive={true}
          isLoading={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(fileToDelete.file_path)}
          onCancel={() => setFileToDelete(null)}
        />
      )}
    </div>
  );
};

export default VolumeExplorer;
