import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Check,
  Copy,
  Download,
  File,
  Loader2,
  Save,
  X,
} from 'lucide-react';
import ReactCodeMirror from '@uiw/react-codemirror';
import { EditorView } from '@codemirror/view';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { json } from '@codemirror/lang-json';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { markdown } from '@codemirror/lang-markdown';
import { cn } from '@/lib/utils';
import { useDevFileContent, useWriteDevFile } from '../../hooks/useApps';
import { formatBytes } from './fileStatusUtils';

export interface FileViewerProps {
  appId: string;
  path: string;
  onClose: () => void;
}

const editorTheme = EditorView.theme(
  {
    '&': {
      height: '100%',
      fontSize: '12.5px',
      backgroundColor: '#ffffff',
      color: '#0f172a',
    },
    '.cm-scroller': {
      fontFamily:
        'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      lineHeight: '1.6',
    },
    '.cm-content': {
      padding: '8px 0',
      caretColor: '#0f172a',
    },
    '.cm-line': {
      padding: '0 8px',
    },
    '.cm-gutters': {
      backgroundColor: '#f8fafc',
      color: '#94a3b8',
      borderRight: '1px solid #e2e8f0',
      paddingRight: '6px',
    },
    '.cm-activeLineGutter': {
      backgroundColor: '#f1f5f9',
      color: '#334155',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(0, 0, 0, 0.03)',
    },
  },
  { dark: false }
);

export function FileViewer({ appId, path, onClose }: FileViewerProps) {
  const { data: fileData, isLoading, isError, error, refetch } = useDevFileContent(appId, path);
  const writeMutation = useWriteDevFile();

  const [content, setContent] = useState<string>('');
  const [isModified, setIsModified] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  // Sync content when file data loads
  useEffect(() => {
    if (fileData) {
      setContent(fileData.content);
      setIsModified(false);
    }
  }, [fileData]);

  const ext = useMemo(() => {
    const dot = path.lastIndexOf('.');
    return dot > 0 ? path.slice(dot + 1).toLowerCase() : '';
  }, [path]);

  const filename = useMemo(() => {
    return path.split('/').filter(Boolean).pop() ?? path;
  }, [path]);

  const extensions = useMemo(() => {
    const exts = [editorTheme];
    if (['js', 'jsx', 'ts', 'tsx'].includes(ext)) {
      exts.push(javascript({ jsx: true, typescript: ['ts', 'tsx'].includes(ext) }));
    } else if (ext === 'py') {
      exts.push(python());
    } else if (ext === 'json') {
      exts.push(json());
    } else if (['html', 'htm'].includes(ext)) {
      exts.push(html());
    } else if (['css', 'scss', 'sass', 'less'].includes(ext)) {
      exts.push(css());
    } else if (['md', 'markdown'].includes(ext)) {
      exts.push(markdown());
    }
    return exts;
  }, [ext]);

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {}
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleSave = () => {
    if (!isModified || writeMutation.isPending) return;
    writeMutation.mutate(
      { appId, path, content },
      {
        onSuccess: () => {
          setIsModified(false);
          setSaveSuccess(true);
          setTimeout(() => setSaveSuccess(false), 2000);
        },
      }
    );
  };

  // Keyboard shortcut Ctrl+S / Cmd+S
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isModified, content, writeMutation.isPending]);

  return (
    <div className="flex h-full w-full min-h-0 flex-col overflow-hidden bg-white text-neutral-800 font-mono">
      {/* Header bar — White theme */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-3 py-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {/* Back button */}
          <button
            type="button"
            onClick={onClose}
            title="Back to files"
            aria-label="Back to files"
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[12px] font-mono text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
          >
            <ArrowLeft className="size-3.5" />
            <span>Files</span>
          </button>

          <div className="h-4 w-px bg-neutral-200" />

          {/* File icon and filename */}
          <div className="flex min-w-0 items-center gap-1.5">
            <File className="size-3.5 text-neutral-600 shrink-0" strokeWidth={1.5} />
            <span
              className="min-w-0 truncate font-mono text-[12px] font-semibold text-neutral-900"
              title={path}
            >
              {filename}
            </span>
          </div>

          {/* Modified badge */}
          {isModified && (
            <span
              className="rounded bg-amber-50 border border-amber-300 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 shrink-0"
              title="Unsaved changes (Ctrl+S to save)"
            >
              Modified
            </span>
          )}
        </div>

        {/* Header Actions */}
        <div className="flex shrink-0 items-center gap-1">
          {/* File size */}
          {fileData && (
            <span className="mr-1 text-[11px] text-neutral-400 font-mono tabular-nums">
              {formatBytes(fileData.size)}
            </span>
          )}

          {/* Save button */}
          {isModified && (
            <button
              type="button"
              onClick={handleSave}
              disabled={writeMutation.isPending}
              title="Save changes (Ctrl+S)"
              className="inline-flex items-center gap-1 rounded bg-neutral-900 px-2 py-1 text-[11px] font-mono font-medium text-white shadow-xs transition-colors hover:bg-neutral-800 disabled:opacity-50"
            >
              {writeMutation.isPending ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Save className="size-3" />
              )}
              <span>Save</span>
            </button>
          )}

          {saveSuccess && (
            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 font-mono font-medium mr-1">
              <Check className="size-3.5" />
              <span>Saved</span>
            </span>
          )}

          {/* Copy path */}
          <button
            type="button"
            onClick={handleCopyPath}
            title="Copy path"
            aria-label="Copy path"
            className="inline-flex size-7 items-center justify-center rounded text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
          >
            {copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
          </button>

          {/* Download */}
          <button
            type="button"
            onClick={handleDownload}
            title="Download file"
            aria-label="Download file"
            className="inline-flex size-7 items-center justify-center rounded text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
          >
            <Download className="size-3.5" />
          </button>

          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            title="Close file viewer"
            aria-label="Close file viewer"
            className="inline-flex size-7 items-center justify-center rounded text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
          >
            <X className="size-4" />
          </button>
        </div>
      </div>

      {/* Breadcrumb Path Banner */}
      <div className="flex items-center border-b border-neutral-200 bg-neutral-50 px-3 py-1 font-mono text-[11px] text-neutral-500 truncate">
        <span className="text-neutral-400 mr-1.5">Path:</span>
        <span className="truncate">{path}</span>
      </div>

      {/* Editor Body — Clean white CodeMirror with light gutters */}
      <div className="flex-1 min-h-0 overflow-auto bg-white [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:bg-neutral-300 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
        {isLoading ? (
          <div className="flex h-48 flex-col items-center justify-center gap-2 text-neutral-400">
            <Loader2 className="size-5 animate-spin text-neutral-500" />
            <span className="text-xs font-mono">Loading file content...</span>
          </div>
        ) : isError ? (
          <div className="flex h-48 flex-col items-center justify-center gap-2 px-4 text-center">
            <span className="text-xs font-mono text-rose-600">
              {error instanceof Error ? error.message : 'Failed to read file.'}
            </span>
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded bg-neutral-100 px-2.5 py-1 text-xs font-mono text-neutral-700 hover:bg-neutral-200"
            >
              Retry
            </button>
          </div>
        ) : (
          <ReactCodeMirror
            value={content}
            theme="light"
            extensions={extensions}
            onChange={(val) => {
              setContent(val);
              setIsModified(val !== fileData?.content);
            }}
            basicSetup={{
              lineNumbers: true,
              highlightActiveLineGutter: true,
              highlightSpecialChars: true,
              history: true,
              foldGutter: true,
              drawSelection: true,
              dropCursor: true,
              allowMultipleSelections: true,
              indentOnInput: true,
              syntaxHighlighting: true,
              bracketMatching: true,
              closeBrackets: true,
              autocompletion: true,
              rectangularSelection: true,
              crosshairCursor: true,
              highlightActiveLine: true,
              highlightSelectionMatches: true,
              closeBracketsKeymap: true,
              defaultKeymap: true,
              searchKeymap: true,
              historyKeymap: true,
              foldKeymap: true,
              completionKeymap: true,
              lintKeymap: true,
            }}
            className="h-full w-full"
            style={{
              height: '100%',
              fontSize: '12.5px',
              lineHeight: '1.6',
              fontFamily:
                'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            }}
          />
        )}
      </div>
    </div>
  );
}
