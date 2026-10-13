// @ts-nocheck
import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  ArrowLeft,
  TerminalSquare,
  Play,
  Square,
  RefreshCw,
  Trash2,
  ExternalLink,
  Copy,
  Check,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { SandboxTerminal } from '@/components/sandbox/SandboxTerminal';
import ConfirmDialog from '@/components/common/ConfirmDialog';

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
  app: { bg: 'rgba(59, 130, 246, 0.15)', color: '#38bdf8', label: 'App Engine' },
  agent: { bg: 'rgba(147, 51, 234, 0.15)', color: '#c084fc', label: 'Agent Runtime' },
  omnigent_dev: { bg: 'rgba(16, 185, 129, 0.15)', color: '#34d399', label: 'Dev Studio' },
  notebook: { bg: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', label: 'Notebook' },
  job: { bg: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', label: 'Jobs' },
  generic: { bg: 'rgba(107, 114, 128, 0.2)', color: '#9ca3af', label: 'Generic Sandbox' },
};

const POLL_INTERVAL = 8000;

export default function ComputeSandboxTerminalPage() {
  const { sandboxId } = useParams();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const [sandbox, setSandbox] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const pollTimerRef = useRef(null);

  const fetchSandbox = useCallback(async (isBackground = false) => {
    if (!sandboxId) return;
    try {
      if (!isBackground) setLoading(true);
      const data = await computeApi.getSandbox(sandboxId);
      setSandbox(data);
      setError(null);
    } catch (err) {
      console.error('[ComputeSandboxTerminalPage] Failed to fetch sandbox:', err);
      if (!isBackground) {
        setError(err?.response?.data?.detail || err?.message || 'Failed to load sandbox details');
      }
    } finally {
      if (!isBackground) setLoading(false);
    }
  }, [sandboxId]);

  useEffect(() => {
    fetchSandbox(false);
    pollTimerRef.current = setInterval(() => {
      fetchSandbox(true);
    }, POLL_INTERVAL);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [fetchSandbox]);

  const handleCopyId = () => {
    if (!sandboxId) return;
    navigator.clipboard.writeText(sandboxId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleSuspend = async () => {
    if (!sandboxId) return;
    setActionLoading(true);
    try {
      await computeApi.suspendSandbox(sandboxId);
      toast.info('Suspending sandbox compute...');
      await fetchSandbox(false);
    } catch (err) {
      toast.error(`Suspend failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    if (!sandboxId) return;
    setActionLoading(true);
    try {
      await computeApi.resumeSandbox(sandboxId);
      toast.info('Resuming sandbox compute...');
      await fetchSandbox(false);
    } catch (err) {
      toast.error(`Resume failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTerminate = async () => {
    if (!sandboxId) return;
    setActionLoading(true);
    try {
      await computeApi.terminateSandbox(sandboxId);
      toast.success('Sandbox terminated successfully');
      navigate('/compute?tab=sandboxes');
    } catch (err) {
      toast.error(`Termination failed: ${err.message}`);
      setActionLoading(false);
      setShowDeleteConfirm(false);
    }
  };

  const isRunning = ['ready', 'running'].includes(String(sandbox?.status).toLowerCase());
  const isSuspended = ['suspended', 'stopped'].includes(String(sandbox?.status).toLowerCase());
  const rawStatus = String(sandbox?.status || (loading ? 'loading' : 'unknown')).toLowerCase();
  const dotColor = statusColorMap[rawStatus] || '#6b7280';
  const consumerKey = sandbox?.consumer_module || 'generic';
  const consumerBadge = consumerBadgeStyles[consumerKey] || consumerBadgeStyles.generic;
  const endpoints = Object.entries(sandbox?.endpoints || {});

  if (loading && !sandbox) {
    return (
      <div
        className="sandbox-terminal-page-root"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          width: '100%',
          background: '#0d1117',
          color: '#8b949e',
          gap: '12px',
        }}
      >
        <Loader2 size={28} className="spin" style={{ color: '#38bdf8' }} />
        <span style={{ fontSize: '13px' }}>Loading sandbox environment...</span>
      </div>
    );
  }

  if (error && !sandbox) {
    return (
      <div
        className="sandbox-terminal-page-root"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          width: '100%',
          background: '#0d1117',
          color: '#f0f6fc',
          padding: '24px',
          textAlign: 'center',
          gap: '16px',
        }}
      >
        <AlertCircle size={36} color="#ef4444" />
        <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>Sandbox Not Found</h2>
        <p style={{ color: '#8b949e', fontSize: '14px', maxWidth: '440px', margin: 0 }}>
          {error || `Unable to locate sandbox ID "${sandboxId}". It may have been terminated or expired.`}
        </p>
        <button
          onClick={() => navigate('/compute?tab=sandboxes')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: '6px',
            background: '#21262d',
            border: '1px solid #30363d',
            color: '#f0f6fc',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 500,
          }}
        >
          <ArrowLeft size={14} /> Back to Sandboxes
        </button>
      </div>
    );
  }

  return (
    <div
      className="sandbox-terminal-page-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        minHeight: 0,
        overflow: 'hidden',
        background: '#0d1117',
      }}
    >
      {/* ── Sleek Full-Page Header ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 18px',
          borderBottom: '1px solid #30363d',
          background: '#161b22',
          color: '#f0f6fc',
          flexShrink: 0,
          gap: '16px',
          flexWrap: 'wrap',
        }}
      >
        {/* Left Side: Back Button & Sandbox Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <button
            onClick={() => navigate('/compute?tab=sandboxes')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 10px',
              borderRadius: '6px',
              background: '#21262d',
              border: '1px solid #30363d',
              color: '#c9d1d9',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              transition: 'background 0.15s ease',
            }}
            title="Back to Sandboxes list"
          >
            <ArrowLeft size={13} />
            <span>Sandboxes</span>
          </button>

          <span style={{ color: '#30363d' }}>|</span>

          {/* Sandbox Identity & Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TerminalSquare size={16} color="#38bdf8" />
            <span style={{ fontWeight: 700, fontSize: '13px', color: '#f0f6fc' }}>
              {sandbox?.name || sandboxId}
            </span>

            {/* Click to copy ID */}
            <button
              onClick={handleCopyId}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                background: 'transparent',
                border: 'none',
                color: '#8b949e',
                fontFamily: 'monospace',
                fontSize: '11px',
                cursor: 'pointer',
                padding: '2px 4px',
                borderRadius: '3px',
              }}
              title="Click to copy sandbox ID"
            >
              <span>({sandboxId})</span>
              {copiedId ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
            </button>
          </div>

          {/* Status Badge */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '2px 8px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.06)',
              fontSize: '11px',
              fontWeight: 500,
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: dotColor,
                boxShadow: isRunning ? `0 0 6px ${dotColor}` : 'none',
              }}
            />
            <span style={{ textTransform: 'capitalize', color: dotColor }}>
              {sandbox?.status || 'Unknown'}
            </span>
          </div>

          {/* Consumer Module Badge */}
          <span
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: consumerBadge.bg,
              color: consumerBadge.color,
            }}
          >
            {consumerBadge.label}
          </span>

          {/* Runtime Mode */}
          {sandbox?.runtime_mode && (
            <span
              style={{
                fontSize: '11px',
                color: '#8b949e',
                background: '#21262d',
                padding: '2px 6px',
                borderRadius: '3px',
                border: '1px solid #30363d',
                textTransform: 'capitalize',
              }}
            >
              {sandbox.runtime_mode}
            </span>
          )}
        </div>

        {/* Right Side: Endpoints & Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Endpoints */}
          {endpoints.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginRight: '6px' }}>
              {endpoints.map(([port, url]) => (
                <a
                  key={port}
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    background: '#21262d',
                    border: '1px solid #30363d',
                    color: '#38bdf8',
                    fontSize: '11px',
                    textDecoration: 'none',
                    fontWeight: 500,
                  }}
                  title={`Open port ${port}`}
                >
                  :{port} <ExternalLink size={10} />
                </a>
              ))}
            </div>
          )}

          {/* Suspend / Resume Button */}
          {isRunning ? (
            <button
              onClick={handleSuspend}
              disabled={actionLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: '5px',
                background: '#21262d',
                border: '1px solid #30363d',
                color: '#f0f6fc',
                fontSize: '12px',
                fontWeight: 500,
                cursor: actionLoading ? 'not-allowed' : 'pointer',
              }}
              title="Suspend compute to save resources"
            >
              <Square size={11} fill="#f59e0b" color="#f59e0b" />
              <span>Suspend</span>
            </button>
          ) : isSuspended ? (
            <button
              onClick={handleResume}
              disabled={actionLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: '5px',
                background: '#238636',
                border: '1px solid rgba(240, 246, 252, 0.1)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 500,
                cursor: actionLoading ? 'not-allowed' : 'pointer',
              }}
              title="Resume compute container"
            >
              <Play size={11} fill="#ffffff" color="#ffffff" />
              <span>Resume</span>
            </button>
          ) : null}

          {/* Refresh Button */}
          <button
            onClick={() => fetchSandbox(false)}
            disabled={loading || actionLoading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '5px',
              background: '#21262d',
              border: '1px solid #30363d',
              color: '#c9d1d9',
              cursor: 'pointer',
            }}
            title="Refresh sandbox status"
          >
            <RefreshCw size={12} className={loading ? 'spin' : ''} />
          </button>

          {/* Terminate Button */}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            disabled={actionLoading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '5px',
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              color: '#f87171',
              cursor: 'pointer',
            }}
            title="Terminate Sandbox"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* ── Fullscreen Interactive Terminal Body ── */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative', overflow: 'hidden' }}>
        <SandboxTerminal
          sandboxId={sandboxId}
          sandboxName={sandbox?.name}
          isRunning={isRunning}
          onResume={handleResume}
          fullHeight={true}
        />
      </div>

      {/* Confirmation Dialog for Termination */}
      {showDeleteConfirm && (
        <ConfirmDialog
          title="Terminate Sandbox"
          message={`Are you sure you want to terminate sandbox "${sandbox?.name || sandboxId}"? All running processes and ephemeral state will be permanently removed.`}
          confirmLabel="Terminate"
          onCancel={() => setShowDeleteConfirm(false)}
          onConfirm={handleTerminate}
          isLoading={actionLoading}
          isDestructive
        />
      )}
    </div>
  );
}
