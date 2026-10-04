import React, { useState, useEffect } from 'react';
import {
  X,
  Terminal,
  Lock,
  Sparkles,
  Zap,
  Bot,
  Loader2,
  Check,
  Cpu,
} from 'lucide-react';
import { AGENT_OPTIONS, type SupportedAgent } from '../pages/AppBuildPage';
import { useAppDevModels } from '../hooks/useApps';

interface NewSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (title: string, agent: SupportedAgent, model?: string) => Promise<void> | void;
  appId?: string;
  isCreating?: boolean;
}

export function NewSessionModal({
  isOpen,
  onClose,
  onSubmit,
  appId,
  isCreating = false,
}: NewSessionModalProps) {
  const [selectedAgent, setSelectedAgent] = useState<SupportedAgent>('opencode');
  const [title, setTitle] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('');

  const { data: models = [], isLoading: isLoadingModels } = useAppDevModels(appId);

  // Set default model when models load
  useEffect(() => {
    if (models.length > 0 && !selectedModel) {
      const defaultMod = models.find((m) => m.is_default) || models[0];
      if (defaultMod) {
        setSelectedModel(defaultMod.id);
      }
    }
  }, [models, selectedModel]);

  // Reset or set default title when opened or agent changes
  useEffect(() => {
    if (isOpen) {
      const agentObj = AGENT_OPTIONS.find((a) => a.id === selectedAgent);
      const defaultName = `Session with ${agentObj?.name || 'Agent'} (${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`;
      if (!title.trim()) {
        setTitle(defaultName);
      }
    }
  }, [isOpen, selectedAgent]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim() || `Session (${selectedAgent})`;
    onSubmit(cleanTitle, selectedAgent, selectedModel || undefined);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.72)',
        backdropFilter: 'blur(4px)',
        padding: '16px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isCreating) {
          onClose();
        }
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '540px',
          background: 'var(--color-surface, #1e293b)',
          border: '1px solid var(--color-border, #334155)',
          borderRadius: '12px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.65)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          animation: 'modalSlideIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border, #334155)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(15, 23, 42, 0.5)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: 'rgba(99, 102, 241, 0.15)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8',
              }}
            >
              <Terminal size={17} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: '0.98rem',
                  fontWeight: 650,
                  color: 'var(--color-text, #f8fafc)',
                  margin: 0,
                }}
              >
                Create New Dev Session
              </h2>
              <p
                style={{
                  fontSize: '0.74rem',
                  color: 'var(--color-text-muted, #94a3b8)',
                  margin: '2px 0 0 0',
                }}
              >
                Spawn an isolated, persistent AI terminal session
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isCreating}
            style={{
              background: 'transparent',
              border: 'none',
              padding: 6,
              color: 'var(--color-text-muted, #94a3b8)',
              cursor: isCreating ? 'not-allowed' : 'pointer',
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
        <form onSubmit={handleSubmit}>
          <div
            style={{
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: 18,
            }}
          >
            {/* Session Title */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color: 'var(--color-text, #f8fafc)',
                  marginBottom: 6,
                }}
              >
                Session Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Implement authentication, Fix styling bug..."
                required
                disabled={isCreating}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--color-border, #334155)',
                  background: 'rgba(15, 23, 42, 0.7)',
                  color: 'var(--color-text, #f8fafc)',
                  fontSize: '0.85rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {/* Agent Selection Cards */}
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 8,
                }}
              >
                <label
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    color: 'var(--color-text, #f8fafc)',
                    margin: 0,
                  }}
                >
                  Select AI Coding Agent
                </label>
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: 'var(--color-text-muted, #94a3b8)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <Lock size={10} color="#f59e0b" />
                  Locked for this session
                </span>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 10,
                }}
              >
                {AGENT_OPTIONS.map((opt) => {
                  const isSelected = selectedAgent === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => !isCreating && setSelectedAgent(opt.id)}
                      style={{
                        padding: '12px 10px',
                        borderRadius: 8,
                        border: isSelected
                          ? `1.5px solid ${opt.color}`
                          : '1px solid var(--color-border, #334155)',
                        background: isSelected
                          ? opt.accentBg
                          : 'rgba(15, 23, 42, 0.45)',
                        cursor: isCreating ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease',
                        position: 'relative',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: 4,
                            background: opt.color,
                            color: '#0f172a',
                            letterSpacing: '0.4px',
                          }}
                        >
                          {opt.badge}
                        </span>
                        {isSelected && (
                          <div
                            style={{
                              width: 14,
                              height: 14,
                              borderRadius: '50%',
                              background: opt.color,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#0f172a',
                            }}
                          >
                            <Check size={10} strokeWidth={3} />
                          </div>
                        )}
                      </div>

                      <div
                        style={{
                          fontSize: '0.86rem',
                          fontWeight: 650,
                          color: isSelected ? opt.color : 'var(--color-text, #f8fafc)',
                        }}
                      >
                        {opt.name}
                      </div>

                      <div
                        style={{
                          fontSize: '0.68rem',
                          color: 'var(--color-text-muted, #94a3b8)',
                          lineHeight: 1.3,
                          flex: 1,
                        }}
                      >
                        {opt.tagline}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* AI Model Selection */}
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 6,
                }}
              >
                <label
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    color: 'var(--color-text, #f8fafc)',
                    margin: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <Cpu size={14} color="#818cf8" />
                  AI Gateway Model
                </label>
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: 'var(--color-text-muted, #94a3b8)',
                  }}
                >
                  Governed via CompassX AI Gateway
                </span>
              </div>

              {isLoadingModels ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '9px 12px',
                    borderRadius: 6,
                    background: 'rgba(15, 23, 42, 0.7)',
                    border: '1px solid var(--color-border, #334155)',
                    color: 'var(--color-text-muted, #94a3b8)',
                    fontSize: '0.8rem',
                  }}
                >
                  <Loader2 size={13} className="spin" />
                  <span>Loading available models...</span>
                </div>
              ) : (
                <div style={{ position: 'relative' }}>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    disabled={isCreating}
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--color-border, #334155)',
                      background: 'rgba(15, 23, 42, 0.7)',
                      color: 'var(--color-text, #f8fafc)',
                      fontSize: '0.84rem',
                      outline: 'none',
                      boxSizing: 'border-box',
                      cursor: isCreating ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {models.map((m) => (
                      <option key={m.id} value={m.id} style={{ background: '#1e293b', color: '#f8fafc' }}>
                        {m.name} {m.is_default ? '(Default)' : ''} {m.provider ? `• ${m.provider}` : ''}
                      </option>
                    ))}
                    {models.length === 0 && (
                      <option value="gpt-5.4-mini" style={{ background: '#1e293b', color: '#f8fafc' }}>
                        gpt-5.4-mini (Default)
                      </option>
                    )}
                  </select>
                </div>
              )}
            </div>

            {/* Architecture / Policy Callout */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                color: '#fde68a',
                fontSize: '0.74rem',
                lineHeight: 1.45,
              }}
            >
              <Lock size={15} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>1 Agent per Session Policy:</strong> The selected agent is permanently bound to this session's background tmux container runtime. To switch to a different agent, start a new session.
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div
            style={{
              padding: '12px 20px',
              borderTop: '1px solid var(--color-border, #334155)',
              background: 'rgba(15, 23, 42, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 10,
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={isCreating}
              style={{
                padding: '7px 14px',
                borderRadius: 6,
                border: '1px solid var(--color-border, #334155)',
                background: 'transparent',
                color: 'var(--color-text-muted, #94a3b8)',
                fontSize: '0.8rem',
                fontWeight: 500,
                cursor: isCreating ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating || !title.trim()}
              style={{
                padding: '7px 18px',
                borderRadius: 6,
                border: 'none',
                background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                color: '#ffffff',
                fontSize: '0.8rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                cursor: isCreating || !title.trim() ? 'not-allowed' : 'pointer',
                opacity: isCreating || !title.trim() ? 0.6 : 1,
                boxShadow: '0 2px 8px rgba(99, 102, 241, 0.35)',
              }}
            >
              {isCreating ? (
                <>
                  <Loader2 size={13} className="spin" />
                  <span>Creating Session...</span>
                </>
              ) : (
                <>
                  <Sparkles size={13} />
                  <span>Create Session</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
