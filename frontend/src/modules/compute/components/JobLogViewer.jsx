import { useEffect, useRef } from 'react';
import { useJobLogs } from '../hooks/useJobLogs';

/**
 * Streaming log output panel.
 *
 * @param {{ resourceId: string|null }} props
 */
export default function JobLogViewer({ resourceId }) {
  const { lines, connected, error, status } = useJobLogs(resourceId);
  const bottomRef = useRef(null);

  // Auto-scroll to bottom as new lines arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  function handleCopyAll() {
    navigator.clipboard.writeText(lines.join('\n'));
  }

  return (
    <div style={{
      border: '1px solid var(--color-border)',
      borderRadius: '8px',
      overflow: 'hidden',
      background: '#0d1117',
    }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 12px',
        borderBottom: '1px solid #30363d',
        background: '#161b22',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#8b949e' }}>
          {/* Connection status dot */}
          <span style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: connected ? '#3fb950' : '#484f58',
          }} />
          <span>{status === 'connecting' ? 'Connecting…' : connected ? 'Live' : 'Disconnected'}</span>
          <span style={{ marginLeft: '8px' }}>{lines.length} lines</span>
          {error && <span style={{ color: '#f85149', marginLeft: '8px' }}>{error}</span>}
        </div>
        <button
          onClick={handleCopyAll}
          disabled={lines.length === 0}
          style={{
            padding: '2px 10px',
            background: 'transparent',
            border: '1px solid #30363d',
            borderRadius: '4px',
            color: '#8b949e',
            cursor: lines.length === 0 ? 'not-allowed' : 'pointer',
            fontSize: '11px',
          }}
        >
          Copy all
        </button>
      </div>

      {/* Log output */}
      <div style={{
        maxHeight: '400px',
        overflowY: 'auto',
        padding: '12px',
        fontFamily: 'monospace',
        fontSize: '12px',
        lineHeight: '1.6',
        color: '#c9d1d9',
      }}>
        {lines.length === 0 && status === 'connecting' ? (
          <span style={{ color: '#484f58' }}>Connecting to pod log stream…</span>
        ) : lines.length === 0 && connected ? (
          <span style={{ color: '#484f58' }}>Waiting for logs…</span>
        ) : (
          lines.map((line, i) => (
            <div key={i}>{line}</div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
