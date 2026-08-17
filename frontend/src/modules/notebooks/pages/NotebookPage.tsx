import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import Notebook from '@/modules/notebooks/components/Notebook';
import { useNotebookStore } from '@/modules/notebooks/store/notebookStore';
import { serialize, deserialize } from '@/modules/notebooks/lib/nbformat';
import api from '@/lib/api';

const AUTO_SAVE_MS = 5_000;

interface Props {
  notebookPath?: string;
  embedded?: boolean;
  onDelete?: () => void;
}

export default function NotebookPage({ notebookPath: notebookPathProp, embedded = false, onDelete }: Props) {
  const [searchParams] = useSearchParams();
  const notebookPath = notebookPathProp ?? searchParams.get('path') ?? 'notebooks/untitled.ipynb';
  const [isLoading, setIsLoading] = useState(true);

  const cells = useNotebookStore((s) => s.cells);
  const isDirty = useNotebookStore((s) => s.isDirty);
  const setNotebookPath = useNotebookStore((s) => s.setNotebookPath);
  const setNotebookId = useNotebookStore((s) => s.setNotebookId);
  const markClean = useNotebookStore((s) => s.markClean);
  const setCells = useNotebookStore((s) => s.setCells);

  // Hydrate store from URL param
  useEffect(() => {
    setIsLoading(true);
    setCells([]); // Clear previous notebook cells immediately so old notebook code is not shown
    setNotebookPath(notebookPath);
    // Reset compute, pod & kernel state so compute/kernel connection is evaluated fresh for the new notebook
    useNotebookStore.getState().setLastComputeInfo(null);
    useNotebookStore.getState().setSelectedPod(null);
    useNotebookStore.getState().setKernel(null);
    useNotebookStore.getState().setKernelStatus('unknown');
    useNotebookStore.setState({ notebookComputeLoaded: false });
  }, [notebookPath, setNotebookPath, setCells]);

  // Load existing notebook from backend
  useEffect(() => {
    let isCancelled = false;
    api
      .get(`/notebook/files/${notebookPath}`)
      .then((res) => {
        if (isCancelled) return;
        const data = res.data;
        const loaded = deserialize(data);
        setCells(loaded);
        // Store catalog metadata for compute persistence and auto-reconnect
        const catalog = data._catalog as { id?: string; last_compute_resource_id?: string; last_kernel_name?: string } | undefined;
        if (catalog?.id) {
          setNotebookId(catalog.id);
        }
        // Trigger auto-reconnect if last compute is stored
        if (catalog?.last_compute_resource_id) {
          useNotebookStore.getState().setLastComputeInfo({
            resource_id: catalog.last_compute_resource_id,
            kernel_name: catalog.last_kernel_name ?? null,
          });
        } else {
          useNotebookStore.getState().setLastComputeInfo(null);
        }
      })
      .catch(() => {
        if (isCancelled) return;
        // File doesn't exist yet — start blank with 1 code cell; still mark compute as loaded so modal shows
        setCells([{ id: Math.random().toString(36).slice(2, 10), type: 'code', source: '', outputs: [], executionCount: null, isRunning: false, cellStatus: 'clean' }]);
        useNotebookStore.getState().setLastComputeInfo(null);
      })
      .finally(() => {
        if (!isCancelled) setIsLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [notebookPath, setCells, setNotebookId]);

  const saveNotebook = useCallback(async () => {
    const nb = serialize(cells);
    await api.put(`/notebook/files/${notebookPath}`, nb);
    markClean();
  }, [cells, notebookPath, markClean]);

  // Keyboard shortcut Cmd/Ctrl+S
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        saveNotebook();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [saveNotebook]);

  // Auto-save every 30s when dirty
  useEffect(() => {
    const id = setInterval(() => {
      if (isDirty) saveNotebook();
    }, AUTO_SAVE_MS);
    return () => clearInterval(id);
  }, [isDirty, saveNotebook]);

  return (
    <div style={{ height: '100%' }}>
      <Notebook notebookPath={notebookPath} isLoading={isLoading} onDelete={onDelete} />
    </div>
  );
}

