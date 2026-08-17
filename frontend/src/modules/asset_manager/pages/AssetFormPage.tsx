import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Box, ArrowLeft } from 'lucide-react';
import {
  useAssetInstance,
  useAssetInstances,
  useAssetTypes,
  useAssetType,
  useCreateAssetInstance,
  useReparentAsset,
  useUpdateAssetInstance,
  useUpdateAssetStatus,
  type AssetStatus,
  type MetadataField,
} from '@/modules/asset_manager/hooks/useAssetManager';
import { useScopedNavigate } from '@/lib/appNavigation';
import { extractApiError, useToast } from '@/lib/toast';

const STATUSES: AssetStatus[] = ['ACTIVE', 'INACTIVE', 'PLANNED', 'MAINTENANCE', 'DECOMMISSIONED'];

function MetadataFieldInput({
  field,
  value,
  onChange,
}: {
  field: MetadataField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const strVal = value == null ? '' : String(value);

  if (field.type === 'BOOLEAN') {
    return (
      <input
        type="checkbox"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  }
  if (field.type === 'ENUM' && field.enum_values) {
    return (
      <select className="form-input" value={strVal} onChange={(e) => onChange(e.target.value)}>
        <option value="">—</option>
        {field.enum_values.map((v) => <option key={v} value={v}>{v}</option>)}
      </select>
    );
  }
  if (['INTEGER', 'FLOAT', 'UOM'].includes(field.type)) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <input
          className="form-input"
          type="number"
          value={strVal}
          onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
          min={field.validation?.min}
          max={field.validation?.max}
        />
        {field.unit && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{field.unit}</span>}
      </div>
    );
  }
  if (['DATETIME', 'DATE'].includes(field.type)) {
    return (
      <input
        className="form-input"
        type={field.type === 'DATE' ? 'date' : 'datetime-local'}
        value={strVal}
        onChange={(e) => onChange(e.target.value || undefined)}
      />
    );
  }
  return (
    <input
      className="form-input"
      type={field.type === 'URL' ? 'url' : field.type === 'EMAIL' ? 'email' : 'text'}
      value={strVal}
      onChange={(e) => onChange(e.target.value || undefined)}
      minLength={field.validation?.min_length}
      maxLength={field.validation?.max_length}
      pattern={field.validation?.pattern}
    />
  );
}

export default function AssetFormPage() {
  const { instanceId } = useParams<{ instanceId?: string }>();
  const [searchParams] = useSearchParams();
  const isEdit = Boolean(instanceId);
  const navigate = useScopedNavigate();
  const toast = useToast();

  const { data: existing } = useAssetInstance(instanceId ? Number(instanceId) : undefined);
  const { data: types } = useAssetTypes();
  const createMutation = useCreateAssetInstance();
  const updateMutation = useUpdateAssetInstance(Number(instanceId));
  const reparentMutation = useReparentAsset(Number(instanceId));
  const statusMutation = useUpdateAssetStatus(Number(instanceId));

  const [typeId, setTypeId] = useState<number | ''>('');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<AssetStatus>('ACTIVE');
  const [parentId, setParentId] = useState<string>('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [address, setAddress] = useState('');
  const [commissionedAt, setCommissionedAt] = useState('');
  const [metadata, setMetadata] = useState<Record<string, unknown>>({});
  const [changeSummary, setChangeSummary] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const { data: selectedType } = useAssetType(typeId !== '' ? typeId : undefined);
  const { data: allAssets } = useAssetInstances({ limit: 500 });

  const selectedParent = parentId ? allAssets?.data.find((a) => a.id === Number(parentId)) : undefined;
  const selectedParentType = selectedParent ? types?.find((t) => t.id === selectedParent.asset_type_id) : undefined;
  const filteredTypes = (types ?? []).filter((t) => {
    if (isEdit && existing && t.id !== existing.asset_type_id) return false;
    if (!selectedParentType) return t.allowed_parents.length === 0 || t.is_root;
    if (selectedParentType.is_leaf) return false;
    const childAllowsParent = t.allowed_parents.length === 0 || t.allowed_parents.includes(selectedParentType.id);
    const parentAllowsChild = selectedParentType.allowed_children.length === 0 || selectedParentType.allowed_children.includes(t.id);
    return childAllowsParent && parentAllowsChild;
  });
  const filteredParents = (allAssets?.data ?? []).filter((a) => {
    if (instanceId && a.id === Number(instanceId)) return false;
    const parentType = types?.find((t) => t.id === a.asset_type_id);
    const childType = typeId !== '' ? types?.find((t) => t.id === Number(typeId)) : undefined;
    if (!parentType || parentType.is_leaf) return false;
    if (!childType) return true;
    const childAllowsParent = childType.allowed_parents.length === 0 || childType.allowed_parents.includes(parentType.id);
    const parentAllowsChild = parentType.allowed_children.length === 0 || parentType.allowed_children.includes(childType.id);
    return childAllowsParent && parentAllowsChild;
  });

  useEffect(() => {
    if (existing) {
      setTypeId(existing.asset_type_id);
      setName(existing.name);
      setCode(existing.code ?? '');
      setDescription(existing.description ?? '');
      setStatus(existing.status);
      setParentId(existing.parent_id != null ? String(existing.parent_id) : '');
      setLatitude(existing.latitude != null ? String(existing.latitude) : '');
      setLongitude(existing.longitude != null ? String(existing.longitude) : '');
      setAddress(existing.address ?? '');
      setCommissionedAt(existing.commissioned_at ? existing.commissioned_at.slice(0, 10) : '');
      setMetadata(existing.metadata ?? {});
    }
  }, [existing]);

  useEffect(() => {
    if (isEdit) return;
    const parentFromUrl = searchParams.get('parentId');
    if (parentFromUrl) setParentId(parentFromUrl);
  }, [isEdit, searchParams]);

  useEffect(() => {
    if (typeId === '' || filteredTypes.some((t) => t.id === Number(typeId))) return;
    setTypeId('');
    setMetadata({});
  }, [filteredTypes, typeId]);

  async function handleSave() {
    if (!name.trim() || typeId === '') {
      const msg = 'Name and type are required';
      setSaveError(msg);
      toast.error(msg);
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const body = {
        asset_type_id: Number(typeId),
        name,
        code: code || undefined,
        description: description || undefined,
        status,
        latitude: latitude ? Number(latitude) : undefined,
        longitude: longitude ? Number(longitude) : undefined,
        address: address || undefined,
        commissioned_at: commissionedAt ? new Date(commissionedAt).toISOString() : undefined,
        metadata,
        change_summary: changeSummary || undefined,
      };
      if (isEdit) {
        await updateMutation.mutateAsync(body);
        const nextParentId = parentId ? Number(parentId) : undefined;
        const currentParentId = existing?.parent_id ?? undefined;
        if (nextParentId !== currentParentId) {
          await reparentMutation.mutateAsync({
            parent_id: nextParentId,
            change_summary: changeSummary || 'Parent asset changed',
          });
        }
        if (existing && existing.status !== status) {
          await statusMutation.mutateAsync({ status, change_summary: changeSummary || undefined });
        }
        toast.success('Asset updated');
        navigate(`/assets/${instanceId}`);
      } else {
        const created = await createMutation.mutateAsync({
          ...body,
          parent_id: parentId ? Number(parentId) : undefined,
        });
        toast.success('Asset created');
        navigate(`/assets/${created.id}`);
      }
    } catch (e: unknown) {
      const msg = extractApiError(e);
      setSaveError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  const schemaFields = selectedType?.metadata_schema?.fields ?? [];
  const groupedFields = schemaFields.reduce<Record<string, MetadataField[]>>((acc, f) => {
    const g = f.group ?? 'General';
    if (!acc[g]) acc[g] = [];
    acc[g].push(f);
    return acc;
  }, {});

  return (
    <div className="page-section asset-page">
      <div className="db-page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="icon-btn" onClick={() => navigate(isEdit ? `/assets/${instanceId}` : '/assets')} title="Back">
            <ArrowLeft size={16} />
          </button>
          <Box size={22} color="var(--color-primary)" />
          <h1 className="db-page-title">{isEdit ? 'Edit Asset' : 'New Asset'}</h1>
        </div>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      {saveError && (
        <div
          role="alert"
          style={{
            marginBottom: 16,
            padding: '10px 12px',
            border: '1px solid rgba(239,68,68,0.35)',
            borderRadius: 6,
            background: 'rgba(239,68,68,0.08)',
            color: 'var(--color-danger)',
            fontSize: 13,
            whiteSpace: 'pre-wrap',
          }}
        >
          {saveError}
        </div>
      )}

      <div className="asset-form-layout">
        {/* Core fields */}
        <section className="asset-form-section">
          <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600 }}>Core Info</h3>
          <div className="asset-form-grid">
            <div>
              <label className="form-label">Asset Type *</label>
              <select
                className="form-input"
                value={typeId}
                onChange={(e) => setTypeId(e.target.value ? Number(e.target.value) : '')}
                disabled={isEdit}
              >
                <option value="">Select type…</option>
                {filteredTypes.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              {selectedParentType && filteredTypes.length === 0 && (
                <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: 12 }}>
                  No asset types are allowed under {selectedParentType.name}.
                </p>
              )}
            </div>
            <div>
              <label className="form-label">Status</label>
              <select className="form-input" value={status} onChange={(e) => setStatus(e.target.value as AssetStatus)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="form-label">Name *</label>
              <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Turbine T-001" />
            </div>
            <div>
              <label className="form-label">Code / Tag Number</label>
              <input className="form-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. T-001" />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">Description</label>
              <textarea className="form-input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <div>
              <label className="form-label">Parent Asset</label>
              <select
                className="form-input"
                value={parentId}
                onChange={(e) => setParentId(e.target.value)}
              >
                <option value="">— Root (no parent) —</option>
                {filteredParents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}{a.code ? ` (${a.code})` : ''} — {a.path}
                  </option>
                ))}
              </select>
              {typeId !== '' && selectedType && selectedType.allowed_parents.length > 0 && !parentId && (
                <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: 12 }}>
                  {selectedType.name} requires one of its allowed parent types.
                </p>
              )}
            </div>
            <div>
              <label className="form-label">Commissioned At</label>
              <input className="form-input" type="date" value={commissionedAt} onChange={(e) => setCommissionedAt(e.target.value)} />
            </div>
          </div>
        </section>

        {/* Location */}
        <section className="asset-form-section">
          <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600 }}>Location</h3>
          <div className="asset-form-grid">
            <div>
              <label className="form-label">Latitude</label>
              <input className="form-input" type="number" step="any" value={latitude} onChange={(e) => setLatitude(e.target.value)} />
            </div>
            <div>
              <label className="form-label">Longitude</label>
              <input className="form-input" type="number" step="any" value={longitude} onChange={(e) => setLongitude(e.target.value)} />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">Address</label>
              <input className="form-input" value={address} onChange={(e) => setAddress(e.target.value)} />
            </div>
          </div>
        </section>

        {/* Dynamic metadata from schema */}
        {typeId !== '' && schemaFields.length > 0 && (
          <section className="asset-form-section">
            <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600 }}>
              Metadata
              {selectedType && (
                <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--color-text-muted)', marginLeft: 8 }}>
                  Schema v{selectedType.schema_version}
                </span>
              )}
            </h3>
            {Object.entries(groupedFields).map(([group, fields]) => (
              <div key={group} style={{ marginBottom: 16 }}>
                {Object.keys(groupedFields).length > 1 && (
                  <h4 style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>{group}</h4>
                )}
                <div className="asset-form-grid">
                  {[...fields].sort((a, b) => a.order - b.order).map((f) => (
                    <div key={f.key} style={f.type === 'BOOLEAN' ? { display: 'flex', alignItems: 'center', gap: 8 } : {}}>
                      <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        {f.label}
                        {f.required && <span style={{ color: '#ef4444' }}>*</span>}
                        {f.unit && <span style={{ fontSize: 10, color: 'var(--color-text-muted)' }}>({f.unit})</span>}
                      </label>
                      <MetadataFieldInput
                        field={f}
                        value={metadata[f.key]}
                        onChange={(v) => setMetadata((prev) => ({ ...prev, [f.key]: v }))}
                      />
                      {f.tooltip && <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--color-text-muted)' }}>{f.tooltip}</p>}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>
        )}

        {isEdit && (
          <section className="asset-form-section">
            <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 600 }}>Change Summary</h3>
            <input className="form-input" value={changeSummary} onChange={(e) => setChangeSummary(e.target.value)} placeholder="Describe what changed (optional)" />
          </section>
        )}
      </div>
    </div>
  );
}
