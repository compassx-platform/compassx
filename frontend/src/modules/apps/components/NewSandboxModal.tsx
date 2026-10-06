import React, { useState } from 'react';
import { X, GitBranch, Layers, GitFork } from 'lucide-react';
import { useToast } from '@/lib/toast';
import { useCreateDevWorkspace, useActivateDevWorkspace } from '../hooks/useApps';

interface NewSandboxModalProps {
  isOpen: boolean;
  onClose: () => void;
  appId: string;
  appName?: string;
  onCreated?: (workspaceId: string) => void;
  activeBranch?: string;
  defaultBaseBranch?: string;
}

export function NewSandboxModal({
  isOpen,
  onClose,
  appId,
  appName,
  onCreated,
  activeBranch,
  defaultBaseBranch = 'main',
}: NewSandboxModalProps) {
  const toast = useToast();
  const createWorkspaceMutation = useCreateDevWorkspace();
  const activateWorkspaceMutation = useActivateDevWorkspace();

  const [sandboxName, setSandboxName] = useState('');
  const [gitBranch, setGitBranch] = useState('');
  const [baseBranchOption, setBaseBranchOption] = useState<'main' | 'current' | 'custom'>('main');
  const [customBaseBranch, setCustomBaseBranch] = useState('');
  const [fetchRemote, setFetchRemote] = useState(true);
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

    let baseBranchToUse = defaultBaseBranch || 'main';
    if (baseBranchOption === 'current') {
      baseBranchToUse = activeBranch || defaultBaseBranch || 'main';
    } else if (baseBranchOption === 'custom') {
      baseBranchToUse = customBaseBranch.trim() || defaultBaseBranch || 'main';
    }

    try {
      setIsSubmitting(true);
      const created = await createWorkspaceMutation.mutateAsync({
        appId,
        name: cleanName,
        gitBranch: branchToUse,
        baseBranch: baseBranchToUse,
        fetchRemote: fetchRemote,
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
        background: 'rgba(15, 23, 42, 0.45)',
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
          background: '#ffffff',
          border: '1px solid #e5e7eb',
          borderRadius: 12,
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
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
            borderBottom: '1px solid #f1f5f9',
            background: '#ffffff',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: '#EBF2FF',
                border: '1px solid #dbeafe',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#1B6EF3',
              }}
            >
              <Layers size={17} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 650, color: '#0f172a' }}>
                New Dev Sandbox
              </h3>
              <p style={{ margin: 0, fontSize: '0.74rem', color: '#64748b' }}>
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
              padding: 5,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.15s ease, color 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
              e.currentTarget.style.color = '#0f172a';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = '#64748b';
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
                color: '#334155',
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
                borderRadius: 7,
                background: '#ffffff',
                border: '1px solid #d1d5db',
                color: '#0f172a',
                fontSize: '0.86rem',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = '#1B6EF3';
                e.currentTarget.style.boxShadow = '0 0 0 3px rgba(27, 110, 243, 0.12)';
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = '#d1d5db';
                e.currentTarget.style.boxShadow = 'none';
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
                color: '#334155',
                marginBottom: 6,
              }}
            >
              <GitBranch size={13} color="#64748b" />
              New Git Branch
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
                borderRadius: 7,
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                color: '#0f172a',
                fontSize: '0.86rem',
                outline: 'none',
                boxSizing: 'border-box',
                fontFamily: 'ui-monospace, SFMono-Regular, monospace',
              }}
            />
          </div>

          {/* Base Branch / Fork From Field */}
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#334155',
                marginBottom: 6,
              }}
            >
              <GitFork size={13} color="#64748b" />
              Base Branch (Fork From)
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {/* Option 1: Remote Main */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 10px',
                  borderRadius: 7,
                  border: baseBranchOption === 'main' ? '1px solid #1B6EF3' : '1px solid #e2e8f0',
                  background: baseBranchOption === 'main' ? '#f0f7ff' : '#ffffff',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                  color: '#1e293b',
                  transition: 'all 0.15s ease',
                }}
              >
                <input
                  type="radio"
                  name="baseBranchOption"
                  value="main"
                  checked={baseBranchOption === 'main'}
                  onChange={() => setBaseBranchOption('main')}
                  disabled={isSubmitting}
                  style={{ accentColor: '#1B6EF3', cursor: 'pointer' }}
                />
                <span style={{ fontWeight: 600 }}>Remote {defaultBaseBranch || 'main'}</span>
                <span style={{ color: '#64748b', fontSize: '0.72rem' }}>
                  (origin/{defaultBaseBranch || 'main'}) - Recommended
                </span>
              </label>

              {/* Option 2: Current sandbox branch (if available and different from main) */}
              {activeBranch && activeBranch !== 'main' && activeBranch !== (defaultBaseBranch || 'main') && (
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '7px 10px',
                    borderRadius: 7,
                    border: baseBranchOption === 'current' ? '1px solid #1B6EF3' : '1px solid #e2e8f0',
                    background: baseBranchOption === 'current' ? '#f0f7ff' : '#ffffff',
                    cursor: 'pointer',
                    fontSize: '0.78rem',
                    color: '#1e293b',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <input
                    type="radio"
                    name="baseBranchOption"
                    value="current"
                    checked={baseBranchOption === 'current'}
                    onChange={() => setBaseBranchOption('current')}
                    disabled={isSubmitting}
                    style={{ accentColor: '#1B6EF3', cursor: 'pointer' }}
                  />
                  <span style={{ fontWeight: 600 }}>Current Sandbox</span>
                  <span style={{ color: '#64748b', fontSize: '0.72rem', fontFamily: 'monospace' }}>
                    ({activeBranch})
                  </span>
                </label>
              )}

              {/* Option 3: Custom ref */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 10px',
                  borderRadius: 7,
                  border: baseBranchOption === 'custom' ? '1px solid #1B6EF3' : '1px solid #e2e8f0',
                  background: baseBranchOption === 'custom' ? '#f0f7ff' : '#ffffff',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                  color: '#1e293b',
                  transition: 'all 0.15s ease',
                }}
              >
                <input
                  type="radio"
                  name="baseBranchOption"
                  value="custom"
                  checked={baseBranchOption === 'custom'}
                  onChange={() => setBaseBranchOption('custom')}
                  disabled={isSubmitting}
                  style={{ accentColor: '#1B6EF3', cursor: 'pointer' }}
                />
                <span>Custom branch or tag ref</span>
              </label>

              {baseBranchOption === 'custom' && (
                <input
                  type="text"
                  value={customBaseBranch}
                  onChange={(e) => setCustomBaseBranch(e.target.value)}
                  placeholder="e.g. origin/develop, release-v2"
                  disabled={isSubmitting}
                  style={{
                    marginTop: 2,
                    padding: '7px 10px',
                    borderRadius: 7,
                    background: '#ffffff',
                    border: '1px solid #d1d5db',
                    color: '#0f172a',
                    fontSize: '0.8rem',
                    fontFamily: 'monospace',
                    outline: 'none',
                  }}
                />
              )}
            </div>
          </div>

          {/* Fetch Remote Checkbox */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 12px',
              borderRadius: 8,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              marginBottom: 16,
              cursor: 'pointer',
            }}
            onClick={() => !isSubmitting && setFetchRemote(!fetchRemote)}
          >
            <input
              type="checkbox"
              id="fetch-remote"
              checked={fetchRemote}
              onChange={(e) => setFetchRemote(e.target.checked)}
              disabled={isSubmitting}
              style={{ cursor: 'pointer', accentColor: '#1B6EF3' }}
            />
            <label
              htmlFor="fetch-remote"
              style={{
                fontSize: '0.77rem',
                fontWeight: 500,
                color: '#334155',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              Fetch latest commits from remote (git fetch origin) before creating
            </label>
          </div>

          {/* Switch Immediately Checkbox */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 12px',
              borderRadius: 8,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
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
              style={{ cursor: 'pointer', accentColor: '#1B6EF3' }}
            />
            <label
              htmlFor="switch-immediately"
              style={{
                fontSize: '0.78rem',
                fontWeight: 500,
                color: '#334155',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              Switch to this sandbox immediately (repoints dev server in &lt; 1s)
            </label>
          </div>

          {/* Footer Actions */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 10,
              paddingTop: 4,
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              style={{
                padding: '7px 14px',
                borderRadius: 6,
                border: '1px solid #d1d5db',
                background: '#ffffff',
                color: '#374151',
                fontSize: '0.8rem',
                fontWeight: 500,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = '#f9fafb';
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) e.currentTarget.style.background = '#ffffff';
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !sandboxName.trim()}
              style={{
                padding: '7px 18px',
                borderRadius: 6,
                border: 'none',
                background: '#1B6EF3',
                color: '#ffffff',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: isSubmitting || !sandboxName.trim() ? 'not-allowed' : 'pointer',
                opacity: isSubmitting || !sandboxName.trim() ? 0.6 : 1,
                transition: 'background 0.15s ease',
                boxShadow: '0 1px 2px rgba(27, 110, 243, 0.2)',
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting && sandboxName.trim()) e.currentTarget.style.background = '#1558C7';
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting && sandboxName.trim()) e.currentTarget.style.background = '#1B6EF3';
              }}
            >
              {isSubmitting ? 'Creating Sandbox...' : 'Create Sandbox'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
