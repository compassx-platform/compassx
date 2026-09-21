import React, { useEffect, useState, useRef } from 'react';
import { Terminal, Trash2, Pause, Play, AlertCircle } from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import { useNotebookStore } from '../../store/notebookStore';

export default function PodLogsPanel() {
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const [logs, setLogs] = useState<string[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selectedPod?.resource_id) {
      setLogs([]);
      return;
    }

    let es: EventSource | null = null;
    setError(null);
    setLogs([]);

    try {
      es = computeApi.streamResourceLogs(
        selectedPod.resource_id,
        (line: string) => {
          if (!isPaused) {
            setLogs((prev) => [...prev.slice(-300), line]);
          }
        },
        (err: any) => {
          console.warn('[notebook] log stream error:', err);
        }
      );
    } catch (err: any) {
      setError(err?.message ?? 'Failed to connect to pod logs');
    }

    return () => {
      if (es) es.close();
    };
  }, [selectedPod?.resource_id, isPaused]);

  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isPaused]);

  return (
    <div className="notebook-logs-panel">
      <div className="notebook-sidebar-section-header">
        <span className="notebook-sidebar-count">{logs.length} lines logged</span>
        <div className="notebook-logs-actions">
          <button
            type="button"
            className={`notebook-sidebar-icon-btn ${isPaused ? 'is-active' : ''}`}
            onClick={() => setIsPaused((p) => !p)}
            title={isPaused ? 'Resume auto-scroll' : 'Pause log stream'}
          >
            {isPaused ? <Play size={12} /> : <Pause size={12} />}
          </button>
          <button
            type="button"
            className="notebook-sidebar-icon-btn"
            onClick={() => setLogs([])}
            title="Clear logs"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {!selectedPod ? (
        <div className="notebook-sidebar-empty">
          <Terminal size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
          <span>No compute pod connected.</span>
        </div>
      ) : logs.length === 0 ? (
        <div className="notebook-sidebar-empty">
          <Terminal size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
          <span>Waiting for compute logs...</span>
        </div>
      ) : (
        <div className="notebook-logs-console" ref={scrollRef}>
          {logs.map((line, idx) => (
            <div key={idx} className="notebook-log-line">
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
