import { useState, useEffect, useRef } from 'react';
import { computeApi } from '../computeApi';

const MAX_LINES = 1000;

/**
 * Hook that streams pod logs via SSE.
 *
 * @param {string|null} resourceId
 * @returns {{ lines: string[], connected: boolean, error: string|null }}
 */
export function useJobLogs(resourceId) {
  const [lines, setLines] = useState([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('idle');
  const esRef = useRef(null);
  const receivedLineRef = useRef(false);

  useEffect(() => {
    // Close existing stream
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setLines([]);
    setConnected(false);
    setError(null);
    receivedLineRef.current = false;
    setStatus(resourceId ? 'connecting' : 'idle');

    if (!resourceId) return;

    const es = computeApi.streamResourceLogs(
      resourceId,
      (line) => {
        receivedLineRef.current = true;
        setLines((prev) => {
          const next = [...prev, line];
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
        });
      },
      (err) => {
        setConnected(false);
        if (err.type === 'error') {
          setStatus('error');
          setError(
            receivedLineRef.current
              ? 'Log stream disconnected'
              : 'Unable to connect to the log stream. If the pod is running, try refreshing or check your access.'
          );
        }
      },
    );

    es.onopen = () => {
      setConnected(true);
      setStatus('live');
    };
    esRef.current = es;

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
      setStatus('idle');
    };
  }, [resourceId]);

  return { lines, connected, error, status };
}
