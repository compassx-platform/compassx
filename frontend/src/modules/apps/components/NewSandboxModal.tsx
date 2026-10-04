import React, { useState } from 'react';
import { X, GitBranch, Layers, Sparkles, Loader2 } from 'lucide-react';
import { useToast } from '@/lib/toast';
import { useCreateDevWorkspace, useActivateDevWorkspace } from '../hooks/useApps';

interface NewSandboxModalProps {
  isOpen: boolean;
  onClose: () => void;
  appId: string;
  appName?: string;
  onCreated?: (workspaceId: string) => void;
}

export function NewSandboxModal({
  isOpen,
  onClose,
  appId,
  appName,
  onCreated,
}: NewSandboxModalProps) {
  const toast = useToast();
  const createWorkspaceMutation = useCreateDevWorkspace();
  const activateWorkspaceMutation = useActivateDevWorkspace();

  const [sandboxName, setSandboxName] = useState('');
  const [gitBranch, setGitBranch] = useState('');
  const [switchImmediately, setSwitchImmediately] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleNameChange = (val: string) => {
    setSandboxName(val);
    const sanitized = val.trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-');
    setGitBranch(sanitized ? `dev/${sanitized}` : '');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sandboxName.trim()) {
      toast.error('Please enter a sandbox name');
      return;
    }

    const cleanName = sandboxName.trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-');
    const branchToUse = gitBranch.trim() || `dev/${cleanName}`;

    try {
      setIsSubmitting(true);
      const created = await createWorkspaceMutation.mutateAsync({
        appId,
        name: cleanName,
        gitBranch: branchToUse,
      });

      if (switchImmediately && created?.id) {
        await activateWorkspaceMutation.mutateAsync({
          appId,
          workspaceId: created.id,
        });
        toast.success(`Sandbox "${cleanName}" created and activated.`);
      } else {
        toast.success(`Sandbox "${cleanName}" created on branch "${branchToUse}".`);
      }

      onCreated?.(created.id);
      setSandboxName('');
      setGitBranch('');
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create sandbox');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1050,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(4px)',
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 480,
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 12,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'fadeIn 0.15s ease-out',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid #1e293b',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: 'rgba(99, 102, 241, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8',
              }}
            >
              <Layers size={18} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 600, color: '#f8fafc' }}>
                New Dev Sandbox
              </h3>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#94a3b8' }}>
                Create an isolated feature workspace (Git worktree) for {appName || 'this app'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              padding: 4,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} style={{ padding: '20px' }}>
          {/* Sandbox Name Field */}
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#e2e8f0',
                marginBottom: 6,
              }}
            >
              Sandbox / Feature Name <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="text"
              required
              autoFocus
              value={sandboxName}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="e.g. auth-flow, payment-gateway, fix-navbar"
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 8,
                background: '#1e293b',
                border: '1px solid #334155',
                color: '#f8fafc',
                fontSize: '0.86rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <span style={{ display: 'block', fontSize: '0.72rem', color: '#64748b', marginTop: 4 }}>
              This will create an isolated worktree folder inside the dev container.
            </span>
          </div>

          {/* Git Branch Field */}
          <div style={{ marginBottom: 18 }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#e2e8f0',
                marginBottom: 6,
              }}
            >
              <GitBranch size={13} color="#818cf8" />
              Git Branch
            </label>
            <input
              type="text"
              value={gitBranch}
              onChange={(e) => setGitBranch(e.target.value)}
              placeholder="dev/feature-name"
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 8,
                background: '#1e293b',
                border: '1px solid #334155',
                color: '#f8fafc',
                fontSize: '0.86rem',
                outline: 'none',
                boxSizing: 'border-box',
                fontFamily: 'ui-monospace, SFMono-Regular, monospace',
              }}
            />
          </div>

          {/* Switch Immediately Checkbox */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 12px',
              borderRadius: 8,
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
              marginBottom: 20,
              cursor: 'pointer',
            }}
            onClick={() => setSwitchImmediately(!switchImmediately)}
          >
            <input
              type="checkbox"
              id="switch-immediately"
              checked={switchImmediately}
              onChange={(e) => setSwitchImmediately(e.target.checked)}
              disabled={isSubmitting}
              style={{ cursor: 'pointer', accentColor: '#6366f1' }}
            />
            <label
              htmlFor="switch-immediately"
              style={{
                fontSize: '0.78rem',
                fontWeight: 500,
                color: '#c7d2fe',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              Switch to this sandbox immediately (repoints dev server in &lt; 1s)
            </label>
          </div>

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              style={{
                padding: '8px 14px',
                borderRadius: 7,
                border: '1px solid #334155',
                background: 'transparent',
                color: '#94a3b8',
                fontSize: '0.82rem',
                fontWeight: 500,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !sandboxName.trim()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                borderRadius: 7,
                border: 'none',
                background: 'linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)',
                color: '#ffffff',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: isSubmitting || !sandboxName.trim() ? 'not-allowed' : 'pointer',
                opacity: isSubmitting || !sandboxName.trim() ? 0.6 : 1,
                boxShadow: '0 2px 4px rgba(79, 70, 229, 0.3)',
              }}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={14} className="spin" />
                  <span>Creating Sandbox...</span>
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>Create Sandbox</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
