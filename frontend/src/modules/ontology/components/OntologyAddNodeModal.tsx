import React, { useState, useEffect, useMemo } from 'react';
import { X, Plus, AlertCircle, Loader2, Check, Lock } from 'lucide-react';
import type { KindConfig, TypeRelationConfig } from '../config/types';
import type { OntologyNode } from '../types/ontology';
import './entity-ui.css';

interface OntologyAddNodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  kindsConfig: KindConfig[];
  typeRelations?: TypeRelationConfig[];
  existingNodes: OntologyNode[];
  initialParentId?: string | null;
  onAddNode: (node: {
    id: string;
    kind: string;
    title: string;
    description?: string;
    parentId?: string | null;
    tags?: string[];
    status?: string;
  }) => Promise<boolean>;
}

export const OntologyAddNodeModal: React.FC<OntologyAddNodeModalProps> = ({
  isOpen,
  onClose,
  kindsConfig,
  typeRelations,
  existingNodes,
  initialParentId,
  onAddNode,
}) => {
  const [title, setTitle] = useState('');
  const [id, setId] = useState('');
  const [kind, setKind] = useState('domain');
  const [parentId, setParentId] = useState<string>('');
  const [description, setDescription] = useState('');
  const [tagsStr, setTagsStr] = useState('');
  const [autoId, setAutoId] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  // Find selected parent node if initialParentId or parentId is set
  const selectedParentNode = useMemo(() => {
    const pId = initialParentId || parentId;
    if (!pId) return null;
    return existingNodes.find(n => n.id === pId) || null;
  }, [initialParentId, parentId, existingNodes]);

  // Compute allowed semantic types (kinds) strictly based on metamodel containment rules for the parent
  const allowedKinds = useMemo(() => {
    if (!selectedParentNode) {
      // When no parent is selected / fixed, allow all registered kinds
      return kindsConfig;
    }

    const parentKind = selectedParentNode.kind;

    // 1. Filter typeRelations for containment rules where source_type_id matches parent's kind
    const containmentRules = (typeRelations || []).filter(
      r => r.source_type_id === parentKind && (r.is_hierarchical || r.relation_type === 'contains')
    );

    if (containmentRules.length > 0) {
      const allowedTypeIds = new Set(containmentRules.map(r => r.target_type_id));
      const matched = kindsConfig.filter(k => allowedTypeIds.has(k.id));
      if (matched.length > 0) {
        return matched;
      }
    }

    // 2. Metamodel tier fallback if no explicit rule is configured: kinds with higher tier than parent
    const parentKindConfig = kindsConfig.find(k => k.id === parentKind);
    const parentTier = parentKindConfig ? parentKindConfig.tier : 0;
    const higherTier = kindsConfig.filter(k => k.tier > parentTier);
    if (higherTier.length > 0) {
      return higherTier;
    }

    // 3. Fallback defaults
    if (parentKind === 'org' || parentKind === 'project') {
      const d = kindsConfig.filter(k => k.id === 'domain');
      if (d.length > 0) return d;
    } else if (parentKind === 'domain') {
      const s = kindsConfig.filter(k => k.id === 'subdomain' || k.id === 'capability');
      if (s.length > 0) return s;
    } else if (parentKind === 'subdomain' || parentKind === 'capability') {
      const e = kindsConfig.filter(k => k.id === 'element');
      if (e.length > 0) return e;
    }

    return kindsConfig;
  }, [selectedParentNode, kindsConfig, typeRelations]);

  // Set default kind and parent on open
  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setId('');
      setDescription('');
      setTagsStr('');
      setAutoId(true);
      setError(null);
      setSuccess(false);

      if (initialParentId) {
        setParentId(initialParentId);
        const parentNode = existingNodes.find(n => n.id === initialParentId);
        if (parentNode) {
          // Look up metamodel hierarchical relation for parentNode.kind
          const rule = (typeRelations || []).find(
            r => r.source_type_id === parentNode.kind && (r.is_hierarchical || r.relation_type === 'contains')
          );
          if (rule && kindsConfig.some(k => k.id === rule.target_type_id)) {
            setKind(rule.target_type_id);
          } else {
            // Find kind with next tier
            const parentKindConfig = kindsConfig.find(k => k.id === parentNode.kind);
            const parentTier = parentKindConfig ? parentKindConfig.tier : 0;
            const nextKind = kindsConfig.find(k => k.tier === parentTier + 1);
            if (nextKind) {
              setKind(nextKind.id);
            } else if (parentNode.kind === 'org' || parentNode.kind === 'project') {
              setKind('domain');
            } else if (parentNode.kind === 'domain') {
              setKind('subdomain');
            } else {
              setKind('element');
            }
          }
        }
      } else {
        setParentId('');
        const defaultK =
          kindsConfig.find(k => k.id !== 'org' && k.id !== 'project')?.id ||
          kindsConfig[0]?.id ||
          'domain';
        setKind(defaultK);
      }
    }
  }, [isOpen, initialParentId, kindsConfig, typeRelations, existingNodes]);

  // Keep kind in sync with allowedKinds whenever allowedKinds changes
  useEffect(() => {
    if (allowedKinds.length > 0 && !allowedKinds.some(k => k.id === kind)) {
      setKind(allowedKinds[0].id);
    }
  }, [allowedKinds, kind]);

  // Auto-generate ID slug from title and kind
  useEffect(() => {
    if (autoId && title) {
      const slug = title
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-');
      let prefix = `${kind}s/`;
      if (kind === 'org') prefix = 'org/';
      else if (kind === 'project') prefix = 'org/';
      else if (kind === 'domain') prefix = 'domains/';
      else if (kind === 'subdomain') prefix = 'subdomains/';
      else if (kind === 'capability') prefix = 'subdomains/';
      else if (kind === 'element') prefix = 'elements/';

      setId(`${prefix}${slug}`);
    }
  }, [title, kind, autoId]);

  // Eligible parent nodes based on kind tier
  const eligibleParents = useMemo(() => {
    const currentKindConfig = kindsConfig.find(k => k.id === kind);
    const targetTier = currentKindConfig ? currentKindConfig.tier : 1;

    // Filter nodes that belong to a higher hierarchy tier (lower tier number) or match initialParentId
    return existingNodes.filter(n => {
      const parentKindConfig = kindsConfig.find(k => k.id === n.kind);
      const pTier = parentKindConfig ? parentKindConfig.tier : 0;
      return pTier < targetTier || n.id === initialParentId;
    });
  }, [kind, kindsConfig, existingNodes, initialParentId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Please provide an entity title.');
      return;
    }
    if (!id.trim()) {
      setError('Please provide a unique slug ID.');
    }

    const tags = tagsStr
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);

    setIsSubmitting(true);
    try {
      const ok = await onAddNode({
        id: id.trim(),
        kind,
        title: title.trim(),
        description: description.trim() || undefined,
        parentId: parentId || null,
        tags,
        status: 'active',
      });
      if (ok) {
        setSuccess(true);
        setTimeout(() => {
          setSuccess(false);
          onClose();
        }, 500);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to add node');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="cx-kg-modal-overlay">
      <div className="cx-kg-modal-content">
        {/* Header */}
        <div className="cx-kg-modal-header">
          <div className="cx-kg-modal-header-left">
            <div className="cx-kg-modal-icon-badge">
              <Plus size={18} />
            </div>
            <div>
              <h3 className="cx-kg-modal-title">
                {selectedParentNode && initialParentId
                  ? `Add Child Entity to "${selectedParentNode.title}"`
                  : 'Add Knowledge Graph Entity'}
              </h3>
              <p className="cx-kg-modal-subtitle">
                {selectedParentNode && initialParentId
                  ? `Creating child node under ${selectedParentNode.kind} (${selectedParentNode.id})`
                  : 'Create a new node in the active database graph'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="cx-kg-modal-close-btn"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="cx-kg-modal-form">
          {error && (
            <div className="cx-kg-alert-error">
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}

          {/* Title */}
          <div className="cx-kg-modal-field">
            <label className="cx-kg-modal-label">
              <span>Display Title <span className="cx-kg-modal-label-required">*</span></span>
            </label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Data Mesh Architecture"
              required
              className="cx-kg-input"
            />
          </div>

          {/* Kind (Entity Type) & Parent */}
          <div className="cx-kg-modal-grid-2">
            <div className="cx-kg-modal-field">
              <label className="cx-kg-modal-label">
                <span>Semantic Type (Kind) <span className="cx-kg-modal-label-required">*</span></span>
                {initialParentId && (
                  <span className="cx-kg-modal-label-badge">Rule Allowed Only</span>
                )}
              </label>
              <select
                value={kind}
                onChange={e => {
                  setKind(e.target.value);
                  if (!initialParentId) {
                    setParentId('');
                  }
                }}
                className="cx-kg-select"
              >
                {allowedKinds.map(k => (
                  <option key={k.id} value={k.id}>
                    {k.label || (k.id === 'org' ? 'Organization' : k.id === 'domain' ? 'Domain' : k.id === 'subdomain' ? 'Subdomain' : k.id === 'element' ? 'Element' : k.id)}
                  </option>
                ))}
              </select>
            </div>

            <div className="cx-kg-modal-field">
              <label className="cx-kg-modal-label">
                <span>Parent Entity</span>
                {initialParentId ? (
                  <span className="cx-kg-modal-label-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                    <Lock size={10} /> Fixed Parent
                  </span>
                ) : (
                  <span className="cx-kg-modal-label-badge">Hierarchy</span>
                )}
              </label>
              <select
                value={parentId}
                onChange={e => setParentId(e.target.value)}
                disabled={Boolean(initialParentId)}
                className={`cx-kg-select ${initialParentId ? 'is-disabled' : ''}`}
              >
                <option value="">(None / Root Apex)</option>
                {eligibleParents.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.title} ({p.kind})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Unique Slug ID */}
          <div className="cx-kg-modal-field">
            <div className="cx-kg-modal-label">
              <span>Unique Node Slug ID <span className="cx-kg-modal-label-required">*</span></span>
              <button
                type="button"
                onClick={() => setAutoId(!autoId)}
                className="cx-kg-modal-label-action"
              >
                {autoId ? 'Manual Edit' : 'Auto-Generate'}
              </button>
            </div>
            <input
              type="text"
              value={id}
              onChange={e => {
                setId(e.target.value);
                setAutoId(false);
              }}
              placeholder="e.g. domains/data-mesh"
              required
              className="cx-kg-input cx-kg-input-mono"
            />
          </div>

          {/* Description */}
          <div className="cx-kg-modal-field">
            <label className="cx-kg-modal-label">
              <span>Description / Documentation</span>
            </label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Summary of architectural responsibilities and boundaries..."
              rows={3}
              className="cx-kg-textarea"
            />
          </div>

          {/* Tags */}
          <div className="cx-kg-modal-field">
            <label className="cx-kg-modal-label">
              <span>Tags (comma separated)</span>
            </label>
            <input
              type="text"
              value={tagsStr}
              onChange={e => setTagsStr(e.target.value)}
              placeholder="e.g. data, architecture, mesh"
              className="cx-kg-input"
            />
          </div>

          {/* Footer Actions */}
          <div className="cx-kg-modal-footer">
            <button
              type="button"
              onClick={onClose}
              className="cx-kg-btn cx-kg-btn-ghost"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="cx-kg-btn cx-kg-btn-primary"
            >
              {isSubmitting ? (
                <Loader2 size={13} className="animate-spin" />
              ) : success ? (
                <Check size={13} />
              ) : (
                <Plus size={13} />
              )}
              <span>{isSubmitting ? 'Saving to DB...' : success ? 'Added!' : 'Add to Knowledge Graph'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};