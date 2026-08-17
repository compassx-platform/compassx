import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import {
  Database,
  Edit2,
  Plus,
  Search,
  Table2,
  Trash2,
  X,
} from 'lucide-react';
import {
  useEntityDefinitions,
  useCreateEntityDefinition,
  useUpdateEntityDefinition,
} from '@/modules/workflows/hooks/useEntity';
import api from '@/lib/api';
import { Table } from '@/components/common/Table';
import type { TableColumn, TableAction } from '@/components/common/Table';
import type { EntityDefinition, EntityFieldCreate, EntitySystemFieldCreate } from '@/types';

// ── Constants ─────────────────────────────────────────────────────────────────

const FIELD_TYPES = ['string', 'text', 'number', 'boolean', 'time', 'datetime', 'json'] as const;
const ENTITY_TYPES = ['generic', 'event', 'transaction', 'observation', 'config'] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractApiError(err: any): string {
  const detail = err?.response?.data?.detail;
  if (!detail) return err?.message ?? 'An unexpected error occurred.';
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => {
        const loc = Array.isArray(d.loc)
          ? d.loc.filter((s: any) => s !== 'body').join(' → ')
          : '';
        const msg: string = d.msg ?? String(d);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join('\n');
  }
  if (typeof detail === 'string') return detail;
  return JSON.stringify(detail);
}

function formatDate(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

// ── Field row sub-components ──────────────────────────────────────────────────

function FieldRow({
  field,
  onChange,
  onRemove,
}: {
  field: EntityFieldCreate;
  onChange: (u: EntityFieldCreate) => void;
  onRemove: () => void;
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 130px 72px 72px 28px', gap: 6, alignItems: 'center' }}>
      <input className="input-field" style={{ fontSize: '0.82rem' }} value={field.field_name}
        onChange={(e) => onChange({ ...field, field_name: e.target.value })} placeholder="field_name" />
      <select className="input-field" style={{ fontSize: '0.82rem' }} value={field.field_type}
        onChange={(e) => onChange({ ...field, field_type: e.target.value })}>
        {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', color: 'var(--color-text-muted)', cursor: 'pointer' }}>
        <input type="checkbox" checked={field.is_required} onChange={(e) => onChange({ ...field, is_required: e.target.checked })} /> Req
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', color: 'var(--color-text-muted)', cursor: 'pointer' }}>
        <input type="checkbox" checked={field.is_indexed} onChange={(e) => onChange({ ...field, is_indexed: e.target.checked })} /> Idx
      </label>
      <button type="button" onClick={onRemove} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', padding: 2, display: 'flex' }}>
        <Trash2 size={13} />
      </button>
    </div>
  );
}

function SystemFieldRow({
  field,
  onChange,
  onRemove,
}: {
  field: EntitySystemFieldCreate;
  onChange: (u: EntitySystemFieldCreate) => void;
  onRemove: () => void;
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 110px 1fr 110px 28px', gap: 6, alignItems: 'center' }}>
      <input className="input-field" style={{ fontSize: '0.82rem' }} value={field.field_name}
        onChange={(e) => onChange({ ...field, field_name: e.target.value })} placeholder="field_name" />
      <select className="input-field" style={{ fontSize: '0.82rem' }} value={field.field_type}
        onChange={(e) => onChange({ ...field, field_type: e.target.value })}>
        {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <input className="input-field" style={{ fontSize: '0.82rem' }} value={field.default_value ?? ''}
        onChange={(e) => onChange({ ...field, default_value: e.target.value || null })} placeholder="__now__ / __uuid__ / value" />
      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', color: 'var(--color-text-muted)', cursor: 'pointer' }}>
        <input type="checkbox" checked={field.system_generated} onChange={(e) => onChange({ ...field, system_generated: e.target.checked })} /> Always override
      </label>
      <button type="button" onClick={onRemove} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', padding: 2, display: 'flex' }}>
        <Trash2 size={13} />
      </button>
    </div>
  );
}

// ── Error box ─────────────────────────────────────────────────────────────────

function ErrorBox({ message }: { message: string }) {
  return (
    <div style={{
      padding: '0.7rem 0.9rem', borderRadius: 'var(--radius)',
      background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
      color: 'var(--color-danger)', fontSize: '0.83rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    }}>
      {message}
    </div>
  );
}

// ── Create Entity Panel ───────────────────────────────────────────────────────

function CreateEntityPanel({ onClose }: { onClose: () => void }) {
  const createMutation = useCreateEntityDefinition();
  const [name, setName] = useState('');
  const [entityType, setEntityType] = useState('generic');
  const [assetScoped, setAssetScoped] = useState(true);
  const [timeBased, setTimeBased] = useState(false);
  const [fields, setFields] = useState<EntityFieldCreate[]>([]);
  const [systemFields, setSystemFields] = useState<EntitySystemFieldCreate[]>([]);
  const [createProjection, setCreateProjection] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = (): string | null => {
    if (!name.trim()) return 'Entity name is required.';
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(name.trim()))
      return 'Entity name must be lowercase snake_case (a–z / 0–9 / _, start with a letter, max 64 chars).';
    for (const f of fields) {
      if (!f.field_name.trim()) return 'All fields must have a name.';
      if (!/^[a-z][a-z0-9_]{0,63}$/.test(f.field_name))
        return `Field name "${f.field_name}" is invalid. Use lowercase snake_case.`;
    }
    for (const sf of systemFields) {
      if (!sf.field_name.trim()) return 'All system fields must have a name.';
      if (!/^[a-z][a-z0-9_]{0,63}$/.test(sf.field_name))
        return `System field name "${sf.field_name}" is invalid. Use lowercase snake_case.`;
    }
    return null;
  };

  const handleSubmit = async () => {
    setError(null);
    const ve = validate();
    if (ve) { setError(ve); return; }
    try {
      await createMutation.mutateAsync({ name: name.trim(), entity_type: entityType, asset_scoped: assetScoped, time_based: timeBased, time_series: timeBased, fields, system_fields: systemFields });
      if (createProjection) {
        try {
          await api.post(`/api/v1/entities/${name.trim()}/projection`);
        } catch {
          // projection creation failure is non-fatal — entity was created
        }
      }
      onClose();
    } catch (err: any) { setError(extractApiError(err)); }
  };

  const labelStyle: React.CSSProperties = { fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, display: 'block' };
  const colHdr: React.CSSProperties = { fontSize: '0.73rem', color: 'var(--color-text-muted)', fontWeight: 500 };

  return (
    <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>Create Entity</h2>
        <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex' }}><X size={16} /></button>
      </div>

      {/* Basic info */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label style={labelStyle}>Basic Info</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 4 }}>Entity name *</span>
            <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. breakdown_event" />
            <p style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)', marginTop: 3 }}>Lowercase snake_case. Unique identifier.</p>
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 4 }}>Entity type</span>
            <select className="input-field" value={entityType} onChange={(e) => setEntityType(e.target.value)}>
              {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 20, marginTop: 2, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={assetScoped} onChange={(e) => setAssetScoped(e.target.checked)} />
            Asset scoped <span style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)' }}>(requires asset_id)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={timeBased} onChange={(e) => setTimeBased(e.target.checked)} /> Time based
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={createProjection} onChange={(e) => setCreateProjection(e.target.checked)} />
            Create projection table
            <span style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)' }}>
              ({name.trim() || 'entity'}_flat)
            </span>
          </label>
        </div>
      </div>

      {/* Fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label style={labelStyle}>Fields</label>
          <button type="button" className="btn-outline" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setFields((p) => [...p, { field_name: '', field_type: 'string', is_required: false, is_indexed: false }])}>
            <Plus size={12} /> Add Field
          </button>
        </div>
        {fields.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 130px 72px 72px 28px', gap: 6, marginBottom: 2 }}>
            {['Name', 'Type', 'Req', 'Idx', ''].map((h) => <span key={h} style={colHdr}>{h}</span>)}
          </div>
        )}
        {fields.map((f, i) => (
          <FieldRow key={i} field={f} onChange={(u) => setFields((p) => p.map((x, j) => j === i ? u : x))} onRemove={() => setFields((p) => p.filter((_, j) => j !== i))} />
        ))}
        {fields.length === 0 && <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>No fields yet. Click "Add Field" to define the entity schema.</p>}
      </div>

      {/* System Fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <label style={labelStyle}>System Fields</label>
            <p style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)', marginTop: -4, marginBottom: 4 }}>
              Injected server-side. Use <code>__now__</code> or <code>__uuid__</code> as defaults.
            </p>
          </div>
          <button type="button" className="btn-outline" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setSystemFields((p) => [...p, { field_name: '', field_type: 'string', default_value: null, system_generated: false, is_indexed: false }])}>
            <Plus size={12} /> Add System Field
          </button>
        </div>
        {systemFields.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 110px 1fr 110px 28px', gap: 6, marginBottom: 2 }}>
            {['Name', 'Type', 'Default value', 'Behaviour', ''].map((h) => <span key={h} style={colHdr}>{h}</span>)}
          </div>
        )}
        {systemFields.map((f, i) => (
          <SystemFieldRow key={i} field={f} onChange={(u) => setSystemFields((p) => p.map((x, j) => j === i ? u : x))} onRemove={() => setSystemFields((p) => p.filter((_, j) => j !== i))} />
        ))}
        {systemFields.length === 0 && <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>No system fields.</p>}
      </div>

      {error && <ErrorBox message={error} />}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button type="button" className="btn-outline" onClick={onClose}>Cancel</button>
        <button type="button" className="btn-primary" onClick={handleSubmit} disabled={createMutation.isPending}>
          {createMutation.isPending ? 'Creating…' : 'Create Entity'}
        </button>
      </div>
    </div>
  );
}

// ── Edit Entity Panel ─────────────────────────────────────────────────────────

function EditEntityPanel({
  entity,
  onClose,
}: {
  entity: EntityDefinition;
  onClose: () => void;
}) {
  const updateMutation = useUpdateEntityDefinition();
  const [entityType, setEntityType] = useState(entity.entity_type ?? 'generic');
  const [assetScoped, setAssetScoped] = useState(entity.asset_scoped);
  const [timeBased, setTimeBased] = useState(entity.time_based);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    try {
      await updateMutation.mutateAsync({
        entityName: entity.name,
        payload: { entity_type: entityType, asset_scoped: assetScoped, time_based: timeBased, time_series: timeBased },
      });
      onClose();
    } catch (err: any) { setError(extractApiError(err)); }
  };

  const labelStyle: React.CSSProperties = { fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, display: 'block' };

  return (
    <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>Edit Entity</h2>
          <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: 2, fontFamily: 'monospace' }}>{entity.name}</p>
        </div>
        <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex' }}><X size={16} /></button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label style={labelStyle}>Metadata</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 4 }}>Entity name</span>
            <input className="input-field" value={entity.name} disabled style={{ opacity: 0.55 }} />
            <p style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)', marginTop: 3 }}>Name is immutable.</p>
          </div>
          <div>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', display: 'block', marginBottom: 4 }}>Entity type</span>
            <select className="input-field" value={entityType} onChange={(e) => setEntityType(e.target.value)}>
              {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 20, marginTop: 2 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={assetScoped} onChange={(e) => setAssetScoped(e.target.checked)} />
            Asset scoped <span style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)' }}>(requires asset_id)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={timeBased} onChange={(e) => setTimeBased(e.target.checked)} /> Time based
          </label>
        </div>
      </div>

      {error && <ErrorBox message={error} />}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button type="button" className="btn-outline" onClick={onClose}>Cancel</button>
        <button type="button" className="btn-primary" onClick={handleSubmit} disabled={updateMutation.isPending}>
          {updateMutation.isPending ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────

function Badge({ active, trueLabel, falseLabel }: { active: boolean; trueLabel: string; falseLabel: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: '0.73rem',
      fontWeight: 500,
      background: active ? '#E8F1FF' : 'transparent',
      color: active ? '#1B6EF3' : '#5F6368',
      border: active ? '1px solid #D1E3FF' : '1px solid #DAE0E5',
    }}>
      {active ? trueLabel : falseLabel}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Entities() {
  const navigate = useScopedNavigate();
  const [search, setSearch] = useState('');
  const [mode, setMode] = useState<'list' | 'create'>('list');
  const { data: entities, isLoading } = useEntityDefinitions();

  const filtered = (entities ?? []).filter((e) => {
    const q = search.trim().toLowerCase();
    return !q || e.name.toLowerCase().includes(q) || (e.entity_type ?? '').toLowerCase().includes(q);
  });

  const closePanel = () => setMode('list');

  // ── Table columns ──────────────────────────────────────────────────────────

  // Percentage widths: Type(10%) + Scope(13%) + Time(11%) + Created(11%) + Actions(13%) = 58%
  // Entity column gets the remaining 42% — always fits without horizontal scroll
  const columns: TableColumn<EntityDefinition>[] = [
    {
      key: 'name',
      header: 'Entity',
      // No width — absorbs remaining space after fixed-% columns
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
          <Database size={14} color="#1B6EF3" style={{ flexShrink: 0 }} />
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontWeight: 500, fontSize: '0.875rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</div>
            <div style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'entity_type',
      header: 'Type',
      width: '10%',
      render: (row) => (
        <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
          {row.entity_type ?? 'generic'}
        </span>
      ),
    },
    {
      key: 'scope',
      header: 'Scope',
      width: '13%',
      render: (row) => <Badge active={row.asset_scoped} trueLabel="Asset Scoped" falseLabel="Global" />,
    },
    {
      key: 'time',
      header: 'Time',
      width: '11%',
      render: (row) => <Badge active={row.time_based} trueLabel="Time Based" falseLabel="Static" />,
    },
    {
      key: 'created_at',
      header: 'Created',
      width: '11%',
      render: (row) => (
        <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
          {formatDate(row.created_at)}
        </span>
      ),
    },
  ];

  const rowActions: TableAction<EntityDefinition>[] = [
    {
      label: 'Edit entity',
      icon: Edit2,
      onClick: (row) => navigate(`/entities/${row.name}/edit`),
    },
    {
      label: 'View records',
      icon: Table2,
      onClick: (row) => navigate(`/entities/${row.name}/records`),
    },
  ];

  const toolbar = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.25rem' }}>Entities</h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
          Registered entity types — the source of truth for all form data.
        </p>
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <label className="glass" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.5rem 0.85rem', borderRadius: 'var(--radius)', minWidth: 220 }}>
          <Search size={14} color="var(--color-text-muted)" />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search entities…"
            style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--color-text)', fontSize: '0.875rem', width: '100%' }} />
        </label>
        <button type="button" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          onClick={() => setMode(mode === 'create' ? 'list' : 'create')}>
          <Plus size={14} /> {mode === 'create' ? 'Cancel' : 'New Entity'}
        </button>
      </div>
    </div>
  );

  const emptyState = (
    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
      <Database size={28} style={{ marginBottom: '0.75rem', opacity: 0.3 }} />
      <div style={{ fontWeight: 600, marginBottom: '0.4rem', color: 'var(--color-text)' }}>
        {entities?.length ? 'No matching entities' : 'No entities yet'}
      </div>
      <p style={{ fontSize: '0.85rem', maxWidth: 380, margin: '0 auto' }}>
        {entities?.length ? 'Try a different search term.' : 'Click "New Entity" to create the first entity definition.'}
      </p>
    </div>
  );

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Create panel */}
      {mode === 'create' && (
        <CreateEntityPanel onClose={closePanel} />
      )}

      {/* Table */}
      <Table<EntityDefinition>
        columns={columns}
        rows={filtered}
        keyExtractor={(e) => String(e.id)}
        primaryAction={{
          label: 'View Records',
          onClick: (row) => navigate(`/entities/${row.name}/records`),
        }}
        rowActions={rowActions}
        emptyState={emptyState}
        loading={isLoading}
        toolbar={toolbar}
        actionsColumnWidth="13%"
      />
    </div>
  );
}
