// @ts-nocheck
import { useState } from 'react';
import { Play, Square, Trash2, Terminal, ExternalLink, RefreshCw, X, Box, Copy, Check } from 'lucide-react';
import { AppTable } from '@/components/common/AppTable';
import ConfirmDialog from '@/components/common/ConfirmDialog';
import { computeApi } from '@/modules/compute/computeApi';

const statusColorMap = {
  ready: '#10b981',
  running: '#10b981',
  provisioning: '#f59e0b',
  initializing: '#f59e0b',
  pending: '#f59e0b',
  suspended: '#6b7280',
  stopped: '#6b7280',
  failed: '#ef4444',
  terminated: '#9ca3af',
};

const consumerBadgeStyles = {
  app: { bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb', label: 'App Engine' },
  agent: { bg: 'rgba(147, 51, 234, 0.12)', color: '#7c3aed', label: 'Agent Runtime' },
  omnigent_dev: { bg: 'rgba(16, 185, 129, 0.12)', color: '#059669', label: 'Dev Studio' },
  notebook: { bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706', label: 'Notebook' },
  job: { bg: 'rgba(236, 72, 153, 0.12)', color: '#db2777', label: 'Jobs' },
  generic: { bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563', label: 'Sandbox' },
};

/**
 * Table displaying active compute sandboxes with lifecycle actions & log viewing.
 */
export default function ComputeSandboxesTable({
  sandboxes = [],
  onTerminate,
  onSuspend,
  onResume,
  loadingId,
  onRefresh,
}) {
  const [sandboxToDelete, setSandboxToDelete] = useState(null);
  const [activeLogsSandbox, setActiveLogsSandbox] = useState(null);
  const [logsText, setLogsText] = useState('');
  const [logsLoading, setLogsLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleOpenLogs = async (sandbox) => {
    setActiveLogsSandbox(sandbox);
    setLogsLoading(true);
    try {
      const data = await computeApi.getSandboxLogs(sandbox.id, 500);
      setLogsText(data?.logs || 'No logs available.');
    } catch (e) {
      setLogsText(`[Failed to fetch logs: ${e.message}]`);
    } finally {
      setLogsLoading(false);
    }
  };

  const handleRefreshLogs = async () => {
    if (!activeLogsSandbox) return;
    setLogsLoading(true);
    try {
      const data = await computeApi.getSandboxLogs(activeLogsSandbox.id, 500);
      setLogsText(data?.logs || 'No logs available.');
    } catch (e) {
      setLogsText(`[Failed to fetch logs: ${e.message}]`);
    } finally {
      setLogsLoading(false);
    }
  };

  const handleCopyLogs = () => {
    navigator.clipboard.writeText(logsText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleConfirmDelete = async () => {
    if (!sandboxToDelete) return;
    try {
      await onTerminate(sandboxToDelete.id);
    } finally {
      setSandboxToDelete(null);
    }
  };

  const isRunning = (sb) => ['ready', 'running'].includes(String(sb.status).toLowerCase());
  const isSuspended = (sb) => ['suspended', 'stopped'].includes(String(sb.status).toLowerCase());
  const isTransitioning = (sb) => ['provisioning', 'initializing', 'pending'].includes(String(sb.status).toLowerCase());

  const columns = [
    {
      key: 'name',
      header: 'Sandbox Name & ID',
      render: (sandbox) => {
        const rawStatus = String(sandbox.status || 'unknown').toLowerCase();
        const dotColor = statusColorMap[rawStatus] || '#6b7280';
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
              <span
                title={`Status: ${sandbox.status}`}
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: dotColor,
                  boxShadow: isRunning(sandbox) ? `0 0 6px ${dotColor}` : 'none',
                  flexShrink: 0,
                }}
              />
              <span style={{ color: 'var(--color-text)' }}>{sandbox.name}</span>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', paddingLeft: '16px', fontFamily: 'monospace' }}>
              {sandbox.id}
            </span>
          </div>
        );
      },
    },
    {
      key: 'consumer',
      header: 'Consumer Module',
      render: (sandbox) => {
        const key = sandbox.consumer_module || 'generic';
        const badge = consumerBadgeStyles[key] || consumerBadgeStyles.generic;
        return (
          <span
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: badge.bg,
              color: badge.color,
            }}
          >
            {badge.label || key}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Status',
      render: (sandbox) => {
        const rawStatus = String(sandbox.status || 'unknown').toLowerCase();
        const color = statusColorMap[rawStatus] || '#6b7280';
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 500, color, textTransform: 'capitalize' }}>
            {sandbox.status}
          </span>
        );
      },
    },
    {
      key: 'runtime',
      header: 'Runtime / Mode',
      render: (sandbox) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <span style={{ fontSize: '12px', fontWeight: 500, textTransform: 'capitalize' }}>
            {sandbox.runtime_mode || 'Auto'}
          </span>
          {sandbox.image && (
            <span
              title={sandbox.image}
              style={{
                fontSize: '11px',
                color: 'var(--color-text-muted)',
                maxWidth: '140px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {sandbox.image}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'endpoints',
      header: 'Endpoints',
      render: (sandbox) => {
        const endpoints = sandbox.endpoints || {};
        const entries = Object.entries(endpoints);
        if (entries.length === 0) {
          return <span style={{ color: 'var(--color-text-muted)', fontSize: '12px' }}>—</span>;
        }
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {entries.map(([port, url]) => (
              <a
                key={port}
                href={url}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '1px 6px',
                  borderRadius: '3px',
                  background: 'var(--color-surface-secondary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-primary)',
                  fontSize: '11px',
                  textDecoration: 'none',
                  fontWeight: 500,
                }}
              >
                :{port} <ExternalLink size={10} />
              </a>
            ))}
          </div>
        );
      },
    },
    {
      key: 'created',
      header: 'Created',
      className: 'app-table-muted',
      render: (sandbox) => {
        if (!sandbox.created_at) return '—';
        try {
          return new Date(sandbox.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + new Date(sandbox.created_at).toLocaleDateString();
        } catch {
          return sandbox.created_at;
        }
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (sandbox) => (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <button
            className="ghost-icon-btn"
            onClick={(e) => {
              e.stopPropagation();
              handleOpenLogs(sandbox);
            }}
            title="View Logs"
            aria-label={`View logs for ${sandbox.name}`}
          >
            <Terminal size={13} />
          </button>

          {isRunning(sandbox) ? (
            <button
              className="ghost-icon-btn"
              onClick={(e) => {
                e.stopPropagation();
                onSuspend(sandbox.id);
              }}
              disabled={loadingId === sandbox.id || isTransitioning(sandbox)}
              title="Suspend Compute"
              aria-label={`Suspend ${sandbox.name}`}
            >
              {loadingId === sandbox.id ? '...' : <Square size={12} fill="#5A5A5A" strokeWidth={0} />}
            </button>
          ) : (
            <button
              className="ghost-icon-btn"
              onClick={(e) => {
                e.stopPropagation();
                onResume(sandbox.id);
              }}
              disabled={loadingId === sandbox.id || isTransitioning(sandbox)}
              title="Resume Compute"
              aria-label={`Resume ${sandbox.name}`}
            >
              {loadingId === sandbox.id ? '...' : <Play size={12} fill="#5A5A5A" strokeWidth={0} />}
            </button>
          )}

          <button
            className="ghost-icon-btn"
            onClick={(e) => {
              e.stopPropagation();
              setSandboxToDelete(sandbox);
            }}
            disabled={loadingId === sandbox.id}
            title="Terminate Sandbox"
            aria-label={`Terminate ${sandbox.name}`}
          >
            <Trash2 size={13} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <>
      <AppTable
        columns={columns}
        rows={sandboxes}
        rowKey={(sb) => sb.id}
        emptyText="No compute sandboxes running currently"
      />

      {/* Confirmation Dialog for Termination */}
      {sandboxToDelete && (
        <ConfirmDialog
          title="Terminate Sandbox"
          message={`Are you sure you want to terminate sandbox "${sandboxToDelete.name}" (${sandboxToDelete.id})? Compute and ephemeral state will be cleaned up.`}
          confirmLabel="Terminate"
          onCancel={() => setSandboxToDelete(null)}
          onConfirm={handleConfirmDelete}
          isLoading={loadingId === sandboxToDelete.id}
          isDestructive
        />
      )}

      {/* Log Viewer Modal */}
      {activeLogsSandbox && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
          onClick={() => setActiveLogsSandbox(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '850px',
              height: '560px',
              backgroundColor: 'var(--color-surface)',
              borderRadius: '6px',
              border: '1px solid var(--color-border)',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderBottom: '1px solid var(--color-border)',
                background: 'var(--color-surface-secondary)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={15} color="var(--color-primary)" />
                <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--color-text)' }}>
                  Sandbox Logs: {activeLogsSandbox.name}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                  ({activeLogsSandbox.id})
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="ghost-icon-btn"
                  onClick={handleCopyLogs}
                  title="Copy logs"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}
                >
                  {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
                <button
                  className="ghost-icon-btn"
                  onClick={handleRefreshLogs}
                  disabled={logsLoading}
                  title="Refresh logs"
                >
                  <RefreshCw size={13} className={logsLoading ? 'animate-spin' : ''} />
                </button>
                <button
                  className="ghost-icon-btn"
                  onClick={() => setActiveLogsSandbox(null)}
                  title="Close"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Terminal Body */}
            <div
              style={{
                flex: 1,
                backgroundColor: '#0d1117',
                color: '#e6edf3',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                fontSize: '12px',
                lineHeight: '1.5',
                padding: '12px 16px',
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {logsLoading ? (
                <div style={{ color: '#8b949e' }}>Loading logs...</div>
              ) : (
                logsText || <span style={{ color: '#8b949e' }}>[No output generated yet]</span>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
