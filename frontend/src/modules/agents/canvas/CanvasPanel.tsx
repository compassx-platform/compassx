import { useEffect, useState } from 'react';
import { agentRuntimeApi } from '@/modules/agents/agentRuntimeApi';
import { CanvasFrame } from './CanvasFrame';
import { canvasTitle, checkCanvasSource } from './canvasSourceGate';

interface CanvasPanelProps {
  sessionId: string;
  paths: string[];
  activePath: string;
  onSelect: (path: string) => void;
}

export function CanvasPanel({ sessionId, paths, activePath, onSelect }: CanvasPanelProps) {
  const [source, setSource] = useState('');
  const [rejected, setRejected] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activePath) {
      setSource('');
      setRejected('');
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    const load = () => {
      agentRuntimeApi.readFile(sessionId, activePath)
        .then((file) => {
          if (cancelled) return;
          if (file.missing) {
            setSource('');
            setRejected('This canvas file is no longer in the session.');
            return;
          }
          if (file.truncated) {
            setSource('');
            setRejected('This canvas is too large.');
            return;
          }
          const problem = checkCanvasSource(file.content || '');
          setSource(problem ? '' : file.content || '');
          setRejected(problem || '');
        })
        .catch(() => {
          if (!cancelled) {
            setSource('');
            setRejected('This canvas could not be read.');
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    setLoading(true);
    load();
    const timer = window.setInterval(load, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sessionId, activePath]);

  if (!paths.length) {
    return <p style={{ margin: 16, color: '#64748b', fontSize: '0.84rem' }}>No canvas in this session yet.</p>;
  }

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      {paths.length > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '8px 10px', borderBottom: '1px solid #e2e8f0' }}>
          {paths.map((path) => {
            const selected = path === activePath;
            return (
              <button
                key={path}
                type="button"
                aria-pressed={selected}
                onClick={() => onSelect(path)}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: 999,
                  background: selected ? '#18181b' : '#ffffff',
                  color: selected ? '#ffffff' : '#334155',
                  padding: '3px 10px',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                }}
              >
                {canvasTitle(path)}
              </button>
            );
          })}
        </div>
      )}
      {loading && !source && !rejected ? (
        <p style={{ margin: 16, color: '#64748b', fontSize: '0.84rem' }}>Loading canvas…</p>
      ) : (
        <CanvasFrame source={source} rejected={rejected} />
      )}
    </div>
  );
}
