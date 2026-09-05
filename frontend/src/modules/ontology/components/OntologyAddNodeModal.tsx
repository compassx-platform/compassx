import React, { useState, useEffect, useMemo } from 'react';
import { X, Plus, AlertCircle, Loader2, Check } from 'lucide-react';
import type { KindConfig } from '../config/types';
import type { OntologyNode } from '../types/ontology';
import './entity-ui.css';

interface OntologyAddNodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  kindsConfig: KindConfig[];
  existingNodes: OntologyNode[];
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
  existingNodes,
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

  // Set default kind on open
  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setId('');
      const defaultK = kindsConfig.find(k => k.id !== 'org' && k.id !== 'project')?.id || kindsConfig[0]?.id || 'domain';
      setKind(defaultK);
      setParentId('');
      setDescription('');
      setTagsStr('');
      setAutoId(true);
      setError(null);
      setSuccess(false);
    }
  }, [isOpen, kindsConfig]);

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

    // Filter nodes that belong to a higher hierarchy tier (lower tier number)
    return existingNodes.filter(n => {
      const parentKindConfig = kindsConfig.find(k => k.id === n.kind);
      const pTier = parentKindConfig ? parentKindConfig.tier : 0;
      return pTier < targetTier;
    });
  }, [kind, kindsConfig, existingNodes]);

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
                Add Knowledge Graph Entity
              </h3>
              <p className="cx-kg-modal-subtitle">
                Create a new node in the active database graph
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
              </label>
              <select
                value={kind}
                onChange={e => {
                  setKind(e.target.value);
                  setParentId('');
                }}
                className="cx-kg-select"
              >
                {kindsConfig.map(k => (
                  <option key={k.id} value={k.id}>
                    {k.label} ({k.id})
                  </option>
                ))}
              </select>
            </div>

            <div className="cx-kg-modal-field">
              <label className="cx-kg-modal-label">
                <span>Parent Entity</span>
                <span className="cx-kg-modal-label-badge">Hierarchy</span>
              </label>
              <select
                value={parentId}
                onChange={e => setParentId(e.target.value)}
                className="cx-kg-select"
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