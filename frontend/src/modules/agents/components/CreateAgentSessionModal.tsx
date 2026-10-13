// @ts-nocheck
import React, { useState, useEffect } from 'react';
import { X, Bot, TerminalSquare, Layers, Lock, Loader2, Sparkles, Box, Check } from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import type { CreateAgentSessionPayload } from '@/modules/agents/agentRuntimeApi';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateAgentSessionPayload) => Promise<void>;
}

const AGENT_OPTIONS = [
  {
    id: 'antigravity',
    name: 'Google Antigravity',
    tag: 'agy',
    badge: 'DeepMind Core',
    color: '#38bdf8',
    bg: 'rgba(56, 189, 248, 0.1)',
    desc: 'Advanced agentic coding with workflow skills, DeepMind reasoning tools, and slash commands.',
  },
  {
    id: 'pi',
    name: 'Pi Coding Agent',
    tag: 'pi',
    badge: 'Codebase Specialist',
    color: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.1)',
    desc: 'Lightweight, rapid agent CLI for deep multi-step codebase search and precise file edits.',
  },
  {
    id: 'opencode',
    name: 'OpenCode AI',
    tag: 'opencode',
    badge: 'Multi-Model',
    color: '#10b981',
    bg: 'rgba(16, 185, 129, 0.1)',
    desc: 'Flexible multi-model code generation, automated refactoring, and test suite verification.',
  },
];

export function CreateAgentSessionModal({ isOpen, onClose, onSubmit }: Props) {
  const [title, setTitle] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<'antigravity' | 'pi' | 'opencode'>('antigravity');
  const [sandboxMode, setSandboxMode] = useState<'new' | 'existing'>('new');
  const [selectedSandboxId, setSelectedSandboxId] = useState('');
  const [availableSandboxes, setAvailableSandboxes] = useState([]);
  const [sandboxesLoading, setSandboxesLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setTitle(`Agent Task ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
      setError(null);
      setSandboxesLoading(true);
      computeApi
        .listSandboxes()
        .then((list) => {
          setAvailableSandboxes(list || []);
          if (list && list.length > 0) {
            setSelectedSandboxId(list[0].id);
          }
        })
        .catch((e) => {
          console.warn('Failed to fetch existing sandboxes:', e);
        })
        .finally(() => {
          setSandboxesLoading(false);
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Please provide a session title.');
      return;
    }
    if (sandboxMode === 'existing' && !selectedSandboxId) {
      setError('Please select an existing sandbox to attach.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        title: title.trim(),
        agent_type: selectedAgent,
        sandbox_mode: sandboxMode,
        sandbox_id: sandboxMode === 'existing' ? selectedSandboxId : undefined,
      });
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to start session');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.65)',
        zIndex: 1100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '580px',
          background: 'var(--color-surface, #161b22)',
          border: '1px solid var(--color-border, #30363d)',
          borderRadius: '10px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border, #30363d)',
            background: 'var(--color-surface-secondary, #0d1117)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <TerminalSquare size={18} color="var(--color-primary, #38bdf8)" />
            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--color-text, #f0f6fc)' }}>
              New Agent Runtime Session
            </h3>
          </div>
          <button
            onClick={onClose}
            className="ghost-icon-btn"
            style={{ color: 'var(--color-text-muted, #8b949e)', cursor: 'pointer' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {error && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                fontSize: '13px',
              }}
            >
              {error}
            </div>
          )}

          {/* Session Title */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text, #c9d1d9)' }}>
              Session Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Refactor Data Processing Pipeline"
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '6px',
                border: '1px solid var(--color-border, #30363d)',
                background: 'var(--color-surface-secondary, #0d1117)',
                color: 'var(--color-text, #f0f6fc)',
                fontSize: '13px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Select Agent Engine */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: 'var(--color-text, #c9d1d9)' }}>
              Select Agent Engine
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              {AGENT_OPTIONS.map((agent) => {
                const isSelected = selectedAgent === agent.id;
                return (
                  <div
                    key={agent.id}
                    onClick={() => setSelectedAgent(agent.id as any)}
                    style={{
                      border: `1.5px solid ${isSelected ? agent.color : 'var(--color-border, #30363d)'}`,
                      borderRadius: '8px',
                      padding: '12px',
                      cursor: 'pointer',
                      background: isSelected ? agent.bg : 'var(--color-surface-secondary, #0d1117)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                      position: 'relative',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {isSelected && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '8px',
                          right: '8px',
                          width: '16px',
                          height: '16px',
                          borderRadius: '50%',
                          background: agent.color,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#0d1117',
                        }}
                      >
                        <Check size={11} strokeWidth={3} />
                      </div>
                    )}
                    <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text, #f0f6fc)' }}>
                      {agent.name}
                    </span>
                    <span
                      style={{
                        display: 'inline-block',
                        fontSize: '10px',
                        fontFamily: 'monospace',
                        color: agent.color,
                        fontWeight: 600,
                      }}
                    >
                      CLI: {agent.tag}
                    </span>
                    <p style={{ margin: 0, fontSize: '11px', color: 'var(--color-text-muted, #8b949e)', lineHeight: '1.3' }}>
                      {agent.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sandbox Binding */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '8px', color: 'var(--color-text, #c9d1d9)' }}>
              Sandbox Runtime Binding
            </label>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {/* Option 1: New Sandbox */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  border: `1px solid ${sandboxMode === 'new' ? 'var(--color-primary, #38bdf8)' : 'var(--color-border, #30363d)'}`,
                  background: sandboxMode === 'new' ? 'rgba(56, 189, 248, 0.08)' : 'var(--color-surface-secondary, #0d1117)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="sandbox_mode"
                  checked={sandboxMode === 'new'}
                  onChange={() => setSandboxMode('new')}
                  style={{ marginTop: '3px' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text, #f0f6fc)' }}>
                    Provision New Sandbox (Recommended)
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted, #8b949e)', marginTop: '2px' }}>
                    Creates a fresh, dedicated compute sandbox running <code>compassx-sandbox-host:latest</code>.
                  </div>
                </div>
              </label>

              {/* Option 2: Existing Sandbox */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  border: `1px solid ${sandboxMode === 'existing' ? 'var(--color-primary, #38bdf8)' : 'var(--color-border, #30363d)'}`,
                  background: sandboxMode === 'existing' ? 'rgba(56, 189, 248, 0.08)' : 'var(--color-surface-secondary, #0d1117)',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="sandbox_mode"
                  checked={sandboxMode === 'existing'}
                  onChange={() => setSandboxMode('existing')}
                  style={{ marginTop: '3px' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text, #f0f6fc)' }}>
                    Attach to Existing Sandbox
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted, #8b949e)', marginTop: '2px' }}>
                    Reuse an active or suspended compute container in your workspace.
                  </div>

                  {sandboxMode === 'existing' && (
                    <div style={{ marginTop: '10px' }}>
                      {sandboxesLoading ? (
                        <div style={{ fontSize: '12px', color: '#8b949e' }}>Loading available sandboxes...</div>
                      ) : availableSandboxes.length === 0 ? (
                        <div style={{ fontSize: '12px', color: '#ef4444' }}>
                          No existing sandboxes found. Please provision a new sandbox.
                        </div>
                      ) : (
                        <select
                          value={selectedSandboxId}
                          onChange={(e) => setSelectedSandboxId(e.target.value)}
                          style={{
                            width: '100%',
                            padding: '8px 10px',
                            borderRadius: '5px',
                            border: '1px solid var(--color-border, #30363d)',
                            background: 'var(--color-surface, #161b22)',
                            color: 'var(--color-text, #f0f6fc)',
                            fontSize: '12px',
                          }}
                        >
                          {availableSandboxes.map((sb) => (
                            <option key={sb.id} value={sb.id}>
                              {sb.name} ({sb.id}) — {sb.status} [{sb.consumer_module || 'sandbox'}]
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  )}
                </div>
              </label>
            </div>

            {/* Immutability Notice Callout */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '10px',
                padding: '8px 12px',
                borderRadius: '5px',
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                fontSize: '11px',
                color: '#fbbf24',
              }}
            >
              <Lock size={12} flexShrink={0} />
              <span>
                <strong>Session Lock:</strong> Once initialized, this sandbox is permanently bound to this session to preserve working directory files, git history, and process state.
              </span>
            </div>
          </div>

          {/* Footer Controls */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '10px',
              paddingTop: '8px',
              borderTop: '1px solid var(--color-border, #30363d)',
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                background: 'transparent',
                border: '1px solid var(--color-border, #30363d)',
                color: 'var(--color-text, #f0f6fc)',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '6px',
                background: '#238636',
                border: 'none',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? (
                <>
                  <Loader2 size={14} className="spin" /> Starting Session...
                </>
              ) : (
                <>
                  <Sparkles size={14} /> Start Agent Session
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
