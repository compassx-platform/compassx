/**
 * EntityEditPage — full entity editor.
 *
 * Sections:
 *   1. Metadata  (entity_type, asset_scoped, time_based)
 *   2. Fields    (add / rename / change type / required / indexed / delete)
 *   3. Projection (create flat table + backfill + sync schema)
 *   4. System Fields (add / update / delete)
 */

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useScopedNavigate } from '@/lib/appNavigation';
import {
  ArrowLeft,
  Check,
  Edit2,
  Layers,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import {
  useEntityDefinition,
  useUpdateEntityDefinition,
  useEntityFields,
  useAddEntityField,
  useUpdateEntityField,
  useDeleteEntityField,
  useProjectionStatus,
  useEnableProjection,
  useSyncProjectionSchema,
  useOrphanedProjectionColumns,
  useDropProjectionColumns,
} from '@/modules/workflows/hooks/useEntity';
import {
  useWorkflow,
  useCreateOrUpdateWorkflow,
} from '@/modules/workflows/hooks/useWorkflow';
import type { EntityField } from '@/types';
import { useToast, extractApiError } from '@/lib/toast';

// ── Constants ─────────────────────────────────────────────────────────────────

const FIELD_TYPES = ['string', 'text', 'number', 'boolean', 'time', 'datetime', 'json'] as const;
const ENTITY_TYPES = ['generic', 'event', 'transaction', 'observation', 'config'] as const;

// ── Style helpers ─────────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  fontSize: '0.73rem',
  fontWeight: 600,
  color: 'var(--color-text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  marginBottom: 4,
  display: 'block',
};

const sectionTitle: React.CSSProperties = {
  fontSize: '0.85rem',
  fontWeight: 600,
  color: 'var(--color-text)',
  marginBottom: 12,
  paddingBottom: 8,
  borderBottom: '1px solid var(--color-border)',
};

// ── Inline field editor row ───────────────────────────────────────────────────

function FieldRow({ field, entityName, onDeleted }: { field: EntityField; entityName: string; onDeleted: () => void }) {
  const toast = useToast();
  const updateMut = useUpdateEntityField(entityName);
  const deleteMut = useDeleteEntityField(entityName);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(field.field_name);
  const [type, setType] = useState(field.field_type);
  const [required, setRequired] = useState(field.is_required);
  const [indexed, setIndexed] = useState(field.is_indexed);

  const handleSave = async () => {
    try {
      await updateMut.mutateAsync({
        fieldName: field.field_name,
        payload: {
          new_field_name: name !== field.field_name ? name : undefined,
          field_type: type !== field.field_type ? type : undefined,
          is_required: required,
          is_indexed: indexed,
        },
      });
      toast.success(`Field "${name}" updated.`);
      setEditing(false);
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete field "${field.field_name}"? Existing record data is not affected.`)) return;
    try {
      await deleteMut.mutateAsync(field.field_name);
      toast.success(`Field "${field.field_name}" deleted.`);
      onDeleted();
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const sourceBadge = (
    <span style={{
      fontSize: '0.68rem', fontWeight: 500, padding: '1px 6px', borderRadius: 3,
      background: field.field_source === 'form' ? '#E8F1FF' : 'transparent',
      color: field.field_source === 'form' ? '#1B6EF3' : '#5F6368',
      border: `1px solid ${field.field_source === 'form' ? '#D1E3FF' : '#DAE0E5'}`,
    }}>{field.field_source}</span>
  );

  const rowBase: React.CSSProperties = {
    display: 'grid', gridTemplateColumns: '1fr 90px 60px 60px auto auto',
    gap: 8, alignItems: 'center', padding: '0.45rem 0',
    borderBottom: '1px solid var(--color-border)',
  };

  if (!editing) {
    return (
      <div style={rowBase}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{field.field_name}</span>
          {sourceBadge}
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{field.field_type}</span>
        <span style={{ fontSize: '0.78rem', color: field.is_required ? '#1B6EF3' : '#5F6368' }}>{field.is_required ? 'Req' : '—'}</span>
        <span style={{ fontSize: '0.78rem', color: field.is_indexed ? '#1B6EF3' : '#5F6368' }}>{field.is_indexed ? 'Idx' : '—'}</span>
        <button type="button" title="Edit" onClick={() => setEditing(true)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#5F6368', display: 'flex', padding: 4 }}>
          <Edit2 size={13} />
        </button>
        <button type="button" title="Delete" onClick={handleDelete} disabled={deleteMut.isPending}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-danger)', display: 'flex', padding: 4 }}>
          <Trash2 size={13} />
        </button>
      </div>
    );
  }

  return (
    <div style={{ ...rowBase, background: '#E8F1FF22' }}>
      <input className="input-field" style={{ fontSize: '0.82rem' }} value={name} onChange={(e) => setName(e.target.value)} />
      <select className="input-field" style={{ fontSize: '0.82rem' }} value={type} onChange={(e) => setType(e.target.value)}>
        {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
        <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} /> Req
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
        <input type="checkbox" checked={indexed} onChange={(e) => setIndexed(e.target.checked)} /> Idx
      </label>
      <button type="button" title="Save" onClick={handleSave} disabled={updateMut.isPending}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#28A745', display: 'flex', padding: 4 }}>
        <Check size={14} />
      </button>
      <button type="button" title="Cancel"
        onClick={() => { setEditing(false); setName(field.field_name); setType(field.field_type); }}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex', padding: 4 }}>
        <X size={14} />
      </button>
    </div>
  );
}

function WorkflowSection({ entityName }: { entityName: string }) {
  const toast = useToast();
  const { data: workflow, isLoading, refetch } = useWorkflow(entityName);
  const workflowMut = useCreateOrUpdateWorkflow();
  const [enabled, setEnabled] = useState(true);
  const [initialState, setInitialState] = useState('');
  const [states, setStates] = useState<string[]>([]);
  const [newStateName, setNewStateName] = useState('');
  const [transitions, setTransitions] = useState<{ from: string; to: string }[]>([]);
  const [transitionFrom, setTransitionFrom] = useState('');
  const [transitionTo, setTransitionTo] = useState('');

  useEffect(() => {
    if (!workflow) return;
    setEnabled(workflow.is_enabled);
    setInitialState(workflow.initial_state);
    setStates(workflow.states || []);
    setTransitions(workflow.transitions || []);
  }, [workflow]);

  const handleAddState = () => {
    const candidate = newStateName.trim();
    if (!candidate) return;
    if (states.includes(candidate)) {
      toast.error('State already exists.');
      return;
    }
    setStates((current) => [...current, candidate]);
    setNewStateName('');
  };

  const handleAddTransition = () => {
    if (!transitionFrom || !transitionTo) {
      toast.error('Both source and target states are required.');
      return;
    }
    if (!states.includes(transitionFrom) || !states.includes(transitionTo)) {
      toast.error('Transition states must be defined in the workflow states list.');
      return;
    }
    setTransitions((current) => [...current, { from: transitionFrom, to: transitionTo }]);
    setTransitionFrom('');
    setTransitionTo('');
  };

  const handleSave = async () => {
    try {
      await workflowMut.mutateAsync({
        entity_name: entityName,
        is_enabled: enabled,
        initial_state: initialState,
        states,
        transitions,
      });
      toast.success('Workflow saved.');
      refetch();
    } catch (err: unknown) {
      toast.error(extractApiError(err));
    }
  };

  return (
    <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)', marginBottom: 16 }}>
      <div style={sectionTitle}>Workflow</div>
      {isLoading ? (
        <div style={{ color: 'var(--color-text-muted)' }}>Loading workflow configuration…</div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              Enabled
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 220 }}>
              <span style={labelStyle}>Initial state</span>
              <select className="input-field" value={initialState} onChange={(e) => setInitialState(e.target.value)}>
                <option value="">Select initial state</option>
                {states.map((state) => <option key={state} value={state}>{state}</option>)}
              </select>
            </label>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ marginBottom: 6, fontSize: '0.78rem', fontWeight: 600 }}>States</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
              {states.map((state) => (
                <span key={state} style={{ padding: '0.4rem 0.7rem', borderRadius: 999, background: '#F4F4F5', fontSize: '0.78rem' }}>
                  {state}
                </span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                className="input-field"
                placeholder="New state"
                value={newStateName}
                onChange={(e) => setNewStateName(e.target.value)}
                style={{ minWidth: 180 }}
              />
              <button type="button" className="btn-outline" onClick={handleAddState}>
                Add state
              </button>
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ marginBottom: 6, fontSize: '0.78rem', fontWeight: 600 }}>Transitions</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 8, alignItems: 'end', marginBottom: 8 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={labelStyle}>From</span>
                <select className="input-field" value={transitionFrom} onChange={(e) => setTransitionFrom(e.target.value)}>
                  <option value="">Select from state</option>
                  {states.map((state) => <option key={state} value={state}>{state}</option>)}
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={labelStyle}>To</span>
                <select className="input-field" value={transitionTo} onChange={(e) => setTransitionTo(e.target.value)}>
                  <option value="">Select to state</option>
                  {states.map((state) => <option key={state} value={state}>{state}</option>)}
                </select>
              </label>
              <div />
              <button type="button" className="btn-outline" onClick={handleAddTransition}>
                Add transition
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {transitions.map((transition, index) => (
                <div key={`${transition.from}-${transition.to}-${index}`} style={{ padding: '0.4rem 0.6rem', borderRadius: 6, background: '#F4F4F5', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem' }}>{transition.from} → {transition.to}</span>
                  <button type="button" className="btn-outline" style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                    onClick={() => setTransitions((current) => current.filter((_, idx) => idx !== index))}>
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn-primary" type="button" onClick={handleSave} disabled={workflowMut.isPending}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <Save size={14} /> {workflowMut.isPending ? 'Saving…' : 'Save Workflow'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── System field row ──────────────────────────────────────────────────────────

function SystemFieldRow({ field, entityName, onDeleted }: { field: EntityField; entityName: string; onDeleted: () => void }) {
  const toast = useToast();
  const updateMut = useUpdateEntityField(entityName);
  const deleteMut = useDeleteEntityField(entityName);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(field.field_name);
  const [type, setType] = useState(field.field_type);
  const [defaultVal, setDefaultVal] = useState(field.default_value ?? '');
  const [sysGen, setSysGen] = useState(field.system_generated);

  const handleSave = async () => {
    try {
      await updateMut.mutateAsync({
        fieldName: field.field_name,
        payload: {
          new_field_name: name !== field.field_name ? name : undefined,
          field_type: type,
          default_value: defaultVal || null,
          system_generated: sysGen,
        },
      });
      toast.success(`System field "${name}" updated.`);
      setEditing(false);
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete system field "${field.field_name}"?`)) return;
    try {
      await deleteMut.mutateAsync(field.field_name);
      toast.success(`System field "${field.field_name}" deleted.`);
      onDeleted();
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const rowBase: React.CSSProperties = {
    display: 'grid', gridTemplateColumns: '1fr 90px 1fr 100px auto auto',
    gap: 8, alignItems: 'center', padding: '0.45rem 0',
    borderBottom: '1px solid var(--color-border)',
  };

  if (!editing) {
    return (
      <div style={rowBase}>
        <span style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{field.field_name}</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{field.field_type}</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{field.default_value || '—'}</span>
        <span style={{ fontSize: '0.78rem', color: field.system_generated ? '#1B6EF3' : '#5F6368' }}>
          {field.system_generated ? 'Always override' : 'Inject once'}
        </span>
        <button type="button" title="Edit" onClick={() => setEditing(true)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#5F6368', display: 'flex', padding: 4 }}>
          <Edit2 size={13} />
        </button>
        <button type="button" title="Delete" onClick={handleDelete} disabled={deleteMut.isPending}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-danger)', display: 'flex', padding: 4 }}>
          <Trash2 size={13} />
        </button>
      </div>
    );
  }

  return (
    <div style={{ ...rowBase, background: '#E8F1FF22' }}>
      <input className="input-field" style={{ fontSize: '0.82rem' }} value={name} onChange={(e) => setName(e.target.value)} />
      <select className="input-field" style={{ fontSize: '0.82rem' }} value={type} onChange={(e) => setType(e.target.value)}>
        {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <input className="input-field" style={{ fontSize: '0.82rem' }} value={defaultVal}
        onChange={(e) => setDefaultVal(e.target.value)} placeholder="__now__ / __uuid__ / value" />
      <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
        <input type="checkbox" checked={sysGen} onChange={(e) => setSysGen(e.target.checked)} /> Always override
      </label>
      <button type="button" title="Save" onClick={handleSave} disabled={updateMut.isPending}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#28A745', display: 'flex', padding: 4 }}>
        <Check size={14} />
      </button>
      <button type="button" title="Cancel" onClick={() => setEditing(false)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'flex', padding: 4 }}>
        <X size={14} />
      </button>
    </div>
  );
}

// ── Projection section ────────────────────────────────────────────────────────

function OrphanedColumnsPanel({ entityName }: { entityName: string }) {
  const toast = useToast();
  const { data, refetch } = useOrphanedProjectionColumns(entityName);
  const dropMut = useDropProjectionColumns(entityName);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);

  const orphaned = data?.orphaned_columns ?? [];
  if (orphaned.length === 0) return null;

  const toggleCol = (col: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(col)) {
        next.delete(col);
      } else {
        next.add(col);
      }
      return next;
    });

  const handleDrop = async () => {
    const cols = Array.from(selected);
    try {
      const result = await dropMut.mutateAsync(cols);
      toast.success(result.message);
      setSelected(new Set());
      setConfirming(false);
      refetch();
    } catch (err) { toast.error(extractApiError(err)); setConfirming(false); }
  };

  return (
    <div style={{ marginTop: 16, padding: '0.9rem', borderRadius: 6, background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.2)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Trash2 size={13} style={{ color: 'var(--color-danger)' }} />
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-danger)' }}>
          Orphaned Projection Columns ({orphaned.length})
        </span>
      </div>
      <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 10, lineHeight: 1.5 }}>
        These columns exist in the flat table but are no longer in the entity field definitions
        (removed or renamed via the form builder). Select columns to permanently drop them.
        <strong style={{ color: 'var(--color-danger)' }}> All data in dropped columns is deleted and cannot be recovered.</strong>
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
        {orphaned.map((col) => (
          <label key={col} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, cursor: 'pointer',
            padding: '3px 8px', borderRadius: 4, fontSize: '0.78rem', fontFamily: 'monospace',
            background: selected.has(col) ? 'rgba(239,68,68,0.12)' : 'var(--color-bg)',
            border: `1px solid ${selected.has(col) ? 'rgba(239,68,68,0.5)' : 'var(--color-border)'}`,
            color: selected.has(col) ? 'var(--color-danger)' : 'var(--color-text-muted)',
          }}>
            <input type="checkbox" checked={selected.has(col)} onChange={() => toggleCol(col)} style={{ margin: 0 }} />
            {col}
          </label>
        ))}
      </div>
      {selected.size > 0 && !confirming && (
        <button
          className="btn-outline"
          onClick={() => setConfirming(true)}
          style={{ fontSize: '0.78rem', color: 'var(--color-danger)', borderColor: 'rgba(239,68,68,0.4)', display: 'inline-flex', alignItems: 'center', gap: 5 }}
        >
          <Trash2 size={12} /> Drop {selected.size} column{selected.size > 1 ? 's' : ''}…
        </button>
      )}
      {confirming && (
        <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.08)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.3)' }}>
          <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-danger)', marginBottom: 6 }}>
            ⚠ Confirm permanent deletion
          </p>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 10 }}>
            You are about to permanently drop <strong>{selected.size}</strong> column{selected.size > 1 ? 's' : ''} from{' '}
            <code style={{ fontFamily: 'monospace' }}>{entityName}_flat</code>:{' '}
            <strong>{Array.from(selected).join(', ')}</strong>.
            This action <strong>cannot be undone</strong> and all data in these columns will be lost.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-outline" onClick={() => setConfirming(false)} style={{ fontSize: '0.78rem' }}>Cancel</button>
            <button
              onClick={handleDrop}
              disabled={dropMut.isPending}
              style={{ fontSize: '0.78rem', padding: '0.35rem 0.8rem', borderRadius: 'var(--radius)', border: 'none', cursor: 'pointer', background: 'var(--color-danger)', color: '#fff', display: 'inline-flex', alignItems: 'center', gap: 5 }}
            >
              <Trash2 size={12} /> {dropMut.isPending ? 'Dropping…' : 'Yes, drop permanently'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProjectionSection({ entityName }: { entityName: string }) {
  const toast = useToast();
  const { data: status, isLoading } = useProjectionStatus(entityName);
  const enableMut = useEnableProjection(entityName);
  const syncMut = useSyncProjectionSchema(entityName);

  const handleEnable = async () => {
    try {
      const result = await enableMut.mutateAsync() as { table: string; records_synced: number };
      toast.success(`Projection table "${result.table}" created. ${result.records_synced} records synced.`);
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const handleSync = async () => {
    try {
      await syncMut.mutateAsync();
      toast.success('Projection schema synced — new columns added.');
    } catch (err) { toast.error(extractApiError(err)); }
  };

  return (
    <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)', marginBottom: 16 }}>
      <div style={sectionTitle}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Layers size={14} /> Projection Table
        </span>
      </div>

      {isLoading ? (
        <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>Checking…</p>
      ) : status?.enabled ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  fontSize: '0.73rem', fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                  background: '#E6F4EA', color: '#1E7E34', border: '1px solid #B7DFC0',
                }}>
                  <Check size={10} /> Enabled
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                  {status.table}
                </span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Records are automatically synced on every insert / update / delete.
              </p>
            </div>
            <button className="btn-outline" onClick={handleSync} disabled={syncMut.isPending}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem' }}>
              <RefreshCw size={13} /> {syncMut.isPending ? 'Syncing…' : 'Sync Schema'}
            </button>
          </div>
          <OrphanedColumnsPanel entityName={entityName} />
        </>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginBottom: 4 }}>
              No projection table yet. Enabling will create{' '}
              <code style={{ fontFamily: 'monospace' }}>{entityName}_flat</code> and backfill all existing records.
            </p>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              Once enabled, every record write is automatically mirrored into the flat table.
            </p>
          </div>
          <button className="btn-primary" onClick={handleEnable} disabled={enableMut.isPending}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
            <Layers size={13} /> {enableMut.isPending ? 'Creating…' : 'Enable Projection'}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function EntityEditPage() {
  const { entityName } = useParams<{ entityName: string }>();
  const navigate = useScopedNavigate();
  const toast = useToast();

  const { data: entity, isLoading } = useEntityDefinition(entityName ?? '');
  const { data: fields, refetch: refetchFields } = useEntityFields(entityName ?? '');
  const updateMeta = useUpdateEntityDefinition();
  const addField = useAddEntityField(entityName ?? '');

  const [entityType, setEntityType] = useState('');
  const [assetScoped, setAssetScoped] = useState(true);
  const [timeBased, setTimeBased] = useState(false);
  const [metaReady, setMetaReady] = useState(false);

  const [newFieldName, setNewFieldName] = useState('');
  const [newFieldType, setNewFieldType] = useState('string');
  const [newRequired, setNewRequired] = useState(false);
  const [newIndexed, setNewIndexed] = useState(false);
  const [showAddField, setShowAddField] = useState(false);
  const [newSystemFieldName, setNewSystemFieldName] = useState('');
  const [newSystemFieldType, setNewSystemFieldType] = useState('string');
  const [newSystemFieldIndexed, setNewSystemFieldIndexed] = useState(false);
  const [newSystemDefaultVal, setNewSystemDefaultVal] = useState('');
  const [newSystemSysGen, setNewSystemSysGen] = useState(false);
  const [showAddSystemField, setShowAddSystemField] = useState(false);

  if (entity && !metaReady) {
    setEntityType(entity.entity_type ?? 'generic');
    setAssetScoped(entity.asset_scoped);
    setTimeBased(entity.time_based);
    setMetaReady(true);
  }

  const regularFields = (fields ?? []).filter((f) => !f.is_system);
  const systemFields = (fields ?? []).filter((f) => f.is_system);

  const handleSaveMeta = async () => {
    if (!entityName) return;
    try {
      await updateMeta.mutateAsync({
        entityName,
        payload: { entity_type: entityType, asset_scoped: assetScoped, time_based: timeBased, time_series: timeBased },
      });
      toast.success('Entity metadata saved.');
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const handleAddField = async () => {
    if (!newFieldName.trim()) { toast.error('Field name is required.'); return; }
    try {
      await addField.mutateAsync({
        field_name: newFieldName.trim(),
        field_type: newFieldType,
        is_required: newRequired,
        is_indexed: newIndexed,
        field_source: 'entity',
      });
      toast.success(`Field "${newFieldName}" added.`);
      setNewFieldName(''); setNewFieldType('string'); setNewRequired(false);
      setNewIndexed(false);
      setShowAddField(false);
    } catch (err) { toast.error(extractApiError(err)); }
  };

  const handleAddSystemField = async () => {
    if (!newSystemFieldName.trim()) { toast.error('System field name is required.'); return; }
    try {
      await addField.mutateAsync({
        field_name: newSystemFieldName.trim(),
        field_type: newSystemFieldType,
        is_required: false,
        is_indexed: newSystemFieldIndexed,
        is_system: true,
        system_generated: newSystemSysGen,
        default_value: newSystemDefaultVal || null,
        field_source: 'entity',
      });
      toast.success(`System field "${newSystemFieldName}" added.`);
      setNewSystemFieldName('');
      setNewSystemFieldType('string');
      setNewSystemFieldIndexed(false);
      setNewSystemDefaultVal('');
      setNewSystemSysGen(false);
      setShowAddSystemField(false);
    } catch (err) { toast.error(extractApiError(err)); }
  };

  if (!entityName) return <div style={{ padding: '2rem' }}>No entity specified.</div>;
  if (isLoading) return <div style={{ padding: '2rem', color: 'var(--color-text-muted)' }}>Loading…</div>;
  if (!entity) return <div style={{ padding: '2rem', color: 'var(--color-danger)' }}>Entity not found.</div>;

  return (
    <div className="animate-fade-in" style={{ maxWidth: 900, margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: '1.75rem' }}>
        <button className="btn-outline" onClick={() => navigate('/entities')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem' }}>
          <ArrowLeft size={15} /> Entities
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600 }}>
            Edit: <span style={{ fontFamily: 'monospace' }}>{entityName}</span>
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
            Manage metadata, fields and projection. Entity name is immutable.
          </p>
        </div>
        <button className="btn-outline" onClick={() => navigate(`/entities/${entityName}/records`)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
          View Records
        </button>
      </div>

      {/* ── Metadata ── */}
      <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)', marginBottom: 16 }}>
        <div style={sectionTitle}>Metadata</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 12 }}>
          <div>
            <span style={labelStyle}>Entity name</span>
            <input className="input-field" value={entityName} disabled style={{ opacity: 0.55 }} />
            <p style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 3 }}>Immutable identifier.</p>
          </div>
          <div>
            <span style={labelStyle}>Entity type</span>
            <select className="input-field" value={entityType} onChange={(e) => setEntityType(e.target.value)}>
              {ENTITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={assetScoped} onChange={(e) => setAssetScoped(e.target.checked)} />
            Asset scoped <span style={{ fontSize: '0.73rem', color: 'var(--color-text-muted)' }}>(requires asset_id)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={timeBased} onChange={(e) => setTimeBased(e.target.checked)} /> Time based
          </label>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn-primary" onClick={handleSaveMeta} disabled={updateMeta.isPending}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Save size={14} /> {updateMeta.isPending ? 'Saving…' : 'Save Metadata'}
          </button>
        </div>
      </div>

      <WorkflowSection entityName={entityName} />

      {/* ── Regular Fields ── */}
      <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)', marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={sectionTitle}>Fields ({regularFields.length})</div>
          <button className="btn-outline" onClick={() => setShowAddField((v) => !v)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', padding: '0.25rem 0.6rem' }}>
            <Plus size={12} /> Add Field
          </button>
        </div>

        {regularFields.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 90px 60px 60px auto auto', gap: 8, marginBottom: 4 }}>
            {['Name / Source', 'Type', 'Req', 'Idx', '', ''].map((h, i) => (
              <span key={i} style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>{h}</span>
            ))}
          </div>
        )}

        {regularFields.map((f) => (
          <FieldRow key={f.id} field={f} entityName={entityName} onDeleted={() => refetchFields()} />
        ))}

        {regularFields.length === 0 && !showAddField && (
          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>No regular fields. Click "Add Field" to define the schema.</p>
        )}

        {showAddField && (
          <div style={{ marginTop: 12, padding: '0.9rem', background: 'var(--color-bg)', borderRadius: 6, border: '1px solid var(--color-border)' }}>
            <p style={{ fontSize: '0.78rem', fontWeight: 600, marginBottom: 8 }}>New Field</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 60px 60px', gap: 8, alignItems: 'center', marginBottom: 8 }}>
              <input className="input-field" style={{ fontSize: '0.82rem' }} value={newFieldName}
                onChange={(e) => setNewFieldName(e.target.value)} placeholder="field_name" />
              <select className="input-field" style={{ fontSize: '0.82rem' }} value={newFieldType}
                onChange={(e) => setNewFieldType(e.target.value)}>
                {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={newRequired} onChange={(e) => setNewRequired(e.target.checked)} /> Req
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={newIndexed} onChange={(e) => setNewIndexed(e.target.checked)} /> Idx
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn-outline" onClick={() => setShowAddField(false)} style={{ fontSize: '0.8rem' }}>Cancel</button>
              <button className="btn-primary" onClick={handleAddField} disabled={addField.isPending}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.8rem' }}>
                <Plus size={13} /> {addField.isPending ? 'Adding…' : 'Add'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Projection ── */}
      <ProjectionSection entityName={entityName} />

      {/* ── System Fields ── */}
      <div className="glass" style={{ padding: '1.25rem', borderRadius: 'var(--radius)' }}>
        <div style={{ ...sectionTitle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            System Fields ({systemFields.length})
            <span style={{ fontWeight: 400, fontSize: '0.75rem', color: 'var(--color-text-muted)', marginLeft: 8 }}>
              Injected server-side. Use <code>__now__</code> or <code>__uuid__</code> as defaults.
            </span>
          </div>
          <button className="btn-outline" onClick={() => setShowAddSystemField((v) => !v)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', padding: '0.25rem 0.6rem' }}>
            <Plus size={12} /> Add System Field
          </button>
        </div>

        {showAddSystemField && (
          <div style={{ marginBottom: 12, padding: '0.9rem', background: 'var(--color-bg)', borderRadius: 6, border: '1px solid var(--color-border)' }}>
            <p style={{ fontSize: '0.78rem', fontWeight: 600, marginBottom: 8 }}>New System Field</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 60px', gap: 8, alignItems: 'center', marginBottom: 8 }}>
              <input className="input-field" style={{ fontSize: '0.82rem' }} value={newSystemFieldName}
                onChange={(e) => setNewSystemFieldName(e.target.value)} placeholder="field_name" />
              <select className="input-field" style={{ fontSize: '0.82rem' }} value={newSystemFieldType}
                onChange={(e) => setNewSystemFieldType(e.target.value)}>
                {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={newSystemFieldIndexed} onChange={(e) => setNewSystemFieldIndexed(e.target.checked)} /> Idx
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, marginBottom: 8 }}>
              <input className="input-field" style={{ fontSize: '0.82rem' }} value={newSystemDefaultVal}
                onChange={(e) => setNewSystemDefaultVal(e.target.value)} placeholder="Default: __now__ / __uuid__ / value" />
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={newSystemSysGen} onChange={(e) => setNewSystemSysGen(e.target.checked)} /> Always override
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn-outline" onClick={() => setShowAddSystemField(false)} style={{ fontSize: '0.8rem' }}>Cancel</button>
              <button className="btn-primary" onClick={handleAddSystemField} disabled={addField.isPending}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.8rem' }}>
                <Plus size={13} /> {addField.isPending ? 'Adding…' : 'Add'}
              </button>
            </div>
          </div>
        )}

        {systemFields.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 90px 1fr 100px auto auto', gap: 8, marginBottom: 4 }}>
            {['Name', 'Type', 'Default', 'Behaviour', '', ''].map((h, i) => (
              <span key={i} style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>{h}</span>
            ))}
          </div>
        )}

        {systemFields.map((f) => (
          <SystemFieldRow key={f.id} field={f} entityName={entityName} onDeleted={() => refetchFields()} />
        ))}

        {systemFields.length === 0 && (
          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>No system fields defined.</p>
        )}
      </div>
    </div>
  );
}


