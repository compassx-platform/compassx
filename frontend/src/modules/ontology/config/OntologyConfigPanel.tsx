import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Settings,
  X,
  Plus,
  Trash2,
  RotateCcw,
  Hexagon,
  Square,
  Circle,
  Hash,
  Edit2,
  Check,
} from 'lucide-react';
import type { KindConfig, NodeShapeType, ConfigTab, OntologyConfigPanelProps } from './types';
import { DEFAULT_KINDS_CONFIG } from './defaults';
import { PageTabs } from '@/components/common/PageTabs';
import './config.css';

export const OntologyConfigPanel: React.FC<OntologyConfigPanelProps> = ({
  kindsConfig = DEFAULT_KINDS_CONFIG,
  onUpdateKindsConfig,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ConfigTab>('kinds');
  const [editingKindId, setEditingKindId] = useState<string | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);

  // New Kind form state
  const [newKind, setNewKind] = useState<KindConfig>({
    id: '',
    label: '',
    description: '',
    shape: 'circle',
    baseRadius: 12,
    tier: 2,
  });

  // Edit Kind temp state
  const [editForm, setEditForm] = useState<KindConfig | null>(null);

  // Default to a wide panel, adjustable via left-border dragging
  const [panelWidth, setPanelWidth] = useState(() => {
    if (typeof window !== 'undefined') {
      return Math.min(520, window.innerWidth - 40);
    }
    return 480;
  });
  const [isDragging, setIsDragging] = useState(false);
  const isDraggingRef = useRef(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Resize handler by dragging left border
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    setIsDragging(true);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ew-resize';

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const rightEdge = window.innerWidth - 10;
      const newWidth = rightEdge - moveEvent.clientX;
      const minWidth = 320;
      const maxWidth = window.innerWidth - 24;
      setPanelWidth(Math.max(minWidth, Math.min(maxWidth, newWidth)));
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      setIsDragging(false);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, []);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const CONFIG_PAGE_TABS = [
    { value: 'kinds', label: 'Semantic Kinds' },
  ] as const;

  const getShapeIcon = (shape: NodeShapeType) => {
    const size = 14;
    switch (shape) {
      case 'hexagon':
        return <Hexagon size={size} />;
      case 'chip':
        return <Square size={size} />;
      case 'circle':
        return <Circle size={size} />;
      case 'pad':
        return <Hash size={size} />;
      default:
        return <Circle size={size} />;
    }
  };

  const startEdit = (k: KindConfig) => {
    setEditingKindId(k.id);
    setEditForm({ ...k });
  };

  const handleSaveEdit = () => {
    if (!editForm || !onUpdateKindsConfig) return;
    const next = kindsConfig.map(k => (k.id === editForm.id ? editForm : k));
    onUpdateKindsConfig(next);
    setEditingKindId(null);
    setEditForm(null);
  };

  const handleAddNewKind = () => {
    if (!newKind.id.trim() || !newKind.label.trim()) return;
    const cleanId = newKind.id.toLowerCase().trim().replace(/[^a-z0-9_-]/g, '-');
    if (kindsConfig.some(k => k.id === cleanId)) {
      alert(`A kind with ID "${cleanId}" already exists.`);
      return;
    }
    const created: KindConfig = {
      ...newKind,
      id: cleanId,
    };
    if (onUpdateKindsConfig) {
      onUpdateKindsConfig([...kindsConfig, created]);
    }
    setNewKind({
      id: '',
      label: '',
      description: '',
      shape: 'circle',
      baseRadius: 12,
      tier: 2,
    });
    setIsAddingNew(false);
  };

  const handleDeleteKind = (kindId: string) => {
    if (!onUpdateKindsConfig) return;
    if (window.confirm(`Delete kind "${kindId}"?`)) {
      const next = kindsConfig.filter(k => k.id !== kindId);
      onUpdateKindsConfig(next);
    }
  };

  const handleResetKinds = () => {
    if (window.confirm('Reset all kinds back to default 4 kinds (Project, Domain, Capability, Element)?')) {
      if (onUpdateKindsConfig) {
        onUpdateKindsConfig(DEFAULT_KINDS_CONFIG);
      }
      setEditingKindId(null);
      setIsAddingNew(false);
    }
  };

  return (
    <>
      {/* Top Right Configure Trigger Button */}
      <div className={`cx-ontology-config-trigger ${isOpen ? 'is-active' : ''}`}>
        <button
          type="button"
          onClick={() => setIsOpen(prev => !prev)}
          className="cx-ontology-config-trigger-btn"
          title="Toggle Configuration Panel"
        >
          <Settings
            size={13}
            style={{
              transition: 'transform 0.25s ease',
              transform: isOpen ? 'rotate(90deg)' : 'none',
            }}
          />
          <span>Configure</span>
        </button>
      </div>

      {/* Drag-resizable Configuration Panel Styled with App Design System */}
      {isOpen && (
        <div
          ref={panelRef}
          className="cx-ontology-config-panel"
          style={{ width: `${panelWidth}px`, maxWidth: 'calc(100vw - 20px)' }}
        >
          {/* Left-edge Drag Resize Handle */}
          <div
            onMouseDown={handleMouseDown}
            className={`cx-ontology-config-resize-handle ${isDragging ? 'is-dragging' : ''}`}
            title="Drag to resize panel width"
          />

          {/* Tabbed Header with standard PageTabs component */}
          <div className="cx-ontology-config-header">
            <PageTabs
              tabs={CONFIG_PAGE_TABS}
              value={activeTab}
              onChange={setActiveTab}
              className="cx-ontology-config-pagetabs"
            />

            {/* Close Button */}
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="cx-ontology-config-close-btn"
              title="Close panel"
            >
              <X size={15} />
            </button>
          </div>

          {/* Panel Body */}
          <div className="cx-ontology-config-body">
            {/* 1. Semantic Kinds Tab */}
            {activeTab === 'kinds' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Header & Add Button */}
                <div className="cx-ontology-config-section-head">
                  <div>
                    <div className="cx-ontology-config-title">
                      Configured Kinds ({kindsConfig.length})
                    </div>
                    <div className="cx-ontology-config-subtitle">
                      Dynamic geometric shapes, base sizes, and layout tiers for graph entities.
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setIsAddingNew(prev => !prev)}
                      className="btn-primary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                    >
                      <Plus size={12} />
                      <span>Add Kind</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleResetKinds}
                      className="cx-ontology-config-icon-btn"
                      title="Reset to default 4 kinds"
                    >
                      <RotateCcw size={13} />
                    </button>
                  </div>
                </div>

                {/* Add New Kind Form */}
                {isAddingNew && (
                  <div className="cx-ontology-config-form">
                    <div className="cx-ontology-config-form-title">
                      Create New Semantic Kind
                    </div>
                    <div className="cx-ontology-config-form-grid">
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Kind ID / Slug
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. microservice"
                          value={newKind.id}
                          onChange={e => setNewKind(prev => ({ ...prev, id: e.target.value }))}
                          className="form-input"
                        />
                      </div>
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Display Title
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Microservice"
                          value={newKind.label}
                          onChange={e => setNewKind(prev => ({ ...prev, label: e.target.value }))}
                          className="form-input"
                        />
                      </div>
                    </div>

                    <div className="cx-ontology-config-form-grid-3">
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Shape
                        </label>
                        <select
                          value={newKind.shape}
                          onChange={e => setNewKind(prev => ({ ...prev, shape: e.target.value as NodeShapeType }))}
                          className="form-input"
                        >
                          <option value="hexagon">Hexagon (Plate)</option>
                          <option value="chip">Square (Chip)</option>
                          <option value="circle">Circle (Disc)</option>
                          <option value="pad">Pad (Via Hole)</option>
                        </select>
                      </div>
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Radius (px)
                        </label>
                        <input
                          type="number"
                          min="5"
                          max="60"
                          value={newKind.baseRadius}
                          onChange={e => setNewKind(prev => ({ ...prev, baseRadius: parseInt(e.target.value, 10) || 10 }))}
                          className="form-input"
                        />
                      </div>
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Hierarchy Tier
                        </label>
                        <select
                          value={newKind.tier}
                          onChange={e => setNewKind(prev => ({ ...prev, tier: parseInt(e.target.value, 10) }))}
                          className="form-input"
                        >
                          <option value="0">Tier 0 (Root Center)</option>
                          <option value="1">Tier 1 (Inner Ring)</option>
                          <option value="2">Tier 2 (Mid Ring)</option>
                          <option value="3">Tier 3 (Outer Clusters)</option>
                        </select>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
                      <button
                        type="button"
                        onClick={() => setIsAddingNew(false)}
                        className="btn-outline"
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleAddNewKind}
                        className="btn-primary"
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                      >
                        Create Kind
                      </button>
                    </div>
                  </div>
                )}

                {/* Kinds List Cards */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {kindsConfig.map(k => {
                    const isEditing = editingKindId === k.id;

                    if (isEditing && editForm) {
                      return (
                        <div
                          key={k.id}
                          className="cx-ontology-config-form"
                          style={{ borderColor: 'var(--color-primary)' }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-primary)' }}>
                              Editing: {k.id}
                            </span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <button
                                type="button"
                                onClick={handleSaveEdit}
                                className="btn-primary"
                                style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
                              >
                                <Check size={11} /> Save
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingKindId(null);
                                  setEditForm(null);
                                }}
                                className="btn-outline"
                                style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>

                          <div className="cx-ontology-config-form-grid-3">
                            <div className="cx-ontology-config-field">
                              <label className="cx-ontology-config-label">
                                Title
                              </label>
                              <input
                                type="text"
                                value={editForm.label}
                                onChange={e => setEditForm(prev => prev ? { ...prev, label: e.target.value } : null)}
                                className="form-input"
                              />
                            </div>
                            <div className="cx-ontology-config-field">
                              <label className="cx-ontology-config-label">
                                Shape
                              </label>
                              <select
                                value={editForm.shape}
                                onChange={e => setEditForm(prev => prev ? { ...prev, shape: e.target.value as NodeShapeType } : null)}
                                className="form-input"
                              >
                                <option value="hexagon">Hexagon</option>
                                <option value="chip">Square Chip</option>
                                <option value="circle">Circle</option>
                                <option value="pad">Via Pad</option>
                              </select>
                            </div>
                            <div className="cx-ontology-config-field">
                              <label className="cx-ontology-config-label">
                                Radius (px)
                              </label>
                              <input
                                type="number"
                                min="5"
                                max="60"
                                value={editForm.baseRadius}
                                onChange={e => setEditForm(prev => prev ? { ...prev, baseRadius: parseInt(e.target.value, 10) || 10 } : null)}
                                className="form-input"
                              />
                            </div>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={k.id} className="cx-ontology-config-card">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                          <div className="cx-ontology-config-card-icon-box">
                            {getShapeIcon(k.shape)}
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text)' }}>
                                {k.label}
                              </span>
                              <span className="cx-ontology-config-slug-badge">
                                {k.id}
                              </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 3 }}>
                              <span className="cx-ontology-config-meta-item">
                                Shape: <strong className="cx-ontology-config-meta-val">{k.shape}</strong>
                              </span>
                              <span className="cx-ontology-config-meta-item">
                                Radius: <strong className="cx-ontology-config-meta-val">{k.baseRadius}px</strong>
                              </span>
                              <span className="cx-ontology-config-meta-item">
                                Tier: <strong className="cx-ontology-config-meta-val">{k.tier}</strong>
                              </span>
                            </div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <button
                            type="button"
                            onClick={() => startEdit(k)}
                            className="cx-ontology-config-icon-btn"
                            title="Edit kind"
                          >
                            <Edit2 size={13} />
                          </button>
                          {kindsConfig.length > 1 && (
                            <button
                              type="button"
                              onClick={() => handleDeleteKind(k.id)}
                              className="cx-ontology-config-icon-btn is-danger"
                              title="Delete kind"
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
