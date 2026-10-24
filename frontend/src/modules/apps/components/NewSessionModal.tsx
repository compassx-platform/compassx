import React, { useState, useEffect } from 'react';
import {
  X,
  Terminal,
  Loader2,
} from 'lucide-react';
import { AGENT_OPTIONS, type SupportedAgent } from '../pages/AppBuildPage';

interface NewSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (title: string, agent: SupportedAgent) => Promise<void> | void;
  appId?: string;
  isCreating?: boolean;
}

export function NewSessionModal({
  isOpen,
  onClose,
  onSubmit,
  appId: _appId,
  isCreating = false,
}: NewSessionModalProps) {
  const [selectedAgent, setSelectedAgent] = useState<SupportedAgent>('opencode');
  const [title, setTitle] = useState('');
  const [isCustomTitle, setIsCustomTitle] = useState(false);

  const getDefaultTitleForAgent = (agentId: SupportedAgent) => {
    const agentObj = AGENT_OPTIONS.find((a) => a.id === agentId);
    return `Session with ${agentObj?.name || 'Agent'}`;
  };

  // Reset to default title for current agent when modal opens
  useEffect(() => {
    if (isOpen) {
      setIsCustomTitle(false);
      setTitle(getDefaultTitleForAgent(selectedAgent));
    }
  }, [isOpen]);

  const handleAgentChange = (newAgent: SupportedAgent) => {
    setSelectedAgent(newAgent);
    if (!isCustomTitle) {
      setTitle(getDefaultTitleForAgent(newAgent));
    }
  };

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim() || getDefaultTitleForAgent(selectedAgent);
    onSubmit(cleanTitle, selectedAgent);
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
        background: 'rgba(15, 23, 42, 0.45)',
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
          maxWidth: '480px',
          background: '#ffffff',
          border: '1px solid #e5e7eb',
          borderRadius: '12px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
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
            borderBottom: '1px solid #f1f5f9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
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
              <Terminal size={17} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: '0.98rem',
                  fontWeight: 650,
                  color: '#0f172a',
                  margin: 0,
                }}
              >
                Create New Dev Session
              </h2>
              <p
                style={{
                  fontSize: '0.74rem',
                  color: '#64748b',
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
              padding: 5,
              color: '#64748b',
              cursor: isCreating ? 'not-allowed' : 'pointer',
              borderRadius: 6,
              display: 'inline-flex',
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
                  color: '#334155',
                  marginBottom: 6,
                }}
              >
                Session Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setIsCustomTitle(e.target.value.trim().length > 0);
                }}
                placeholder="e.g. Implement authentication, Fix styling bug..."
                required
                disabled={isCreating}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 7,
                  border: '1px solid #d1d5db',
                  background: '#ffffff',
                  color: '#0f172a',
                  fontSize: '0.85rem',
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
            </div>

            {/* Select AI Coding Agent */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color: '#334155',
                  marginBottom: 6,
                }}
              >
                Select AI Coding Agent
              </label>
              <select
                value={selectedAgent}
                onChange={(e) => handleAgentChange(e.target.value as SupportedAgent)}
                disabled={isCreating}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 7,
                  border: '1px solid #d1d5db',
                  background: '#ffffff',
                  color: '#0f172a',
                  fontSize: '0.84rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                  cursor: isCreating ? 'not-allowed' : 'pointer',
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
              >
                {AGENT_OPTIONS.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Footer Actions */}
          <div
            style={{
              padding: '12px 20px',
              borderTop: '1px solid #f1f5f9',
              background: '#fafafa',
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
                border: '1px solid #d1d5db',
                background: '#ffffff',
                color: '#374151',
                fontSize: '0.8rem',
                fontWeight: 500,
                cursor: isCreating ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isCreating) e.currentTarget.style.background = '#f9fafb';
              }}
              onMouseLeave={(e) => {
                if (!isCreating) e.currentTarget.style.background = '#ffffff';
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
                background: '#1B6EF3',
                color: '#ffffff',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: isCreating || !title.trim() ? 'not-allowed' : 'pointer',
                opacity: isCreating || !title.trim() ? 0.6 : 1,
                transition: 'background 0.15s ease',
                boxShadow: '0 1px 2px rgba(27, 110, 243, 0.2)',
              }}
              onMouseEnter={(e) => {
                if (!isCreating && title.trim()) e.currentTarget.style.background = '#1558C7';
              }}
              onMouseLeave={(e) => {
                if (!isCreating && title.trim()) e.currentTarget.style.background = '#1B6EF3';
              }}
            >
              {isCreating ? 'Creating Session...' : 'Create Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
