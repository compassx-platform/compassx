import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  Check,
  Hexagon,
  Square,
  Circle,
  Hash,
  ArrowDownLeft,
  ArrowUpRight,
  Tag,
  Sparkles,
  Edit2,
  Trash2,
  Save,
  Link,
  Plus,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { LayoutNode, OntologyKind, OntologyNode } from '../types/ontology';
import type { KindConfig } from '../config/types';
import '../config/config.css';
import './entity-ui.css';

interface OntologySideDrawerProps {
  node: LayoutNode | null;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  onIsolateArea: (nodeId: string) => void;
  onOpenAddChildNode?: (parentId: string) => void;
  onUpdateNode?: (nodeId: string, updates: { title?: string; description?: string; tags?: string[]; status?: string }) => Promise<boolean>;
  onDeleteNode?: (nodeId: string) => Promise<boolean>;
  onAddEdge?: (edge: { source: string; target: string; type: string; description?: string }) => Promise<boolean>;
  kindsConfig?: KindConfig[];
  allNodes?: OntologyNode[];
}

export const OntologySideDrawer: React.FC<OntologySideDrawerProps> = ({
  node,
  onClose,
  onSelectNode,
  onIsolateArea,
  onOpenAddChildNode,
  onUpdateNode,
  onDeleteNode,
  onAddEdge,
  kindsConfig = [],
  allNodes = [],
}) => {
  const [copied, setCopied] = useState(false);

  // Edit Mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editStatus, setEditStatus] = useState('active');
  const [isSaving, setIsSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Add Edge Mode state
  const [isAddingEdge, setIsAddingEdge] = useState(false);
  const [targetNodeId, setTargetNodeId] = useState('');
  const [relationType, setRelationType] = useState('depends_on');
  const [isSavingEdge, setIsSavingEdge] = useState(false);
  const [edgeError, setEdgeError] = useState<string | null>(null);

  // Delete Confirmation state
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (node) {
      setEditTitle(node.title || '');
      setEditDescription(node.description || '');
      setEditTags((node.tags || []).join(', '));
      setEditStatus(node.status || 'active');
      setIsEditing(false);
      setIsAddingEdge(false);
      setIsConfirmingDelete(false);
      setEditError(null);
      setEdgeError(null);
    }
  }, [node]);

  // Drawer width state with left-border drag resizing matching OntologyConfigPanel
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
      if (event.key === 'Escape') {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!node) return null;

  const handleCopyPrompt = () => {
    const aiContext = `---
concept: "${node.title}"
kind: "${node.kind}"
slug: "${node.id}"
${node.parentId ? `parent: "${node.parentId}"\n` : ''}description: "${node.description || ''}"
${node.path ? `path: "${node.path}"\n` : ''}direct_children: ${node.directChildCount || 0}
total_descendants: ${node.totalDescendantCount || 0}
inbound_uses: [${(node.inboundDependencies || []).map(d => `"${d}"`).join(', ')}]
outbound_needs: [${(node.outboundDependencies || []).map(d => `"${d}"`).join(', ')}]
---

# ${node.title} (${node.kind})
${node.description || ''}
`;
    navigator.clipboard.writeText(aiContext);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveNode = async () => {
    if (!onUpdateNode) return;
    setEditError(null);
    setIsSaving(true);
    try {
      const tags = editTags.split(',').map(t => t.trim()).filter(Boolean);
      const ok = await onUpdateNode(node.id, {
        title: editTitle.trim() || node.title,
        description: editDescription.trim(),
        tags,
        status: editStatus,
      });
      if (ok) {
        setIsEditing(false);
      }
    } catch (err: any) {
      setEditError(err?.response?.data?.detail || err.message || 'Failed to update node');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!onDeleteNode) return;
    setIsDeleting(true);
    try {
      const ok = await onDeleteNode(node.id);
      if (ok) {
        onClose();
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || err.message || 'Failed to delete node');
    } finally {
      setIsDeleting(false);
      setIsConfirmingDelete(false);
    }
  };

  const handleSaveEdge = async () => {
    if (!onAddEdge || !targetNodeId) return;
    setEdgeError(null);
    setIsSavingEdge(true);
    try {
      const ok = await onAddEdge({
        source: node.id,
        target: targetNodeId,
        type: relationType,
      });
      if (ok) {
        setIsAddingEdge(false);
        setTargetNodeId('');
      }
    } catch (err: any) {
      setEdgeError(err?.response?.data?.detail || err.message || 'Failed to create connection');
    } finally {
      setIsSavingEdge(false);
    }
  };

  const getKindBadge = (kind: OntologyKind) => {
    switch (kind) {
      case 'org':
      case 'project':
        return (
          <span className="cx-kg-kind-badge cx-kg-kind-org">
            <Hexagon size={12} /> Organization
          </span>
        );
      case 'domain':
        return (
          <span className="cx-kg-kind-badge cx-kg-kind-domain">
            <Square size={12} /> Domain
          </span>
        );
      case 'subdomain':
      case 'capability':
        return (
          <span className="cx-kg-kind-badge cx-kg-kind-subdomain">
            <Circle size={12} /> Subdomain
          </span>
        );
      case 'element':
        return (
          <span className="cx-kg-kind-badge cx-kg-kind-element">
            <svg
              width={12}
              height={12}
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
            Element
          </span>
        );
      default:
        return (
          <span className="cx-kg-kind-badge cx-kg-kind-custom">
            <Sparkles size={12} /> {kind}
          </span>
        );
    }
  };

  return (
    <div
      ref={panelRef}
      className="cx-ontology-config-panel cx-kg-drawer-standard"
      style={{ width: `${panelWidth}px`, maxWidth: 'calc(100vw - 20px)' }}
    >
      {/* Left-edge Drag Resize Handle */}
      <div
        onMouseDown={handleMouseDown}
        className={`cx-ontology-config-resize-handle ${isDragging ? 'is-dragging' : ''}`}
        title="Drag to resize panel width"
      />

      {/* Header */}
      <div className="cx-ontology-config-header cx-kg-drawer-header-standard">
        <div className="cx-kg-drawer-header-left">
          <div className="cx-kg-drawer-badges-row">
            {getKindBadge(node.kind)}
            {node.status && !isEditing && (
              <span className="cx-kg-status-badge">
                {node.status}
              </span>
            )}
          </div>

          {isEditing ? (
            <input
              type="text"
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              className="cx-kg-input"
              style={{ fontWeight: 600, fontSize: 14 }}
              autoFocus
            />
          ) : (
            <h2 className="cx-kg-drawer-title">
              {node.title}
            </h2>
          )}

          <p className="cx-kg-drawer-id" title={node.id}>
            {node.id}
          </p>
        </div>

        <div className="cx-kg-drawer-header-actions">
          {onOpenAddChildNode && !isEditing && (
            <button
              type="button"
              onClick={() => onOpenAddChildNode(node.id)}
              className="cx-ontology-config-close-btn"
              title="Add child entity under this node"
            >
              <Plus size={15} />
            </button>
          )}
          {onUpdateNode && !isEditing && (
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              className="cx-ontology-config-close-btn"
              title="Edit entity"
            >
              <Edit2 size={14} />
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="cx-ontology-config-close-btn"
            title="Close drawer"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Body Content */}
      <div className="cx-ontology-config-body cx-kg-drawer-body-standard cx-kg-scrollbar">
        {editError && (
          <div className="cx-kg-alert-error">
            <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>{editError}</span>
          </div>
        )}

        {/* Edit Form or Read View */}
        {isEditing ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="cx-kg-modal-field">
              <label className="cx-kg-modal-label">Description</label>
              <textarea
                value={editDescription}
                onChange={e => setEditDescription(e.target.value)}
                rows={3}
                className="cx-kg-textarea"
                placeholder="Entity description..."
              />
            </div>

            <div className="cx-kg-modal-field">
              <label className="cx-kg-modal-label">Tags (comma separated)</label>
              <input
                type="text"
                value={editTags}
                onChange={e => setEditTags(e.target.value)}
                className="cx-kg-input"
                placeholder="tag1, tag2"
              />
            </div>

            <div className="cx-kg-modal-field">
              <label className="cx-kg-modal-label">Status</label>
              <select
                value={editStatus}
                onChange={e => setEditStatus(e.target.value)}
                className="cx-kg-select"
              >
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="deprecated">Deprecated</option>
                <option value="archived">Archived</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 4 }}>
              <button
                type="button"
                onClick={handleSaveNode}
                disabled={isSaving}
                className="cx-kg-btn cx-kg-btn-primary"
                style={{ flex: 1 }}
              >
                {isSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
              </button>
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="cx-kg-btn cx-kg-btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Description */}
            {node.description && (
              <div>
                <div className="cx-kg-drawer-section-title">Description</div>
                <div className="cx-kg-drawer-card">
                  <p className="cx-kg-drawer-description">
                    {node.description}
                  </p>
                </div>
              </div>
            )}

            {/* Dual Channel Metrics Cards */}
            <div className="cx-kg-drawer-metrics-grid">
              <div className="cx-kg-drawer-metric-card">
                <div className="cx-kg-drawer-metric-header">
                  <span>Direct Children</span>
                  {onOpenAddChildNode ? (
                    <button
                      type="button"
                      onClick={() => onOpenAddChildNode(node.id)}
                      className="cx-kg-drawer-add-child-action"
                      title="Add child entity under this node"
                    >
                      <Plus size={11} />
                      <span>Add</span>
                    </button>
                  ) : (
                    <span className="cx-kg-drawer-metric-hint">Glance</span>
                  )}
                </div>
                <div className="cx-kg-drawer-metric-val">
                  {node.directChildCount || 0}
                </div>
              </div>
              <div className="cx-kg-drawer-metric-card">
                <div className="cx-kg-drawer-metric-header">
                  <span>Descendants</span>
                  <span className="cx-kg-drawer-metric-hint">Depth</span>
                </div>
                <div className="cx-kg-drawer-metric-val is-amber">
                  {node.totalDescendantCount || 0}
                </div>
              </div>
            </div>

            {/* Inbound & Outbound Connections */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Outbound Needs */}
              <div className="cx-kg-drawer-conn-section">
                <div className="cx-kg-drawer-conn-head">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <ArrowUpRight size={13} style={{ color: 'var(--color-primary)' }} /> Needs (Requires)
                  </span>
                  <span className="cx-kg-drawer-conn-count">
                    {(node.outboundDependencies || []).length}
                  </span>
                </div>
                {(node.outboundDependencies || []).length === 0 ? (
                  <p className="cx-kg-drawer-empty-text">No direct outbound requirements.</p>
                ) : (
                  <div className="cx-kg-drawer-conn-chips">
                    {(node.outboundDependencies || []).map(depId => (
                      <button
                        key={depId}
                        type="button"
                        onClick={() => onSelectNode(depId)}
                        className="cx-kg-drawer-conn-chip"
                        title={depId}
                      >
                        {depId.split('/').pop()}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Inbound Uses */}
              <div className="cx-kg-drawer-conn-section">
                <div className="cx-kg-drawer-conn-head">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <ArrowDownLeft size={13} style={{ color: 'var(--color-info-text)' }} /> Uses (Depended On By)
                  </span>
                  <span className="cx-kg-drawer-conn-count">
                    {(node.inboundDependencies || []).length}
                  </span>
                </div>
                {(node.inboundDependencies || []).length === 0 ? (
                  <p className="cx-kg-drawer-empty-text">No inbound dependents recorded.</p>
                ) : (
                  <div className="cx-kg-drawer-conn-chips">
                    {(node.inboundDependencies || []).map(depId => (
                      <button
                        key={depId}
                        type="button"
                        onClick={() => onSelectNode(depId)}
                        className="cx-kg-drawer-conn-chip"
                        title={depId}
                      >
                        {depId.split('/').pop()}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Add Relationship Form */}
            {isAddingEdge ? (
              <div className="cx-kg-drawer-rel-box">
                <div className="cx-kg-drawer-rel-box-head">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-primary)' }}>
                    <Link size={13} /> Add Relationship
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsAddingEdge(false)}
                    className="cx-kg-drawer-icon-btn"
                    style={{ width: 24, height: 24 }}
                  >
                    <X size={13} />
                  </button>
                </div>

                {edgeError && (
                  <div className="cx-kg-alert-error" style={{ padding: '6px 10px', fontSize: 11 }}>
                    {edgeError}
                  </div>
                )}

                <div className="cx-kg-modal-field">
                  <label className="cx-kg-modal-label">Relation Type</label>
                  <select
                    value={relationType}
                    onChange={e => setRelationType(e.target.value)}
                    className="cx-kg-select"
                  >
                    <option value="depends_on">depends_on</option>
                    <option value="relies_on">relies_on</option>
                    <option value="reads">reads</option>
                    <option value="relates">relates</option>
                    <option value="contains">contains</option>
                  </select>
                </div>

                <div className="cx-kg-modal-field">
                  <label className="cx-kg-modal-label">Target Entity</label>
                  <select
                    value={targetNodeId}
                    onChange={e => setTargetNodeId(e.target.value)}
                    className="cx-kg-select"
                  >
                    <option value="">Select target node...</option>
                    {allNodes
                      .filter(n => n.id !== node.id)
                      .map(n => (
                        <option key={n.id} value={n.id}>
                          {n.title} ({n.kind})
                        </option>
                      ))}
                  </select>
                </div>

                <button
                  type="button"
                  onClick={handleSaveEdge}
                  disabled={isSavingEdge || !targetNodeId}
                  className="cx-kg-btn cx-kg-btn-primary"
                  style={{ width: '100%' }}
                >
                  {isSavingEdge ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                  <span>Save Relationship</span>
                </button>
              </div>
            ) : onAddEdge && (
              <button
                type="button"
                onClick={() => setIsAddingEdge(true)}
                className="cx-kg-btn cx-kg-btn-secondary"
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <Plus size={13} />
                <span>Add Relationship Connection</span>
              </button>
            )}

            {/* Tags */}
            {node.tags && node.tags.length > 0 && (
              <div>
                <div className="cx-kg-drawer-section-title">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <Tag size={12} /> Semantic Tags
                  </span>
                </div>
                <div className="cx-kg-drawer-tags-wrap">
                  {node.tags.map(t => (
                    <span key={t} className="cx-kg-drawer-tag">
                      #{t}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Delete Confirmation Box */}
      {isConfirmingDelete && (
        <div className="cx-kg-drawer-delete-confirm">
          <div className="cx-kg-drawer-delete-title">
            Delete "{node.title}" from Knowledge Graph?
          </div>
          <p className="cx-kg-drawer-delete-desc">
            This will permanently remove this node and all its connected relationships from the database.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 4 }}>
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className="cx-kg-btn cx-kg-btn-danger"
              style={{ flex: 1 }}
            >
              {isDeleting ? 'Deleting...' : 'Confirm Delete'}
            </button>
            <button
              type="button"
              onClick={() => setIsConfirmingDelete(false)}
              className="cx-kg-btn cx-kg-btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Footer Actions */}
      {!isConfirmingDelete && (
        <div className="cx-kg-drawer-footer">
          <button
            type="button"
            onClick={handleCopyPrompt}
            className="cx-kg-btn cx-kg-btn-primary"
            style={{ flex: 1 }}
          >
            {copied ? <Check size={14} /> : <Sparkles size={14} />}
            <span>{copied ? 'Copied AI Context!' : 'Copy for AI'}</span>
          </button>

          <button
            type="button"
            onClick={() => onIsolateArea(node.id)}
            className="cx-kg-btn cx-kg-btn-secondary"
            title="Isolate this subtree"
          >
            Isolate
          </button>

          {onDeleteNode && (
            <button
              type="button"
              onClick={() => setIsConfirmingDelete(true)}
              className="cx-kg-btn cx-kg-btn-secondary"
              style={{ padding: '8px 10px' }}
              title="Delete node from database"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      )}
    </div>
  );
};

