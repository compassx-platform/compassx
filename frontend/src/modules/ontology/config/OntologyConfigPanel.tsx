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
  ArrowRight,
  GitFork,
} from 'lucide-react';
import type {
  KindConfig,
  NodeShapeType,
  TypeRelationConfig,
  ConfigTab,
  OntologyConfigPanelProps,
} from './types';
import { DEFAULT_KINDS_CONFIG, DEFAULT_TYPE_RELATIONS } from './defaults';
import { PageTabs } from '@/components/common/PageTabs';
import {
  createOntologyType,
  updateOntologyType,
  deleteOntologyType,
  createTypeRelation,
  deleteTypeRelation,
} from '../api/ontologyApi';
import './config.css';

export const OntologyConfigPanel: React.FC<OntologyConfigPanelProps> = ({
  kindsConfig = DEFAULT_KINDS_CONFIG,
  onUpdateKindsConfig,
  typeRelations = DEFAULT_TYPE_RELATIONS,
  onUpdateTypeRelations,
  onResetDefaultData,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ConfigTab>('kinds');

  // ─── Semantic Kinds Form State ──────────────────────────────────────────────
  const [editingKindId, setEditingKindId] = useState<string | null>(null);
  const [isAddingNewKind, setIsAddingNewKind] = useState(false);
  const [newKind, setNewKind] = useState<KindConfig>({
    id: '',
    label: '',
    description: '',
    shape: 'circle',
    baseRadius: 12,
    tier: 2,
  });
  const [editKindForm, setEditKindForm] = useState<KindConfig | null>(null);

  // ─── Type Relations Form State ──────────────────────────────────────────────
  const [isAddingNewRelation, setIsAddingNewRelation] = useState(false);
  const [newRelation, setNewRelation] = useState<TypeRelationConfig>({
    source_type_id: kindsConfig[0]?.id || 'org',
    relation_type: 'contains',
    target_type_id: kindsConfig[1]?.id || 'domain',
    is_hierarchical: true,
    description: '',
  });

  // Default to a wide panel, adjustable via left-border dragging
  const [panelWidth, setPanelWidth] = useState(() => {
    if (typeof window !== 'undefined') {
      return Math.min(560, window.innerWidth - 40);
    }
    return 500;
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
      const minWidth = 340;
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
    { value: 'kinds', label: 'Semantic Types' },
    { value: 'relations', label: 'Type Relationships' },
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

  // ─── Kinds Handlers ─────────────────────────────────────────────────────────

  const startEditKind = (k: KindConfig) => {
    setEditingKindId(k.id);
    setEditKindForm({ ...k });
  };

  const handleSaveEditKind = async () => {
    if (!editKindForm || !onUpdateKindsConfig) return;
    const next = kindsConfig.map(k => (k.id === editKindForm.id ? editKindForm : k));
    onUpdateKindsConfig(next);
    setEditingKindId(null);
    setEditKindForm(null);

    try {
      await updateOntologyType(editKindForm.id, editKindForm);
    } catch (err) {
      console.warn('Backend update failed (offline fallback active):', err);
    }
  };

  const handleAddNewKind = async () => {
    if (!newKind.id.trim() || !newKind.label.trim()) return;
    const cleanId = newKind.id.toLowerCase().trim().replace(/[^a-z0-9_-]/g, '-');
    if (kindsConfig.some(k => k.id === cleanId)) {
      alert(`An entity type with ID "${cleanId}" already exists.`);
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
    setIsAddingNewKind(false);

    try {
      await createOntologyType(created);
    } catch (err) {
      console.warn('Backend create type failed (offline fallback active):', err);
    }
  };

  const handleDeleteKind = async (kindId: string) => {
    if (!onUpdateKindsConfig) return;
    const targetKind = kindsConfig.find(k => k.id === kindId);
    if (targetKind?.is_system) {
      alert(`System entity type "${kindId}" is protected and cannot be deleted.`);
      return;
    }
    if (window.confirm(`Delete entity type "${kindId}"? Associated relationship rules will also be removed.`)) {
      const next = kindsConfig.filter(k => k.id !== kindId);
      onUpdateKindsConfig(next);
      if (onUpdateTypeRelations) {
        onUpdateTypeRelations(
          typeRelations.filter(r => r.source_type_id !== kindId && r.target_type_id !== kindId)
        );
      }

      try {
        await deleteOntologyType(kindId);
      } catch (err) {
        console.warn('Backend delete type failed (offline fallback active):', err);
      }
    }
  };

  const handleResetKinds = () => {
    if (window.confirm('Reset all entity types back to default system types (Org, Domain, Subdomain, Element)?')) {
      if (onUpdateKindsConfig) {
        onUpdateKindsConfig(DEFAULT_KINDS_CONFIG);
      }
      setEditingKindId(null);
      setIsAddingNewKind(false);
      if (onResetDefaultData) {
        onResetDefaultData();
      }
    }
  };

  // ─── Relations Handlers ─────────────────────────────────────────────────────

  const handleAddNewRelation = async () => {
    const cleanRel = newRelation.relation_type.trim().toLowerCase().replace(/\s+/g, '_');
    if (!cleanRel || !newRelation.source_type_id || !newRelation.target_type_id) return;

    const exists = typeRelations.some(
      r =>
        r.source_type_id === newRelation.source_type_id &&
        r.relation_type.toLowerCase() === cleanRel &&
        r.target_type_id === newRelation.target_type_id
    );

    if (exists) {
      alert(`Relationship "${newRelation.source_type_id} --[${cleanRel}]--> ${newRelation.target_type_id}" already exists.`);
      return;
    }

    const created: TypeRelationConfig = {
      ...newRelation,
      relation_type: cleanRel,
      is_hierarchical: newRelation.is_hierarchical || cleanRel === 'contains',
    };

    if (onUpdateTypeRelations) {
      onUpdateTypeRelations([...typeRelations, created]);
    }

    setIsAddingNewRelation(false);
    setNewRelation({
      source_type_id: kindsConfig[0]?.id || 'org',
      relation_type: 'contains',
      target_type_id: kindsConfig[1]?.id || 'domain',
      is_hierarchical: true,
      description: '',
    });

    try {
      const saved = await createTypeRelation(created);
      if (saved.id && onUpdateTypeRelations) {
        onUpdateTypeRelations([...typeRelations, saved]);
      }
    } catch (err) {
      console.warn('Backend create relation failed (offline fallback active):', err);
    }
  };

  const handleDeleteRelation = async (index: number, relId?: number) => {
    if (!onUpdateTypeRelations) return;
    const item = typeRelations[index];
    if (!item) return;

    if (item.is_system) {
      alert(`System containment rule "${item.source_type_id} --[${item.relation_type}]--> ${item.target_type_id}" is protected and cannot be deleted.`);
      return;
    }

    if (window.confirm(`Delete relationship rule "${item.source_type_id} --[${item.relation_type}]--> ${item.target_type_id}"?`)) {
      const next = typeRelations.filter((_, i) => i !== index);
      onUpdateTypeRelations(next);

      if (relId) {
        try {
          await deleteTypeRelation(relId);
        } catch (err) {
          console.warn('Backend delete relation failed (offline fallback active):', err);
        }
      }
    }
  };

  const handleResetRelations = () => {
    if (window.confirm('Reset all metamodel relationship rules back to system defaults?')) {
      if (onUpdateTypeRelations) {
        onUpdateTypeRelations(DEFAULT_TYPE_RELATIONS);
      }
      setIsAddingNewRelation(false);
      if (onResetDefaultData) {
        onResetDefaultData();
      }
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
            {/* ─── TAB 1: Semantic Entity Types ─────────────────────────────── */}
            {activeTab === 'kinds' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Header & Add Button */}
                <div className="cx-ontology-config-section-head">
                  <div>
                    <div className="cx-ontology-config-title">
                      Configured Entity Types ({kindsConfig.length})
                    </div>
                    <div className="cx-ontology-config-subtitle">
                      Shapes, base radii, and concentric layout tiers for graph entities.
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setIsAddingNewKind(prev => !prev)}
                      className="btn-primary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                    >
                      <Plus size={12} />
                      <span>Add Type</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleResetKinds}
                      className="cx-ontology-config-icon-btn"
                      title="Reset entity types to defaults"
                    >
                      <RotateCcw size={13} />
                    </button>
                  </div>
                </div>

                {/* Add New Type Form */}
                {isAddingNewKind && (
                  <div className="cx-ontology-config-form">
                    <div className="cx-ontology-config-form-title">
                      Create New Entity Type
                    </div>
                    <div className="cx-ontology-config-form-grid">
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Type ID / Slug
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
                          Display Label
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
                          <option value="0">Tier 0 (Root Apex)</option>
                          <option value="1">Tier 1 (Inner Ring)</option>
                          <option value="2">Tier 2 (Mid Ring)</option>
                          <option value="3">Tier 3 (Outer Clusters)</option>
                        </select>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
                      <button
                        type="button"
                        onClick={() => setIsAddingNewKind(false)}
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
                        Create Type
                      </button>
                    </div>
                  </div>
                )}

                {/* Types List Cards */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {kindsConfig.map(k => {
                    const isEditing = editingKindId === k.id;

                    if (isEditing && editKindForm) {
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
                                onClick={handleSaveEditKind}
                                className="btn-primary"
                                style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
                              >
                                <Check size={11} /> Save
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingKindId(null);
                                  setEditKindForm(null);
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
                                Label
                              </label>
                              <input
                                type="text"
                                value={editKindForm.label}
                                onChange={e => setEditKindForm(prev => prev ? { ...prev, label: e.target.value } : null)}
                                className="form-input"
                              />
                            </div>
                            <div className="cx-ontology-config-field">
                              <label className="cx-ontology-config-label">
                                Shape
                              </label>
                              <select
                                value={editKindForm.shape}
                                onChange={e => setEditKindForm(prev => prev ? { ...prev, shape: e.target.value as NodeShapeType } : null)}
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
                                value={editKindForm.baseRadius}
                                onChange={e => setEditKindForm(prev => prev ? { ...prev, baseRadius: parseInt(e.target.value, 10) || 10 } : null)}
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
                              {k.is_system && (
                                <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--color-primary, #2272b4)', background: 'var(--color-primary-bg, rgba(34, 114, 180, 0.1))', padding: '2px 6px', borderRadius: 4, textTransform: 'uppercase' }}>
                                  System Type (Protected)
                                </span>
                              )}
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
                            onClick={() => startEditKind(k)}
                            className="cx-ontology-config-icon-btn"
                            title="Edit type"
                          >
                            <Edit2 size={13} />
                          </button>
                          {!k.is_system && kindsConfig.length > 1 && (
                            <button
                              type="button"
                              onClick={() => handleDeleteKind(k.id)}
                              className="cx-ontology-config-icon-btn is-danger"
                              title="Delete type"
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

            {/* ─── TAB 2: Type Relationships (Metamodel) ──────────────────── */}
            {activeTab === 'relations' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Header & Add Button */}
                <div className="cx-ontology-config-section-head">
                  <div>
                    <div className="cx-ontology-config-title">
                      Allowed Relationships ({typeRelations.length})
                    </div>
                    <div className="cx-ontology-config-subtitle">
                      Metamodel rules defining valid relationships between entity types.
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setIsAddingNewRelation(prev => !prev)}
                      className="btn-primary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                    >
                      <Plus size={12} />
                      <span>Add Rule</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleResetRelations}
                      className="cx-ontology-config-icon-btn"
                      title="Reset metamodel rules to defaults"
                    >
                      <RotateCcw size={13} />
                    </button>
                  </div>
                </div>

                {/* Add New Relation Rule Form */}
                {isAddingNewRelation && (
                  <div className="cx-ontology-config-form">
                    <div className="cx-ontology-config-form-title">
                      Define Allowed Type Relationship
                    </div>
                    <div className="cx-ontology-config-form-grid-3">
                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Source Type
                        </label>
                        <select
                          value={newRelation.source_type_id}
                          onChange={e => setNewRelation(prev => ({ ...prev, source_type_id: e.target.value }))}
                          className="form-input"
                        >
                          {kindsConfig.map(k => (
                            <option key={k.id} value={k.id}>
                              {k.label} ({k.id})
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Relation Name
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. contains, depends_on"
                          value={newRelation.relation_type}
                          onChange={e => {
                            const val = e.target.value;
                            setNewRelation(prev => ({
                              ...prev,
                              relation_type: val,
                              is_hierarchical: val === 'contains' || prev.is_hierarchical,
                            }));
                          }}
                          className="form-input"
                        />
                      </div>

                      <div className="cx-ontology-config-field">
                        <label className="cx-ontology-config-label">
                          Target Type
                        </label>
                        <select
                          value={newRelation.target_type_id}
                          onChange={e => setNewRelation(prev => ({ ...prev, target_type_id: e.target.value }))}
                          className="form-input"
                        >
                          {kindsConfig.map(k => (
                            <option key={k.id} value={k.id}>
                              {k.label} ({k.id})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', cursor: 'pointer', color: 'var(--color-text)' }}>
                        <input
                          type="checkbox"
                          checked={newRelation.is_hierarchical || newRelation.relation_type === 'contains'}
                          onChange={e => setNewRelation(prev => ({ ...prev, is_hierarchical: e.target.checked }))}
                        />
                        <span>Hierarchical Tree Containment (allows <code>parentId</code> linkage)</span>
                      </label>
                    </div>

                    <div className="cx-ontology-config-field">
                      <label className="cx-ontology-config-label">
                        Rule Description (Optional)
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Domain contains capabilities in architectural hierarchy"
                        value={newRelation.description || ''}
                        onChange={e => setNewRelation(prev => ({ ...prev, description: e.target.value }))}
                        className="form-input"
                      />
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
                      <button
                        type="button"
                        onClick={() => setIsAddingNewRelation(false)}
                        className="btn-outline"
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleAddNewRelation}
                        className="btn-primary"
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                      >
                        Add Rule
                      </button>
                    </div>
                  </div>
                )}

                {/* Relationships List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {typeRelations.map((rel, index) => {
                    const srcKind = kindsConfig.find(k => k.id === rel.source_type_id);
                    const tgtKind = kindsConfig.find(k => k.id === rel.target_type_id);

                    return (
                      <div key={`${rel.source_type_id}-${rel.relation_type}-${rel.target_type_id}-${index}`} className="cx-ontology-config-card">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, flex: 1 }}>
                          <div className="cx-ontology-relation-flow">
                            <span className="cx-ontology-type-chip">
                              {srcKind && getShapeIcon(srcKind.shape)}
                              <span>{srcKind?.label || rel.source_type_id}</span>
                            </span>

                            <span className="cx-ontology-rel-arrow">
                              <ArrowRight size={12} />
                              <span className="cx-ontology-rel-badge">
                                {rel.relation_type}
                              </span>
                              <ArrowRight size={12} />
                            </span>

                            <span className="cx-ontology-type-chip">
                              {tgtKind && getShapeIcon(tgtKind.shape)}
                              <span>{tgtKind?.label || rel.target_type_id}</span>
                            </span>

                            {rel.is_hierarchical && (
                              <span className="cx-ontology-hier-badge">
                                Hierarchy
                              </span>
                            )}

                            {rel.is_system && (
                              <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--color-primary, #2272b4)', background: 'var(--color-primary-bg, rgba(34, 114, 180, 0.1))', padding: '2px 6px', borderRadius: 4, textTransform: 'uppercase' }}>
                                System Rule (Protected)
                              </span>
                            )}
                          </div>

                          {rel.description && (
                            <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: 2 }}>
                              {rel.description}
                            </div>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
                          {!rel.is_system && (
                            <button
                              type="button"
                              onClick={() => handleDeleteRelation(index, rel.id)}
                              className="cx-ontology-config-icon-btn is-danger"
                              title="Delete relationship rule"
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
