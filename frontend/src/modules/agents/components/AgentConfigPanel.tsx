import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Settings } from 'lucide-react';

export interface AgentManifestData {
  agent_id: string;
  display_name: string;
  base_profile: 'build_agent' | 'reactive_agent' | 'custom';
  capabilities: {
    planning: {
      enabled: boolean;
      router_thresholds: string;
      max_retry_attempts: number;
    };
    checkpoints: {
      enabled: boolean;
      gated_write_categories: string[];
    };
    document_upload: {
      enabled: boolean;
      accepted_types: string[];
    };
    artifact_visibility: {
      enabled: boolean;
      link_resolution: boolean;
      diff_capture: boolean;
    };
  };
}

const WRITE_CATEGORIES = ['catalog', 'storage', 'scheduler', 'dashboard', 'app'];
const FILE_TYPES = ['pdf', 'docx', 'xlsx', 'csv', 'txt', 'md', 'json', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'];

const DEFAULT_MANIFEST: AgentManifestData = {
  agent_id: 'custom-agent',
  display_name: 'Custom Agent',
  base_profile: 'reactive_agent',
  capabilities: {
    planning: { enabled: false, router_thresholds: 'default', max_retry_attempts: 3 },
    checkpoints: { enabled: false, gated_write_categories: [] },
    document_upload: { enabled: true, accepted_types: ['pdf', 'docx', 'xlsx', 'csv', 'txt', 'md', 'json', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'] },
    artifact_visibility: { enabled: true, link_resolution: true, diff_capture: true },
  },
};

interface AgentConfigPanelProps {
  manifest: AgentManifestData;
  onChange: (manifest: AgentManifestData) => void;
}

export const AgentConfigPanel: React.FC<AgentConfigPanelProps> = ({ manifest: rawManifest, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);

  // Normalize incoming manifest prop to guarantee capabilities structure exists
  const manifest: AgentManifestData = {
    ...DEFAULT_MANIFEST,
    ...rawManifest,
    base_profile: rawManifest?.base_profile || DEFAULT_MANIFEST.base_profile,
    capabilities: {
      planning: {
        ...DEFAULT_MANIFEST.capabilities.planning,
        ...rawManifest?.capabilities?.planning,
      },
      checkpoints: {
        ...DEFAULT_MANIFEST.capabilities.checkpoints,
        ...rawManifest?.capabilities?.checkpoints,
        gated_write_categories: rawManifest?.capabilities?.checkpoints?.gated_write_categories ?? DEFAULT_MANIFEST.capabilities.checkpoints.gated_write_categories,
      },
      document_upload: {
        ...DEFAULT_MANIFEST.capabilities.document_upload,
        ...rawManifest?.capabilities?.document_upload,
        accepted_types: rawManifest?.capabilities?.document_upload?.accepted_types ?? DEFAULT_MANIFEST.capabilities.document_upload.accepted_types,
      },
      artifact_visibility: {
        ...DEFAULT_MANIFEST.capabilities.artifact_visibility,
        ...rawManifest?.capabilities?.artifact_visibility,
      },
    },
  };

  const updateManifest = (next: AgentManifestData) => {
    onChange(next);
  };

  const handleProfileChange = (profile: 'build_agent' | 'reactive_agent' | 'custom') => {
    if (profile === 'reactive_agent') {
      updateManifest({
        ...manifest,
        base_profile: profile,
        capabilities: {
          ...manifest.capabilities,
          planning: { ...manifest.capabilities.planning, enabled: false },
          checkpoints: { enabled: false, gated_write_categories: [] },
        },
      });
    } else if (profile === 'build_agent') {
      updateManifest({
        ...manifest,
        base_profile: profile,
        capabilities: {
          ...manifest.capabilities,
          planning: { ...manifest.capabilities.planning, enabled: true },
          checkpoints: { enabled: true, gated_write_categories: [...WRITE_CATEGORIES] },
        },
      });
    } else {
      updateManifest({ ...manifest, base_profile: profile });
    }
  };

  const toggleCategory = (cat: string) => {
    const current = manifest.capabilities.checkpoints.gated_write_categories;
    const next = current.includes(cat) ? current.filter((c) => c !== cat) : [...current, cat];
    updateManifest({
      ...manifest,
      capabilities: {
        ...manifest.capabilities,
        checkpoints: { ...manifest.capabilities.checkpoints, gated_write_categories: next },
      },
    });
  };

  const toggleFileType = (type: string) => {
    const current = manifest.capabilities.document_upload.accepted_types;
    const next = current.includes(type) ? current.filter((t) => t !== type) : [...current, type];
    updateManifest({
      ...manifest,
      capabilities: {
        ...manifest.capabilities,
        document_upload: { ...manifest.capabilities.document_upload, accepted_types: next },
      },
    });
  };

  return (
    <div
      style={{
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
        background: 'var(--color-surface)',
        overflow: 'hidden',
        transition: 'all 0.2s ease',
      }}
    >
      {/* Expander Header */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          padding: '14px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--color-text)',
          textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Settings size={18} style={{ color: 'var(--color-primary)' }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>Agent Execution Profile</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
              Configure autonomous planning, write-checkpoint gates, and capability rules
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontSize: '0.75rem',
              padding: '3px 8px',
              borderRadius: '4px',
              fontWeight: 500,
              background: 'var(--color-background)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-primary)',
            }}
          >
            {manifest.base_profile === 'build_agent'
              ? 'Build Agent'
              : manifest.base_profile === 'reactive_agent'
              ? 'Reactive Agent'
              : 'Custom'}
          </span>
          {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </div>
      </button>

      {/* Expander Content */}
      {isOpen && (
        <div
          style={{
            padding: '16px',
            borderTop: '1px solid var(--color-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            background: 'var(--color-background)',
          }}
        >
          {/* Base Profile Selector */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Execution Preset Profile</label>
            <select
              className="form-input"
              value={manifest.base_profile}
              onChange={(e) => handleProfileChange(e.target.value as any)}
            >
              <option value="build_agent">Build Agent (Full autonomous multi-step planning & gated writes)</option>
              <option value="reactive_agent">Reactive Agent (Single-turn read-only, no planning)</option>
              <option value="custom">Custom Configuration</option>
            </select>
          </div>

          {/* Planning Capability */}
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 6 }}>Planning & Routing Engine</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem' }}>
              <input
                type="checkbox"
                checked={manifest.capabilities.planning.enabled}
                onChange={(e) =>
                  updateManifest({
                    ...manifest,
                    capabilities: {
                      ...manifest.capabilities,
                      planning: { ...manifest.capabilities.planning, enabled: e.target.checked },
                    },
                  })
                }
              />
              Enable Autonomous Multi-Stage Request Router & Planning Machinery
            </label>
          </div>

          {/* Checkpoints & Write-Gating */}
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 6 }}>Write Gating & Safety Checkpoints (2-Gate Rule)</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: 10, cursor: 'pointer', fontSize: '0.85rem' }}>
              <input
                type="checkbox"
                checked={manifest.capabilities.checkpoints.enabled}
                onChange={(e) =>
                  updateManifest({
                    ...manifest,
                    capabilities: {
                      ...manifest.capabilities,
                      checkpoints: { ...manifest.capabilities.checkpoints, enabled: e.target.checked },
                    },
                  })
                }
              />
              Require Human Approval Checkpoints (Gate 1: Plan Approval, Gate 2: First Execution Run)
            </label>

            {manifest.capabilities.checkpoints.enabled && (
              <div style={{ marginTop: 8, paddingLeft: 22 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                  Gated Platform Asset Categories:
                </div>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {WRITE_CATEGORIES.map((cat) => (
                    <label key={cat} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.8rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={manifest.capabilities.checkpoints.gated_write_categories.includes(cat)}
                        onChange={() => toggleCategory(cat)}
                      />
                      <span style={{ textTransform: 'capitalize' }}>{cat}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Document Upload */}
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 6 }}>Document Evidence Upload</div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: 10, cursor: 'pointer', fontSize: '0.85rem' }}>
              <input
                type="checkbox"
                checked={manifest.capabilities.document_upload.enabled}
                onChange={(e) =>
                  updateManifest({
                    ...manifest,
                    capabilities: {
                      ...manifest.capabilities,
                      document_upload: { ...manifest.capabilities.document_upload, enabled: e.target.checked },
                    },
                  })
                }
              />
              Allow Users to Upload Documents in Chat
            </label>

            {manifest.capabilities.document_upload.enabled && (
              <div style={{ marginTop: 8, paddingLeft: 22 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                  Accepted Evidence Formats:
                </div>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {FILE_TYPES.map((type) => (
                    <label key={type} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.8rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={manifest.capabilities.document_upload.accepted_types.includes(type)}
                        onChange={() => toggleFileType(type)}
                      />
                      .{type}
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Artifact Visibility (Part G / D17) */}
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 6 }}>Session Artifact Visibility</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 8 }}>
              Surface clickable asset chips and diff cards in the chat session.
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: 8, cursor: 'pointer', fontSize: '0.85rem' }}>
              <input
                type="checkbox"
                checked={manifest.capabilities.artifact_visibility.enabled}
                onChange={(e) =>
                  updateManifest({
                    ...manifest,
                    capabilities: {
                      ...manifest.capabilities,
                      artifact_visibility: { ...manifest.capabilities.artifact_visibility, enabled: e.target.checked },
                    },
                  })
                }
              />
              Enable Artifact Visibility
            </label>

            {manifest.capabilities.artifact_visibility.enabled && (
              <div style={{ paddingLeft: 22, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.83rem' }}>
                  <input
                    type="checkbox"
                    checked={manifest.capabilities.artifact_visibility.link_resolution}
                    onChange={(e) =>
                      updateManifest({
                        ...manifest,
                        capabilities: {
                          ...manifest.capabilities,
                          artifact_visibility: { ...manifest.capabilities.artifact_visibility, link_resolution: e.target.checked },
                        },
                      })
                    }
                  />
                  Resolve &lt;asset&gt; tags to clickable chips (G2)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.83rem' }}>
                  <input
                    type="checkbox"
                    checked={manifest.capabilities.artifact_visibility.diff_capture}
                    onChange={(e) =>
                      updateManifest({
                        ...manifest,
                        capabilities: {
                          ...manifest.capabilities,
                          artifact_visibility: { ...manifest.capabilities.artifact_visibility, diff_capture: e.target.checked },
                        },
                      })
                    }
                  />
                  Capture before/after diffs for review (G5)
                </label>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
