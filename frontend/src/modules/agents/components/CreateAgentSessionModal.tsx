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
        background: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(4px)',
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
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          boxShadow: '0 20px 48px rgba(0, 0, 0, 0.12)',
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
            borderBottom: '1px solid #e2e8f0',
            background: '#ffffff',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
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
              <TerminalSquare size={17} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700, color: '#0f172a' }}>
                New Agent Runtime Session
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: '0.74rem', color: '#64748b' }}>
                Spawn an isolated agent session bound to container compute
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              padding: 5,
              color: '#64748b',
              cursor: 'pointer',
              borderRadius: 6,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {error && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: '#dc2626',
                fontSize: '0.82rem',
              }}
            >
              {error}
            </div>
          )}

          {/* Session Title */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '6px', color: '#334155' }}>
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
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#0f172a',
                fontSize: '0.85rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Select Agent Engine */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '8px', color: '#334155' }}>
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
                      border: `1.5px solid ${isSelected ? agent.color : '#e2e8f0'}`,
                      borderRadius: '8px',
                      padding: '12px',
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(56, 189, 248, 0.08)' : '#f8fafc',
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
                          color: '#ffffff',
                        }}
                      >
                        <Check size={11} strokeWidth={3} />
                      </div>
                    )}
                    <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#0f172a' }}>
                      {agent.name}
                    </span>
                    <span
                      style={{
                        display: 'inline-block',
                        fontSize: '0.68rem',
                        fontFamily: 'monospace',
                        color: agent.color,
                        fontWeight: 600,
                      }}
                    >
                      CLI: {agent.tag}
                    </span>
                    <p style={{ margin: 0, fontSize: '0.74rem', color: '#64748b', lineHeight: '1.3' }}>
                      {agent.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sandbox Binding */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '8px', color: '#334155' }}>
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
                  border: `1px solid ${sandboxMode === 'new' ? '#2563eb' : '#e2e8f0'}`,
                  background: sandboxMode === 'new' ? 'rgba(37, 99, 235, 0.05)' : '#f8fafc',
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
                  <div style={{ fontSize: '0.84rem', fontWeight: 600, color: '#0f172a' }}>
                    Provision New Sandbox (Recommended)
                  </div>
                  <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
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
                  border: `1px solid ${sandboxMode === 'existing' ? '#2563eb' : '#e2e8f0'}`,
                  background: sandboxMode === 'existing' ? 'rgba(37, 99, 235, 0.05)' : '#f8fafc',
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
                  <div style={{ fontSize: '0.84rem', fontWeight: 600, color: '#0f172a' }}>
                    Attach to Existing Sandbox
                  </div>
                  <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
                    Reuse an active or suspended compute container in your workspace.
                  </div>

                  {sandboxMode === 'existing' && (
                    <div style={{ marginTop: '10px' }}>
                      {sandboxesLoading ? (
                        <div style={{ fontSize: '0.78rem', color: '#64748b' }}>Loading available sandboxes...</div>
                      ) : availableSandboxes.length === 0 ? (
                        <div style={{ fontSize: '0.78rem', color: '#dc2626' }}>
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
                            border: '1px solid #cbd5e1',
                            background: '#ffffff',
                            color: '#0f172a',
                            fontSize: '0.82rem',
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
                background: '#fffbeb',
                border: '1px solid #fde68a',
                fontSize: '0.74rem',
                color: '#b45309',
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
              borderTop: '1px solid #e2e8f0',
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                color: '#334155',
                fontSize: '0.82rem',
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
                background: '#2563eb',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.82rem',
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
