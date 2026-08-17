import { type ReactNode, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  ArrowLeft, MoreVertical, Pencil, Tag, FileText, Link2, Calendar, History, AlertTriangle, Plus, Trash2, X,
} from 'lucide-react';
import {
  useAssetInstance,
  useAssetAncestors,
  useAssetVersions,
  useAssetEvents,
  useAssetType,
  useAssetRelationships,
  useCreateAssetEvent,
  useDeleteAssetEvent,
  useCreateAssetTag,
  useDeleteAssetTag,
  useCreateRelationship,
  useDeleteRelationship,
  useDeleteAssetInstance,
  useAssetInstances,
  useAssetChildren,
  useAssetTags,
  type AssetStatus,
  type EventSeverity,
  type DocumentType,
  type RelationshipDirection,
  type AssetDocument,
  type AssetEvent,
  type AssetRelationship,
  type AssetTag,
  type AssetTypeTag,
} from '@/modules/asset_manager/hooks/useAssetManager';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { PageTabs } from '@/components/common/PageTabs';
import ConfirmDialog from '@/components/common/ConfirmDialog';
import api from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';

const STATUS_COLOR: Record<AssetStatus, string> = {
  ACTIVE: '#10b981',
  INACTIVE: '#9ca3af',
  DECOMMISSIONED: '#6b7280',
  PLANNED: '#3b82f6',
  MAINTENANCE: '#f59e0b',
};

const SEVERITY_COLOR: Record<EventSeverity, string> = {
  INFO: '#3b82f6',
  WARNING: '#f59e0b',
  CRITICAL: '#ef4444',
};

type Tab = 'details' | 'events' | 'tags' | 'documents' | 'relationships' | 'history';

const ASSET_DETAIL_TABS = [
  { value: 'details' },
  { value: 'events' },
  { value: 'tags' },
  { value: 'documents' },
  { value: 'relationships' },
  { value: 'history' },
] as const satisfies readonly { value: Tab }[];

// â”€â”€ Inline Add Event Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AddEventForm({ assetId, onDone }: { assetId: number; onDone: () => void }) {
  const toast = useToast();
  const createEvent = useCreateAssetEvent();
  const [title, setTitle] = useState('');
  const [eventType, setEventType] = useState('maintenance');
  const [severity, setSeverity] = useState<EventSeverity | ''>('');
  const [description, setDescription] = useState('');
  const [startedAt, setStartedAt] = useState(new Date().toISOString().slice(0, 16));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      await createEvent.mutateAsync({
        asset_id: assetId,
        title: title.trim(),
        event_type: eventType,
        started_at: new Date(startedAt).toISOString(),
        severity: severity || undefined,
        description: description.trim() || undefined,
      });
      toast.success('Event created');
      onDone();
    } catch {
      toast.error('Failed to create event');
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>New Event</span>
        <button type="button" className="icon-btn" onClick={onDone}><X size={14} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <label className="form-label">Title *</label>
          <input className="form-input" value={title} onChange={e => setTitle(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Event Type</label>
          <select className="form-input" value={eventType} onChange={e => setEventType(e.target.value)}>
            {['maintenance', 'inspection', 'alarm', 'note', 'incident'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label">Started At *</label>
          <input className="form-input" type="datetime-local" value={startedAt} onChange={e => setStartedAt(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Severity</label>
          <select className="form-input" value={severity} onChange={e => setSeverity(e.target.value as EventSeverity | '')}>
            <option value="">None</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <label className="form-label">Description</label>
          <input className="form-input" value={description} onChange={e => setDescription(e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary" type="submit" disabled={createEvent.isPending}>
        {createEvent.isPending ? 'Savingâ€¦' : 'Create Event'}
      </button>
    </form>
  );
}

// â”€â”€ Inline Add Tag Link Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AddTagForm({ assetId, tagDefinitions, onDone }: { assetId: number; tagDefinitions: AssetTypeTag[]; onDone: () => void }) {
  const toast = useToast();
  const createTag = useCreateAssetTag();
  const { data: existingTags } = useAssetTags();
  const [tagId, setTagId] = useState('');
  const [tagName, setTagName] = useState('');
  const [parameter, setParameter] = useState('');
  const [unit, setUnit] = useState('');
  const [source, setSource] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);
  const [assetTypeTagId, setAssetTypeTagId] = useState<string>('');

  // Auto-fill tag name/unit/source from existing tag link when tagId matches
  function handleTagIdChange(val: string) {
    setTagId(val);
    const match = (existingTags ?? []).find((t) => t.tag_id === val);
    if (match) {
      if (!tagName) setTagName(match.tag_name);
      if (!unit && match.unit) setUnit(match.unit);
      if (!source && match.source) setSource(match.source);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tagId.trim() || !tagName.trim()) return;
    try {
      await createTag.mutateAsync({
        asset_id: assetId,
        tag_id: tagId.trim(),
        tag_name: tagName.trim(),
        parameter: parameter.trim() || undefined,
        unit: unit.trim() || undefined,
        source: source.trim() || undefined,
        is_primary: isPrimary,
        asset_type_tag_id: assetTypeTagId ? Number(assetTypeTagId) : undefined,
      });
      toast.success('Tag created');
      onDone();
    } catch {
      toast.error('Failed to create tag');
    }
  }

  // Deduplicated tag IDs from all existing links
  const allTagIds = [...new Set((existingTags ?? []).map((t) => t.tag_id))];

  return (
    <form onSubmit={handleSubmit} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>New Tag Link</span>
        <button type="button" className="icon-btn" onClick={onDone}><X size={14} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        {tagDefinitions.length > 0 && (
          <div style={{ gridColumn: '1 / -1' }}>
            <label className="form-label">Tag Type (Definition)</label>
            <select
              className="form-input"
              value={assetTypeTagId}
              onChange={e => {
                const val = e.target.value;
                setAssetTypeTagId(val);
                if (val) {
                  const tagDef = tagDefinitions.find(t => t.id === Number(val));
                  if (tagDef) {
                    if (tagDef.name) setTagName(tagDef.name);
                    if (tagDef.parameter) setParameter(tagDef.parameter);
                    if (tagDef.unit) setUnit(tagDef.unit);
                  }
                }
              }}
            >
              <option value="">Select Tag Type...</option>
              {tagDefinitions.map(t => (
                <option key={t.id} value={t.id}>{t.name} ({t.tag_key})</option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="form-label">Tag ID *</label>
          {allTagIds.length > 0 ? (
            <select
              className="form-input"
              value={tagId}
              onChange={e => handleTagIdChange(e.target.value)}
              required
            >
              <option value="">Select tagâ€¦</option>
              {allTagIds.map((id) => {
                const match = (existingTags ?? []).find((t) => t.tag_id === id);
                return <option key={id} value={id}>{match?.tag_name ?? id}</option>;
              })}
            </select>
          ) : (
            <input
              className="form-input"
              placeholder="e.g. PI:TURBINE.001.POWER"
              value={tagId}
              onChange={e => handleTagIdChange(e.target.value)}
              required
            />
          )}
        </div>
        <div>
          <label className="form-label">Tag Name *</label>
          <input className="form-input" placeholder="e.g. Active Power" value={tagName} onChange={e => setTagName(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Parameter</label>
          <input className="form-input" placeholder="e.g. Active Power" value={parameter} onChange={e => setParameter(e.target.value)} />
        </div>
        <div>
          <label className="form-label">Unit</label>
          <input className="form-input" placeholder="e.g. kW" value={unit} onChange={e => setUnit(e.target.value)} />
        </div>
        <div>
          <label className="form-label">Source</label>
          <input className="form-input" placeholder="e.g. PI Historian" value={source} onChange={e => setSource(e.target.value)} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 20 }}>
          <input type="checkbox" id="is-primary" checked={isPrimary} onChange={e => setIsPrimary(e.target.checked)} />
          <label htmlFor="is-primary" style={{ fontSize: 13 }}>Primary tag</label>
        </div>
      </div>
      <button className="btn btn-primary" type="submit" disabled={createTag.isPending}>
        {createTag.isPending ? 'Savingâ€¦' : 'Add Tag'}
      </button>
    </form>
  );
}

// â”€â”€ Inline Add Document Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AddDocumentForm({ assetId, onDone }: { assetId: number; onDone: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [title, setTitle] = useState('');
  const [type, setType] = useState<DocumentType>('MANUAL');
  const [url, setUrl] = useState('');
  const [version, setVersion] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !url.trim()) return;
    setSaving(true);
    try {
      await api.post('/asset-documents', {
        asset_id: assetId,
        title: title.trim(),
        type,
        url: url.trim(),
        version: version.trim() || undefined,
      });
      qc.invalidateQueries({ queryKey: ['asset-instances', assetId] });
      toast.success('Document added');
      onDone();
    } catch {
      toast.error('Failed to add document');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>New Document</span>
        <button type="button" className="icon-btn" onClick={onDone}><X size={14} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <label className="form-label">Title *</label>
          <input className="form-input" value={title} onChange={e => setTitle(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Type</label>
          <select className="form-input" value={type} onChange={e => setType(e.target.value as DocumentType)}>
            {(['MANUAL', 'CERTIFICATE', 'DRAWING', 'REPORT', 'CONTRACT', 'OTHER'] as DocumentType[]).map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <label className="form-label">URL *</label>
          <input className="form-input" placeholder="https://â€¦" value={url} onChange={e => setUrl(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Version</label>
          <input className="form-input" placeholder="e.g. v2.1" value={version} onChange={e => setVersion(e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary" type="submit" disabled={saving}>
        {saving ? 'Savingâ€¦' : 'Add Document'}
      </button>
    </form>
  );
}

// â”€â”€ Inline Add Relationship Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AddRelationshipForm({ assetId, onDone }: { assetId: number; onDone: () => void }) {
  const toast = useToast();
  const createRel = useCreateRelationship();
  const { data: allAssets } = useAssetInstances({ limit: 500 });
  const [toAssetId, setToAssetId] = useState('');
  const [relType, setRelType] = useState('connected-to');
  const [direction, setDirection] = useState<RelationshipDirection>('BIDIRECTIONAL');
  const [description, setDescription] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!toAssetId) return;
    try {
      await createRel.mutateAsync({
        from_asset_id: assetId,
        to_asset_id: Number(toAssetId),
        type: relType,
        direction,
        description: description.trim() || undefined,
      });
      toast.success('Relationship created');
      onDone();
    } catch {
      toast.error('Failed to create relationship');
    }
  }

  const otherAssets = (allAssets?.data ?? []).filter(a => a.id !== assetId);

  return (
    <form onSubmit={handleSubmit} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>New Relationship</span>
        <button type="button" className="icon-btn" onClick={onDone}><X size={14} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <label className="form-label">Related Asset *</label>
          <select className="form-input" value={toAssetId} onChange={e => setToAssetId(e.target.value)} required>
            <option value="">Select assetâ€¦</option>
            {otherAssets.map(a => (
              <option key={a.id} value={a.id}>{a.name}{a.code ? ` (${a.code})` : ''}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="form-label">Relationship Type</label>
          <input className="form-input" list="rel-types" value={relType} onChange={e => setRelType(e.target.value)} />
          <datalist id="rel-types">
            {['connected-to', 'feeds-into', 'monitors', 'backs-up', 'depends-on', 'redundant-with'].map(t => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </div>
        <div>
          <label className="form-label">Direction</label>
          <select className="form-input" value={direction} onChange={e => setDirection(e.target.value as RelationshipDirection)}>
            <option value="BIDIRECTIONAL">BIDIRECTIONAL</option>
            <option value="UNIDIRECTIONAL">UNIDIRECTIONAL</option>
          </select>
        </div>
        <div>
          <label className="form-label">Description</label>
          <input className="form-input" value={description} onChange={e => setDescription(e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary" type="submit" disabled={createRel.isPending}>
        {createRel.isPending ? 'Savingâ€¦' : 'Add Relationship'}
      </button>
    </form>
  );
}

// â”€â”€ Main Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function AssetDetailPage({
  assetId,
  embedded = false,
  headerActions,
}: {
  assetId?: number;
  embedded?: boolean;
  headerActions?: ReactNode;
} = {}) {
  const { instanceId } = useParams<{ instanceId: string }>();
  const id = assetId ?? Number(instanceId);
  const navigate = useScopedNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('details');
  const [showAddEvent, setShowAddEvent] = useState(false);
  const [showAddTag, setShowAddTag] = useState(false);
  const [showAddDoc, setShowAddDoc] = useState(false);
  const [showAddRel, setShowAddRel] = useState(false);
  const [assetMenuOpen, setAssetMenuOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteBlocked, setDeleteBlocked] = useState(false);
  const [tagPendingDelete, setTagPendingDelete] = useState<AssetTag | null>(null);
  const [documentPendingDelete, setDocumentPendingDelete] = useState<AssetDocument | null>(null);
  const [eventPendingDelete, setEventPendingDelete] = useState<AssetEvent | null>(null);
  const [relationshipPendingDelete, setRelationshipPendingDelete] = useState<AssetRelationship | null>(null);

  const hasAssetId = Number.isFinite(id);
  const { data: asset, isLoading } = useAssetInstance(hasAssetId ? id : undefined);
  const { data: ancestors } = useAssetAncestors(hasAssetId ? id : undefined);
  const { data: versions } = useAssetVersions(tab === 'history' ? id : undefined);
  const { data: events } = useAssetEvents(tab === 'events' ? { asset_id: id } : undefined);
  const { data: assetType } = useAssetType(asset?.asset_type_id);
  const { data: childAssets } = useAssetChildren(hasAssetId ? id : undefined);
  const { data: relationships } = useAssetRelationships(tab === 'relationships' ? { from_asset_id: id } : undefined);
  const { data: tagLinks } = useAssetTags(id);

  const deleteEvent = useDeleteAssetEvent();
  const deleteTag = useDeleteAssetTag();
  const deleteRel = useDeleteRelationship();
  const deleteAsset = useDeleteAssetInstance();

  if (!hasAssetId) return <div className="empty-state">Select an asset from the hierarchy to view details.</div>;
  if (isLoading) return <div className="loading-state">Loading assetâ€¦</div>;
  if (!asset) return <div className="empty-state">Asset not found.</div>;

  const currentAsset = asset;
  const hasChildAssets = (childAssets?.length ?? 0) > 0;
  const isSchemaStale = assetType && asset.metadata_schema_version < assetType.schema_version;

  const resolvedTagLinks = tagLinks ?? [];
  const documents = (asset as unknown as { documents?: AssetDocument[] }).documents ?? [];

  async function handleDeleteDocument(doc: AssetDocument) {
    try {
      await api.delete(`/asset-documents/${doc.id}`);
      qc.invalidateQueries({ queryKey: ['asset-instances', id] });
      toast.success('Document removed');
      setDocumentPendingDelete(null);
    } catch {
      setDocumentPendingDelete(null);
      toast.error('Failed to remove document');
    }
  }

  async function handleDeleteEvent(event: AssetEvent) {
    try {
      await deleteEvent.mutateAsync(event.id);
      toast.success('Event deleted');
      setEventPendingDelete(null);
    } catch {
      setEventPendingDelete(null);
      toast.error('Delete failed');
    }
  }

  async function handleDeleteRelationship(relationship: AssetRelationship) {
    try {
      await deleteRel.mutateAsync(relationship.id);
      toast.success('Relationship removed');
      setRelationshipPendingDelete(null);
    } catch {
      setRelationshipPendingDelete(null);
      toast.error('Remove failed');
    }
  }

  async function handleDeleteTagLink(tagLink: AssetTag) {
    try {
      await deleteTag.mutateAsync(tagLink.id);
      toast.success('Tag removed');
      setTagPendingDelete(null);
    } catch {
      toast.error('Remove failed');
    }
  }

  async function handleDeleteAsset() {
    try {
      await deleteAsset.mutateAsync(id);
      toast.success('Asset deleted');
      setShowDeleteConfirm(false);
      setDeleteBlocked(false);
      navigate('/assets');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Delete failed';
      setShowDeleteConfirm(false);
      if (msg.includes('ASSET_HAS_CHILDREN')) {
        setDeleteBlocked(true);
      } else {
        setDeleteBlocked(false);
      }
      toast.error(msg);
    }
  }

  return (
    <div className={embedded ? undefined : 'page-section asset-page'}>
      {/* Breadcrumb */}
      <div className="asset-detail-breadcrumb">
        {!embedded && (
          <button className="icon-btn" onClick={() => navigate('/assets')} title="Back">
            <ArrowLeft size={14} />
          </button>
        )}
        {(ancestors ?? []).map((a) => (
          <span key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', fontSize: 12 }} onClick={() => navigate(`/assets/${a.id}`)}>
              {a.name}
            </button>
            <span>/</span>
          </span>
        ))}
        <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{asset.name}</span>
      </div>

      {/* Header */}
      <div className="db-page-header">
        <div className="asset-detail-title-row">
          <h1 className="db-page-title" style={{ margin: 0 }}>{asset.name}</h1>
          {asset.code && <span style={{ fontSize: 12, background: 'var(--color-bg)', border: '1px solid var(--color-border)', padding: '2px 8px', borderRadius: 4 }}>{asset.code}</span>}
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: STATUS_COLOR[asset.status], fontWeight: 600 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLOR[asset.status] }} />
            {asset.status}
          </span>
        </div>
        <div className="asset-page-actions" style={{ position: 'relative' }}>
          <button className="icon-btn" onClick={() => setAssetMenuOpen((open) => !open)} title="Asset actions">
            <MoreVertical size={16} />
          </button>
          {headerActions}
          {assetMenuOpen && (
            <div className="asset-inline-menu">
              <button
                onClick={() => {
                  setAssetMenuOpen(false);
                  navigate(`/assets/${id}/edit`);
                }}
              >
                <Pencil size={14} /> Edit
              </button>
              <button
                onClick={() => {
                  setAssetMenuOpen(false);
                  setDeleteBlocked(false);
                  setShowDeleteConfirm(true);
                }}
                disabled={deleteAsset.isPending}
              >
                <Trash2 size={14} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {isSchemaStale && (
        <div style={{ background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: 6, padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 12 }}>
          <AlertTriangle size={14} color="#f59e0b" />
          Schema updated (type v{assetType?.schema_version}, this asset v{asset.metadata_schema_version}). Review and re-save to update.
        </div>
      )}

      {/* Tabs */}
      <PageTabs tabs={ASSET_DETAIL_TABS} value={tab} onChange={setTab} />

      {tagPendingDelete && (
        <ConfirmDialog
          title="Remove tag link"
          message={`Remove "${tagPendingDelete.tag_name}" from this asset?`}
          confirmLabel="Remove"
          onCancel={() => setTagPendingDelete(null)}
          onConfirm={() => handleDeleteTagLink(tagPendingDelete)}
          isLoading={deleteTag.isPending}
        />
      )}

      {documentPendingDelete && (
        <ConfirmDialog
          title="Remove document"
          message={`Remove "${documentPendingDelete.title}" from this asset?`}
          confirmLabel="Remove"
          onCancel={() => setDocumentPendingDelete(null)}
          onConfirm={() => handleDeleteDocument(documentPendingDelete)}
          isLoading={false}
        />
      )}

      {eventPendingDelete && (
        <ConfirmDialog
          title="Delete event"
          message={`Delete "${eventPendingDelete.title}"? This action cannot be undone.`}
          confirmLabel="Delete"
          onCancel={() => setEventPendingDelete(null)}
          onConfirm={() => handleDeleteEvent(eventPendingDelete)}
          isLoading={deleteEvent.isPending}
        />
      )}

      {relationshipPendingDelete && (
        <ConfirmDialog
          title="Remove relationship"
          message={`Remove this "${relationshipPendingDelete.type}" relationship?`}
          confirmLabel="Remove"
          onCancel={() => setRelationshipPendingDelete(null)}
          onConfirm={() => handleDeleteRelationship(relationshipPendingDelete)}
          isLoading={deleteRel.isPending}
        />
      )}

      {showDeleteConfirm && (
        <ConfirmDialog
          title={hasChildAssets || deleteBlocked ? "Cannot delete asset" : "Delete asset"}
          message={
            hasChildAssets || deleteBlocked
              ? `"${currentAsset.name}" has child assets. Move or delete its child assets first, then try again.`
              : `Delete "${currentAsset.name}"? This action cannot be undone.`
          }
          confirmLabel="Delete"
          onCancel={() => {
            setShowDeleteConfirm(false);
            setDeleteBlocked(false);
          }}
          onConfirm={handleDeleteAsset}
          isLoading={deleteAsset.isPending}
          hideConfirm={hasChildAssets || deleteBlocked}
        />
      )}

      {/* â”€â”€ Details â”€â”€ */}
      {tab === 'details' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <section style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600 }}>Core Info</h3>
            <table style={{ width: '100%', fontSize: 13 }}>
              <tbody>
                {[
                  ['Type', asset.asset_type_name ?? String(asset.asset_type_id)],
                  ['Description', asset.description ?? 'â€”'],
                  ['Path', asset.path],
                  ['Depth', String(asset.depth)],
                  ['Commissioned', asset.commissioned_at ? new Date(asset.commissioned_at).toLocaleDateString() : 'â€”'],
                  ['Address', asset.address ?? 'â€”'],
                  ['Coordinates', asset.latitude != null ? `${asset.latitude}, ${asset.longitude}` : 'â€”'],
                  ['Created by', asset.created_by ?? 'â€”'],
                  ['Updated', new Date(asset.updated_at).toLocaleString()],
                ].map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ color: 'var(--color-text-muted)', paddingBottom: 6, paddingRight: 12, whiteSpace: 'nowrap' }}>{k}</td>
                    <td style={{ paddingBottom: 6, wordBreak: 'break-all' }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600 }}>Metadata</h3>
            {Object.keys(asset.metadata).length === 0 ? (
              <p style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>No metadata values.</p>
            ) : (
              <table style={{ width: '100%', fontSize: 13 }}>
                <tbody>
                  {Object.entries(asset.metadata).map(([k, v]) => {
                    const fieldDef = assetType?.metadata_schema?.fields?.find((f) => f.key === k);
                    return (
                      <tr key={k}>
                        <td style={{ color: 'var(--color-text-muted)', paddingBottom: 6, paddingRight: 12 }}>
                          {fieldDef?.label ?? k}
                          {fieldDef?.unit && <span style={{ fontSize: 10, marginLeft: 4 }}>{fieldDef.unit}</span>}
                        </td>
                        <td style={{ paddingBottom: 6 }}>{String(v)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>
        </div>
      )}

      {/* â”€â”€ Events â”€â”€ */}
      {tab === 'events' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            {!showAddEvent && (
              <button className="btn btn-primary" onClick={() => setShowAddEvent(true)}>
                <Plus size={13} /> Add Event
              </button>
            )}
          </div>
          {showAddEvent && <AddEventForm assetId={id} onDone={() => setShowAddEvent(false)} />}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(events ?? []).length === 0 ? (
              <div className="empty-state"><Calendar size={32} color="var(--color-text-muted)" /><p>No events for this asset.</p></div>
            ) : (
              (events ?? []).map((e) => (
                <div key={e.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{e.title}</span>
                    {e.severity && (
                      <span style={{ fontSize: 10, fontWeight: 700, color: SEVERITY_COLOR[e.severity], background: SEVERITY_COLOR[e.severity] + '22', padding: '1px 6px', borderRadius: 4 }}>{e.severity}</span>
                    )}
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{e.event_type}</span>
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginLeft: 'auto' }}>{new Date(e.started_at).toLocaleString()}</span>
                    <button className="icon-btn danger" onClick={() => setEventPendingDelete(e)} title="Delete">
                      <Trash2 size={13} />
                    </button>
                  </div>
                  {e.description && <p style={{ margin: 0, fontSize: 12, color: 'var(--color-text-muted)' }}>{e.description}</p>}
                  {e.source && <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Source: {e.source}</span>}
                  {e.external_ref && <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginLeft: 8 }}>Ref: {e.external_ref}</span>}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* â”€â”€ Tags â”€â”€ */}
      {tab === 'tags' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            {!showAddTag && (
              <button className="btn btn-primary" onClick={() => setShowAddTag(true)}>
                <Plus size={13} /> Add Tag Link
              </button>
            )}
          </div>
          {showAddTag && <AddTagForm assetId={id} tagDefinitions={assetType?.tag_definitions ?? []} onDone={() => setShowAddTag(false)} />}
          {resolvedTagLinks.length === 0 && !showAddTag ? (
            <div className="empty-state"><Tag size={32} color="var(--color-text-muted)" /><p>No tags linked. Add a time-series tag reference.</p></div>
          ) : (
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr><th>Tag ID</th><th>Name</th><th>Tag Type</th><th>Parameter</th><th>Unit</th><th>Source</th><th>Primary</th><th /></tr>
              </thead>
              <tbody>
                {resolvedTagLinks.map((t) => (
                  <tr key={t.id}>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{t.tag_id}</td>
                    <td>{t.tag_name}</td>
                    <td>{t.asset_type_tag?.name ? `${t.asset_type_tag.name} (${t.asset_type_tag.tag_key})` : 'â€”'}</td>
                    <td>{t.parameter ?? 'â€”'}</td>
                    <td>{t.unit ?? 'â€”'}</td>
                    <td style={{ fontSize: 12 }}>{t.source ?? 'â€”'}</td>
                    <td>{t.is_primary ? 'âœ“' : ''}</td>
                    <td>
                      <button className="icon-btn danger" onClick={() => setTagPendingDelete(t)} title="Remove">
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* â”€â”€ Documents â”€â”€ */}
      {tab === 'documents' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            {!showAddDoc && (
              <button className="btn btn-primary" onClick={() => setShowAddDoc(true)}>
                <Plus size={13} /> Add Document
              </button>
            )}
          </div>
          {showAddDoc && <AddDocumentForm assetId={id} onDone={() => setShowAddDoc(false)} />}
          {documents.length === 0 && !showAddDoc ? (
            <div className="empty-state"><FileText size={32} color="var(--color-text-muted)" /><p>No documents linked.</p></div>
          ) : (
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr><th>Title</th><th>Type</th><th>Version</th><th>Uploaded</th><th>URL</th><th /></tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id}>
                    <td style={{ fontWeight: 500 }}>{d.title}</td>
                    <td><span style={{ fontSize: 11, background: 'var(--color-bg)', border: '1px solid var(--color-border)', padding: '1px 6px', borderRadius: 4 }}>{d.type}</span></td>
                    <td style={{ fontSize: 12 }}>{d.version ?? 'â€”'}</td>
                    <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{new Date(d.uploaded_at).toLocaleDateString()}</td>
                    <td>
                      <a href={d.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: 'var(--color-primary)' }}>
                        Open â†—
                      </a>
                    </td>
                    <td>
                      <button className="icon-btn danger" onClick={() => setDocumentPendingDelete(d)} title="Remove">
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* â”€â”€ Relationships â”€â”€ */}
      {tab === 'relationships' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            {!showAddRel && (
              <button className="btn btn-primary" onClick={() => setShowAddRel(true)}>
                <Plus size={13} /> Add Relationship
              </button>
            )}
          </div>
          {showAddRel && <AddRelationshipForm assetId={id} onDone={() => setShowAddRel(false)} />}
          {(relationships ?? []).length === 0 && !showAddRel ? (
            <div className="empty-state"><Link2 size={32} color="var(--color-text-muted)" /><p>No relationships defined.</p></div>
          ) : (
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr><th>Related Asset ID</th><th>Type</th><th>Direction</th><th>Description</th><th /></tr>
              </thead>
              <tbody>
                {(relationships ?? []).map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', fontSize: 12 }}
                        onClick={() => navigate(`/assets/${r.to_asset_id}`)}>
                        #{r.to_asset_id}
                      </button>
                    </td>
                    <td><span style={{ fontSize: 11, background: 'var(--color-bg)', border: '1px solid var(--color-border)', padding: '1px 6px', borderRadius: 4 }}>{r.type}</span></td>
                    <td style={{ fontSize: 12 }}>{r.direction}</td>
                    <td style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{r.description ?? 'â€”'}</td>
                    <td>
                      <button className="icon-btn danger" onClick={() => setRelationshipPendingDelete(r)} title="Remove">
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* â”€â”€ History â”€â”€ */}
      {tab === 'history' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {(versions ?? []).length === 0 ? (
            <div className="empty-state"><History size={32} color="var(--color-text-muted)" /><p>No version history.</p></div>
          ) : (
            (versions ?? []).map((v) => (
              <div key={v.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 12, fontWeight: 700, background: 'var(--color-bg)', border: '1px solid var(--color-border)', padding: '2px 8px', borderRadius: 4 }}>v{v.version}</span>
                <span style={{ fontSize: 13, flex: 1 }}>{v.change_summary ?? 'No summary'}</span>
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{v.changed_by ?? 'â€”'}</span>
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{new Date(v.changed_at).toLocaleString()}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

