import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Settings,
  X,
  Plus,
  Trash2,
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
  updateTypeRelation,
  deleteTypeRelation,
} from '../api/ontologyApi';
import './config.css';

export const OntologyConfigPanel: React.FC<OntologyConfigPanelProps> = ({
  isOpen: controlledIsOpen,
  onClose: controlledOnClose,
  onToggleOpen: controlledOnToggleOpen,
  hideTrigger = false,
  kindsConfig = DEFAULT_KINDS_CONFIG,
  onUpdateKindsConfig,
  typeRelations = DEFAULT_TYPE_RELATIONS,
  onUpdateTypeRelations,
}) => {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;

  const handleToggle = () => {
    if (controlledOnToggleOpen) {
      controlledOnToggleOpen();
    } else if (controlledOnClose && isOpen) {
      controlledOnClose();
    } else {
      setInternalIsOpen(prev => !prev);
    }
  };

  const handleClose = () => {
    if (controlledOnClose) {
      controlledOnClose();
    } else {
      setInternalIsOpen(false);
    }
  };

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
  const [inlineAddPairKey, setInlineAddPairKey] = useState<string | null>(null);
  const [inlineRelationName, setInlineRelationName] = useState('');
  const [isAddingNewRelation, setIsAddingNewRelation] = useState(false);
  const [newRelation, setNewRelation] = useState<TypeRelationConfig>({
    source_type_id: kindsConfig[0]?.id || 'org',
    relation_type: 'contains',
    target_type_id: kindsConfig[1]?.id || 'domain',
    is_hierarchical: true,
    description: '',
  });

  // Group relations by Type Pair (Source -> Target)
  const groupedPairs = useMemo(() => {
    const map = new Map<
      string,
      {
        pairKey: string;
        source_type_id: string;
        target_type_id: string;
        relations: TypeRelationConfig[];
        hasSystemRelation: boolean;
      }
    >();
    for (const rel of typeRelations) {
      const key = `${rel.source_type_id}->${rel.target_type_id}`;
      if (!map.has(key)) {
        map.set(key, {
          pairKey: key,
          source_type_id: rel.source_type_id,
          target_type_id: rel.target_type_id,
          relations: [],
          hasSystemRelation: false,
        });
      }
      const entry = map.get(key)!;
      entry.relations.push(rel);
      if (rel.is_system) {
        entry.hasSystemRelation = true;
      }
    }
    return Array.from(map.values());
  }, [typeRelations]);

  // Default to a wide panel, adjustable via left-border dragging
  const [panelWidth, setPanelWidth] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('cx_ontology_drawer_width') || localStorage.getItem('cx_ontology_config_panel_width');
      if (saved) {
        const num = parseInt(saved, 10);
        if (!isNaN(num)) return Math.max(340, Math.min(window.innerWidth - 24, num));
      }
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
      if (panelRef.current) {
        const currentWidth = panelRef.current.offsetWidth;
        localStorage.setItem('cx_ontology_drawer_width', String(currentWidth));
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, []);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        handleClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

  const CONFIG_PAGE_TABS = [
    { value: 'kinds' as const, label: `Entity Types (${kindsConfig.length})` },
    { value: 'relations' as const, label: `Relationships (${groupedPairs.length})` },
  ];

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
        return (
          <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <circle cx="12" cy="12" r="4" />
          </svg>
        );
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
    const rawLabel = newKind.label.trim();
    if (!rawLabel) return;
    const cleanId = rawLabel.toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (kindsConfig.some(k => k.id === cleanId)) {
      alert(`An entity type with name "${rawLabel}" already exists.`);
      return;
    }
    const created: KindConfig = {
      id: cleanId,
      label: rawLabel,
      description: newKind.description?.trim() || '',
      shape: 'circle',
      baseRadius: 11,
      tier: 2,
      is_system: false,
    };
    if (onUpdateKindsConfig) {
      onUpdateKindsConfig([...kindsConfig, created]);
    }
    setNewKind({
      id: '',
      label: '',
      description: '',
      shape: 'circle',
      baseRadius: 11,
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

  // ─── Relations Handlers ─────────────────────────────────────────────────────

  const handleInlineAddRelation = async (sourceId: string, targetId: string) => {
    const cleanRel = inlineRelationName.trim().toLowerCase().replace(/\s+/g, '_');
    if (!cleanRel) return;

    const exists = typeRelations.some(
      r => r.source_type_id === sourceId && r.target_type_id === targetId && r.relation_type.toLowerCase() === cleanRel
    );
    if (exists) {
      alert(`Relationship "${sourceId} --[${cleanRel}]--> ${targetId}" already exists.`);
      return;
    }

    const created: TypeRelationConfig = {
      source_type_id: sourceId,
      relation_type: cleanRel,
      target_type_id: targetId,
      is_hierarchical: cleanRel === 'contains',
      description: '',
    };

    const next = [...typeRelations, created];
    if (onUpdateTypeRelations) {
      onUpdateTypeRelations(next);
    }
    setInlineAddPairKey(null);
    setInlineRelationName('');

    try {
      const saved = await createTypeRelation(created);
      if (saved.id && onUpdateTypeRelations) {
        onUpdateTypeRelations(next.map(r => (r === created ? saved : r)));
      }
    } catch (err) {
      console.warn('Backend create relation failed (offline fallback active):', err);
    }
  };

  const handleDeleteSingleRelation = async (rel: TypeRelationConfig) => {
    if (rel.is_system) {
      alert(`System rule "${rel.source_type_id} --[${rel.relation_type}]--> ${rel.target_type_id}" is protected and cannot be deleted.`);
      return;
    }

    if (window.confirm(`Delete relationship "${rel.source_type_id} --[${rel.relation_type}]--> ${rel.target_type_id}"?`)) {
      const next = typeRelations.filter(r => r !== rel && !(r.id && rel.id && r.id === rel.id));
      if (onUpdateTypeRelations) {
        onUpdateTypeRelations(next);
      }

      if (rel.id) {
        try {
          await deleteTypeRelation(rel.id);
        } catch (err) {
          console.warn('Backend delete relation failed (offline fallback active):', err);
        }
      }
    }
  };

  const handleDeletePair = async (pair: { source_type_id: string; target_type_id: string; relations: TypeRelationConfig[]; hasSystemRelation: boolean }) => {
    if (pair.hasSystemRelation) {
      alert(`This entity pair contains protected system rules and cannot be deleted.`);
      return;
    }

    if (window.confirm(`Delete all relationship rules between "${pair.source_type_id}" and "${pair.target_type_id}"?`)) {
      const relsToDelete = pair.relations;
      const next = typeRelations.filter(r => r.source_type_id !== pair.source_type_id || r.target_type_id !== pair.target_type_id);
      if (onUpdateTypeRelations) {
        onUpdateTypeRelations(next);
      }

      for (const rel of relsToDelete) {
        if (rel.id) {
          try {
            await deleteTypeRelation(rel.id);
          } catch (err) {
            console.warn('Backend delete relation failed (offline fallback active):', err);
          }
        }
      }
    }
  };

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

    const next = [...typeRelations, created];
    if (onUpdateTypeRelations) {
      onUpdateTypeRelations(next);
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
        onUpdateTypeRelations(next.map(r => (r === created ? saved : r)));
      }
    } catch (err) {
      console.warn('Backend create relation failed (offline fallback active):', err);
    }
  };

  return (
    <>
      {/* Top Right Configure Trigger Button (rendered if not hidden by parent) */}
      {!hideTrigger && (
        <div className={`cx-ontology-config-trigger ${isOpen ? 'is-active' : ''}`}>
          <button
            type="button"
            onClick={handleToggle}
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
      )}

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
              onClick={handleClose}
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {kindsConfig.map(k => {
                    const isEditing = editingKindId === k.id;
                    const cleanLabel = k.id === 'org' ? 'Organization' : k.id === 'domain' ? 'Domain' : k.id === 'subdomain' ? 'Subdomain' : k.id === 'element' ? 'Element' : k.label;

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

                          <div className="cx-ontology-config-form-grid" style={{ marginTop: 8 }}>
                            <div className="cx-ontology-config-field">
                              <label className="cx-ontology-config-label">
                                Display Name
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
                                Description
                              </label>
                              <input
                                type="text"
                                value={editKindForm.description || ''}
                                onChange={e => setEditKindForm(prev => prev ? { ...prev, description: e.target.value } : null)}
                                className="form-input"
                              />
                            </div>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={k.id} className="cx-ontology-config-card">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                          <span style={{ color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}>
                            {getShapeIcon(k.shape)}
                          </span>
                          <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text)' }}>
                            {cleanLabel}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          {!k.is_system && (
                            <>
                              <button
                                type="button"
                                onClick={() => startEditKind(k)}
                                className="cx-ontology-config-icon-btn"
                                title="Edit type"
                              >
                                <Edit2 size={13} />
                              </button>
                              {kindsConfig.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => handleDeleteKind(k.id)}
                                  className="cx-ontology-config-icon-btn is-danger"
                                  title="Delete type"
                                >
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {/* Dotted Add Type Box / Inline Form sticky at the bottom */}
                  <div className="cx-ontology-config-sticky-footer">
                    {isAddingNewKind ? (
                      <div className="cx-ontology-config-form" style={{ marginTop: 2 }}>
                        <div className="cx-ontology-config-form-title">
                          Create Entity Type
                        </div>
                        <div className="cx-ontology-config-field">
                          <label className="cx-ontology-config-label">
                            Type Name <span style={{ color: 'var(--color-danger, #ef4444)' }}>*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. Microservice"
                            value={newKind.label}
                            onChange={e => setNewKind(prev => ({ ...prev, label: e.target.value }))}
                            className="form-input"
                            autoFocus
                            onKeyDown={e => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleAddNewKind();
                              }
                            }}
                          />
                        </div>

                        <div className="cx-ontology-config-field" style={{ marginTop: 8 }}>
                          <label className="cx-ontology-config-label">
                            Description (Optional)
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. Independent deployment service unit"
                            value={newKind.description || ''}
                            onChange={e => setNewKind(prev => ({ ...prev, description: e.target.value }))}
                            className="form-input"
                            onKeyDown={e => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleAddNewKind();
                              }
                            }}
                          />
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
                          <button
                            type="button"
                            onClick={() => {
                              setIsAddingNewKind(false);
                              setNewKind({
                                id: '',
                                label: '',
                                description: '',
                                shape: 'circle',
                                baseRadius: 11,
                                tier: 2,
                              });
                            }}
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
                    ) : (
                      <button
                        type="button"
                        onClick={() => setIsAddingNewKind(true)}
                        className="cx-ontology-config-add-box"
                        title="Add a new entity type"
                      >
                        <Plus size={14} />
                        <span>Add Type</span>
                      </button>
                    )}
                  </div>
                </div>
              )}

            {/* ─── TAB 2: Type Relationships (Metamodel) ──────────────────── */}
            {activeTab === 'relations' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {groupedPairs.map(pair => {
                  const srcKind = kindsConfig.find(k => k.id === pair.source_type_id);
                  const tgtKind = kindsConfig.find(k => k.id === pair.target_type_id);
                  const isAddingInline = inlineAddPairKey === pair.pairKey;

                  return (
                    <div key={pair.pairKey} className="cx-ontology-pair-card">
                      <div className="cx-ontology-pair-header">
                        <div className="cx-ontology-pair-title">
                          <span className="cx-ontology-type-chip">
                            <span style={{ color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center' }}>
                              {srcKind && getShapeIcon(srcKind.shape)}
                            </span>
                            <span>{srcKind?.label || pair.source_type_id}</span>
                          </span>

                          <span className="cx-ontology-pair-arrow">
                            <ArrowRight size={13} />
                          </span>

                          <span className="cx-ontology-type-chip">
                            <span style={{ color: 'var(--color-primary)', display: 'inline-flex', alignItems: 'center' }}>
                              {tgtKind && getShapeIcon(tgtKind.shape)}
                            </span>
                            <span>{tgtKind?.label || pair.target_type_id}</span>
                          </span>
                        </div>

                        {!pair.hasSystemRelation && (
                          <button
                            type="button"
                            onClick={() => handleDeletePair(pair)}
                            className="cx-ontology-config-icon-btn is-danger"
                            title="Delete all relations for this pair"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>

                      <div className="cx-ontology-pair-relations">
                        {pair.relations.map(rel => (
                          <span
                            key={`${rel.source_type_id}-${rel.relation_type}-${rel.target_type_id}`}
                            className={`cx-ontology-relation-pill ${rel.is_hierarchical ? 'is-hierarchical' : ''}`}
                            title={rel.description || undefined}
                          >
                            <span>{rel.relation_type}</span>
                            {rel.is_hierarchical && (
                              <span className="cx-ontology-hier-badge" style={{ fontSize: '8px', padding: '0 3px' }}>
                                Hierarchy
                              </span>
                            )}
                            {!rel.is_system && (
                              <button
                                type="button"
                                onClick={() => handleDeleteSingleRelation(rel)}
                                className="cx-ontology-relation-pill-del"
                                title={`Remove ${rel.relation_type} relation`}
                              >
                                <X size={10} />
                              </button>
                            )}
                          </span>
                        ))}

                        {/* Inline Quick Add Relation */}
                        {isAddingInline ? (
                          <form
                            onSubmit={e => {
                              e.preventDefault();
                              handleInlineAddRelation(pair.source_type_id, pair.target_type_id);
                            }}
                            className="cx-ontology-add-rel-inline-form"
                          >
                            <input
                              type="text"
                              placeholder="e.g. calls"
                              value={inlineRelationName}
                              onChange={e => setInlineRelationName(e.target.value)}
                              className="cx-ontology-add-rel-inline-input"
                              autoFocus
                              onKeyDown={e => {
                                if (e.key === 'Escape') {
                                  setInlineAddPairKey(null);
                                  setInlineRelationName('');
                                }
                              }}
                            />
                            <button
                              type="submit"
                              className="cx-ontology-config-icon-btn"
                              style={{ width: 20, height: 20, color: 'var(--color-primary)' }}
                              title="Add relation"
                            >
                              <Check size={11} />
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setInlineAddPairKey(null);
                                setInlineRelationName('');
                              }}
                              className="cx-ontology-config-icon-btn"
                              style={{ width: 20, height: 20 }}
                              title="Cancel"
                            >
                              <X size={11} />
                            </button>
                          </form>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setInlineAddPairKey(pair.pairKey);
                              setInlineRelationName('');
                            }}
                            className="cx-ontology-add-rel-inline-btn"
                            title="Add relationship type to this pair"
                          >
                            <Plus size={11} />
                            <span>Add Relation</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Dotted Add Rule Box / Inline Form sticky at the bottom */}
                <div className="cx-ontology-config-sticky-footer">
                  {isAddingNewRelation ? (
                    <div className="cx-ontology-config-form" style={{ marginTop: 2 }}>
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
                                {k.label || k.id}
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
                                {k.label || k.id}
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

                      <div className="cx-ontology-config-field" style={{ marginTop: 6 }}>
                        <label className="cx-ontology-config-label">
                          Rule Description (Optional)
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Domain contains subdomains in architectural hierarchy"
                          value={newRelation.description || ''}
                          onChange={e => setNewRelation(prev => ({ ...prev, description: e.target.value }))}
                          className="form-input"
                        />
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
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
                  ) : (
                    <button
                      type="button"
                      onClick={() => setIsAddingNewRelation(true)}
                      className="cx-ontology-config-add-box"
                      title="Add a new relationship rule"
                    >
                      <Plus size={14} />
                      <span>Add Rule</span>
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
