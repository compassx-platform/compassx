import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Layers, Plus, Trash2, ArrowLeft } from 'lucide-react';
import {
  useAssetType,
  useCreateAssetType,
  useUpdateAssetType,
  useUpdateAssetTypeById,
  useUpdateAssetTypeSchema,
  type AssetCategory,
  type AssetType,
  type AssetTypeCreateRequest,
  type MetadataField,
  type MetadataFieldType,
  type AssetTypeTag,
} from '@/modules/asset_manager/hooks/useAssetManager';
import { useScopedNavigate } from '@/lib/appNavigation';
import { extractApiError, useToast } from '@/lib/toast';

const CATEGORIES: AssetCategory[] = ['SITE', 'EQUIPMENT', 'COMPONENT', 'TAG', 'EVENT_TYPE'];
const FIELD_TYPES: MetadataFieldType[] = ['STRING', 'INTEGER', 'FLOAT', 'BOOLEAN', 'DATETIME', 'DATE', 'ENUM', 'URL', 'EMAIL', 'UOM'];

export default function AssetTypeFormPage() {
  const { typeId } = useParams<{ typeId?: string }>();
  const [searchParams] = useSearchParams();
  const parentTypeIdParam = searchParams.get('parentTypeId');
  const parsedParentTypeId = parentTypeIdParam ? Number(parentTypeIdParam) : undefined;
  const parentTypeId = parsedParentTypeId && Number.isFinite(parsedParentTypeId) ? parsedParentTypeId : undefined;
  const isEdit = Boolean(typeId);
  const isChildCreate = !isEdit && parentTypeId !== undefined;
  const navigate = useScopedNavigate();
  const toast = useToast();

  const { data: existing } = useAssetType(typeId ? Number(typeId) : undefined);
  const { data: parentType } = useAssetType(parentTypeId);
  const createMutation = useCreateAssetType();
  const updateMutation = useUpdateAssetType(Number(typeId));
  const updateTypeById = useUpdateAssetTypeById();
  const schemaMutation = useUpdateAssetTypeSchema(Number(typeId));

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [category, setCategory] = useState<AssetCategory>('EQUIPMENT');
  const [description, setDescription] = useState('');
  const [industryTags, setIndustryTags] = useState('');
  const [icon, setIcon] = useState('');
  const [isRoot, setIsRoot] = useState(false);
  const [isLeaf, setIsLeaf] = useState(false);
  const [fields, setFields] = useState<MetadataField[]>([]);
  const [tagDefinitions, setTagDefinitions] = useState<Partial<AssetTypeTag>[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (existing) {
      setName(existing.name);
      setSlug(existing.slug);
      setCategory(existing.category);
      setDescription(existing.description ?? '');
      setIndustryTags((existing.industry_tags ?? []).join(', '));
      setIcon(existing.icon ?? '');
      setIsRoot(existing.is_root);
      setIsLeaf(existing.is_leaf);
      setFields(existing.metadata_schema?.fields ?? []);
      setTagDefinitions(existing.tag_definitions ?? []);
    }
  }, [existing]);

  useEffect(() => {
    if (isChildCreate) {
      setIsRoot(false);
    }
  }, [isChildCreate]);

  function autoSlug(n: string) {
    return n.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '');
  }

  function addField() {
    setFields((f) => [
      ...f,
      {
        key: `field_${f.length + 1}`,
        label: `Field ${f.length + 1}`,
        type: 'STRING',
        required: false,
        order: f.length,
        is_searchable: false,
        is_filterable: false,
      },
    ]);
  }

  function removeField(idx: number) {
    setFields((f) => f.filter((_, i) => i !== idx));
  }

  function updateField(idx: number, patch: Partial<MetadataField>) {
    setFields((f) => f.map((field, i) => (i === idx ? { ...field, ...patch } : field)));
  }

  function addTagDefinition() {
    setTagDefinitions((tags) => [
      ...tags,
      {
        tag_key: `tag_${tags.length + 1}`,
        name: `Tag ${tags.length + 1}`,
        parameter: '',
        unit: '',
        description: '',
        is_required: false,
      },
    ]);
  }

  function removeTagDefinition(idx: number) {
    setTagDefinitions((tags) => tags.filter((_, i) => i !== idx));
  }

  function updateTagDefinition(idx: number, patch: Partial<AssetTypeTag>) {
    setTagDefinitions((tags) => tags.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  }

  async function handleSave() {
    if (!name.trim() || !slug.trim()) {
      const msg = 'Name and slug are required';
      setSaveError(msg);
      toast.error(msg);
      return;
    }
    if (isChildCreate && !parentType) {
      const msg = 'Parent asset type is still loading. Please try again.';
      setSaveError(msg);
      toast.error(msg);
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const createBody: AssetTypeCreateRequest = {
        name,
        slug,
        category: category || 'EQUIPMENT',
        description: description || undefined,
        industry_tags: industryTags.split(',').map((t) => t.trim()).filter(Boolean),
        icon: icon || undefined,
        allowed_parents: isChildCreate ? [parentTypeId] : [],
        is_root: isChildCreate ? false : isRoot,
        is_leaf: isLeaf,
        metadata_schema: { version: 1, fields },
        tag_definitions: tagDefinitions.map((t) => ({
          id: t.id,
          tag_key: t.tag_key?.trim(),
          name: t.name?.trim(),
          parameter: t.parameter?.trim() || undefined,
          unit: t.unit?.trim() || undefined,
          description: t.description?.trim() || undefined,
          is_required: !!t.is_required,
        })),
      };
      const updateBody: Partial<AssetType> = {
        name,
        slug,
        category: category || 'EQUIPMENT',
        description: description || undefined,
        industry_tags: industryTags.split(',').map((t) => t.trim()).filter(Boolean),
        icon: icon || undefined,
        allowed_parents: isChildCreate ? [parentTypeId] : [],
        is_root: isChildCreate ? false : isRoot,
        is_leaf: isLeaf,
        metadata_schema: { version: 1, fields },
      };

      if (isEdit) {
        await updateMutation.mutateAsync(updateBody);
        await schemaMutation.mutateAsync({ version: 1, fields });
        toast.success('Asset type updated');
      } else {
        const created = await createMutation.mutateAsync(createBody);
        if (isChildCreate && parentType) {
          const allowedChildren = Array.isArray(parentType.allowed_children) ? parentType.allowed_children : [];
          await updateTypeById.mutateAsync({
            id: parentType.id,
            body: { allowed_children: Array.from(new Set([...allowedChildren, created.id])) },
          });
        }
        toast.success('Asset type created');
        navigate('/assets/types');
      }
    } catch (e: unknown) {
      const msg = extractApiError(e);
      setSaveError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-section">
      <div className="db-page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="icon-btn" onClick={() => navigate('/assets/types')} title="Back">
            <ArrowLeft size={16} />
          </button>
          <Layers size={22} color="var(--color-primary)" />
          <h1 className="db-page-title">{isEdit ? 'Edit Asset Type' : 'New Asset Type'}</h1>
          {isChildCreate && parentType && (
            <span className="asset-pill">Child of {parentType.name}</span>
          )}
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
        <section className="asset-form-section">
          <h3 className="asset-form-section-title">Basic Info</h3>
          <div className="asset-form-grid">
            <div>
              <label className="form-label">Name *</label>
              <input
                className="form-input"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (!isEdit) setSlug(autoSlug(e.target.value));
                }}
                placeholder="e.g. Wind Turbine"
              />
            </div>
            <div>
              <label className="form-label">Slug *</label>
              <input
                className="form-input"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="e.g. wind-turbine"
                disabled={isEdit}
              />
            </div>
            <div>
              <label className="form-label">Category *</label>
              <select className="form-input" value={category} onChange={(e) => setCategory(e.target.value as AssetCategory)}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="form-label">Icon (emoji/key)</label>
              <input className="form-input" value={icon} onChange={(e) => setIcon(e.target.value)} placeholder="e.g. 🏭" />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">Description</label>
              <textarea className="form-input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <div>
              <label className="form-label">Industry Tags (comma-separated)</label>
              <input className="form-input" value={industryTags} onChange={(e) => setIndustryTags(e.target.value)} placeholder="renewable, onshore-wind" />
            </div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center', paddingTop: 20 }}>
              {!isChildCreate && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                  <input type="checkbox" checked={isRoot} onChange={(e) => setIsRoot(e.target.checked)} />
                  Root node
                </label>
              )}
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <input type="checkbox" checked={isLeaf} onChange={(e) => setIsLeaf(e.target.checked)} />
                Leaf node
              </label>
            </div>
          </div>
        </section>

        <section className="asset-form-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Metadata Schema Fields</h3>
            <button className="btn btn-secondary" onClick={addField} style={{ fontSize: 12 }}>
              <Plus size={12} /> Add Field
            </button>
          </div>
          {fields.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>No fields defined. Add fields to capture metadata.</p>
          ) : (
            <div className="asset-form-card-list">
              {fields.map((field, idx) => (
                <div key={idx} className="asset-form-field-row">
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Key</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={field.key} onChange={(e) => updateField(idx, { key: e.target.value })} />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Label</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={field.label} onChange={(e) => updateField(idx, { label: e.target.value })} />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Type</label>
                    <select className="form-input" style={{ fontSize: 12 }} value={field.type} onChange={(e) => updateField(idx, { type: e.target.value as MetadataFieldType })}>
                      {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Unit</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={field.unit ?? ''} onChange={(e) => updateField(idx, { unit: e.target.value || undefined })} placeholder="e.g. MW" />
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', paddingBottom: 2 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, whiteSpace: 'nowrap' }}>
                      <input type="checkbox" checked={field.required} onChange={(e) => updateField(idx, { required: e.target.checked })} />
                      Req
                    </label>
                    <button className="icon-btn danger" onClick={() => removeField(idx)} title="Remove field">
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="asset-form-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Tag Definitions</h3>
            <button className="btn btn-secondary" onClick={addTagDefinition} style={{ fontSize: 12 }}>
              <Plus size={12} /> Add Tag Definition
            </button>
          </div>
          {tagDefinitions.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>No tag definitions. Add expected tag types (e.g. active_power).</p>
          ) : (
            <div className="asset-form-card-list">
              {tagDefinitions.map((t, idx) => (
                <div key={idx} className="asset-form-field-row" style={{ gridTemplateColumns: '1fr 1.2fr 1.2fr 0.8fr 2fr auto' }}>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Tag Key *</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={t.tag_key ?? ''} onChange={(e) => updateTagDefinition(idx, { tag_key: e.target.value })} placeholder="active_power" />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Display Name *</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={t.name ?? ''} onChange={(e) => updateTagDefinition(idx, { name: e.target.value })} placeholder="Active Power" />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Parameter</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={t.parameter ?? ''} onChange={(e) => updateTagDefinition(idx, { parameter: e.target.value })} placeholder="Active Power" />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Unit</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={t.unit ?? ''} onChange={(e) => updateTagDefinition(idx, { unit: e.target.value })} placeholder="kW" />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: 11 }}>Description</label>
                    <input className="form-input" style={{ fontSize: 12 }} value={t.description ?? ''} onChange={(e) => updateTagDefinition(idx, { description: e.target.value })} placeholder="Power output" />
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', paddingBottom: 2 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, whiteSpace: 'nowrap' }}>
                      <input type="checkbox" checked={!!t.is_required} onChange={(e) => updateTagDefinition(idx, { is_required: e.target.checked })} />
                      Req
                    </label>
                    <button className="icon-btn danger" onClick={() => removeTagDefinition(idx)} title="Remove tag definition">
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}



