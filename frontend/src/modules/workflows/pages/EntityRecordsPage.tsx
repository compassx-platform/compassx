import { useMemo, type CSSProperties, type ChangeEvent } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { useScopedNavigate } from '@/lib/appNavigation';
import { Edit2, Trash2, RefreshCw } from 'lucide-react';
import { useDeleteEntityRecord, useEntityRecords, useUpdateEntityRecord } from '@/modules/workflows/hooks/useEntity';
import { useForms } from '@/modules/workflows/hooks/useForm';
import { useAllAssets, useAssetTypes } from '@/hooks/useAssets';
import { useWorkflowTransitions } from '@/modules/workflows/hooks/useWorkflow';
import { useToast, extractApiError } from '@/lib/toast';

type TableColumn = { id: string; label: string; fieldType?: string; };

function fmt(v: string) { return v.replace(/_/g, ' '); }
function fmtCol(v: string) { return v.split('_').filter(Boolean).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' '); }
function fmtCell(v: unknown) {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'object') return Object.values(v as Record<string, unknown>).join(', ');
  return String(v);
}

function RecordStateTransitionDropdown({
  entityName,
  record,
}: {
  entityName: string;
  record: { id: number; status: string };
}) {
  const toast = useToast();
  const transitionQuery = useWorkflowTransitions(entityName, record.status || '');
  const updateMut = useUpdateEntityRecord(entityName);

  const transitions = transitionQuery.data?.available || [];

  const handleChange = async (event: ChangeEvent<HTMLSelectElement>) => {
    const targetState = event.target.value;
    if (!targetState) return;

    try {
      await updateMut.mutateAsync({ id: record.id, data: {}, status: targetState });
      toast.success(`State changed to ${targetState}.`);
    } catch (error: unknown) {
      toast.error(extractApiError(error));
    }
  };

  if (transitionQuery.isLoading) {
    return <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>Loading transitions…</div>;
  }

  if (!transitions.length) {
    return <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>No state transitions configured.</div>;
  }

  return (
    <select
      value=""
      onChange={handleChange}
      style={{ minWidth: 175, padding: '0.4rem 0.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}
    >
      <option value="">Change status...</option>
      {transitions.map((nextState) => (
        <option key={nextState} value={nextState}>
          {nextState}
        </option>
      ))}
    </select>
  );
}

export default function EntityRecordsPage() {
  // Support both old (:entity_name) and new (:entityName) param names
  const params = useParams<{ entityName?: string; entity_name?: string }>();
  const entityName = params.entityName || params.entity_name || '';
  const navigate = useScopedNavigate();
  const location = useLocation();
  const isPublic = location.pathname.startsWith('/public/');

  const { data: records, isLoading, error, refetch } = useEntityRecords(entityName);
  const { data: forms } = useForms();
  const deleteMut = useDeleteEntityRecord(entityName);
  const { data: allAssets } = useAllAssets();
  const { data: assetTypes } = useAssetTypes();

  const assetMap = useMemo(() => {
    const m: Record<string, string> = {};
    (allAssets || []).forEach((a) => { m[String(a.id)] = a.name; });
    return m;
  }, [allAssets]);

  const assetTypeMap = useMemo(() => {
    const m: Record<string, string> = {};
    (assetTypes || []).forEach((t) => { m[String(t.id)] = t.name; });
    return m;
  }, [assetTypes]);

  const toast = useToast();

  const matchingForm = useMemo(
    () => forms?.find((f) => f.entity_name === entityName) || null,
    [forms, entityName],
  );

  const dataColumns = useMemo<TableColumn[]>(() => {
    if (matchingForm?.schema?.fields?.length) {
      return matchingForm.schema.fields.map((f) => ({ id: f.id, label: f.label || fmtCol(f.id), fieldType: f.type }));
    }
    const keys = Array.from(new Set((records || []).flatMap((r) => Object.keys(r.data_json || {}))));
    return keys.map((k) => ({ id: k, label: fmtCol(k) }));
  }, [matchingForm, records]);

  if (!entityName) return <div style={{ padding: '2rem', color: 'var(--color-text-muted)' }}>No entity specified.</div>;

  const resolveCell = (col: TableColumn, raw: unknown): string => {
    const s = raw === null || raw === undefined ? '' : String(raw);
    if (!s) return '—';
    if (col.fieldType === 'asset_type_dropdown') return assetTypeMap[s] || s;
    if (col.fieldType === 'asset_dropdown') return assetMap[s] || s;
    return fmtCell(raw);
  };

  const handleDelete = async (rec: { id: number; asset_id: string }) => {
    const label = assetMap[String(rec.asset_id)] || `Asset ${rec.asset_id}`;
    if (window.confirm(`Delete record for ${label}?`)) {
      try {
        await deleteMut.mutateAsync(rec.id);
        toast.success('Record deleted.');
      } catch (e: unknown) {
        toast.error(extractApiError(e));
      }
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, textTransform: 'capitalize' }}>{fmt(entityName)} Records</h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: 2 }}>
            {matchingForm ? `Schema from ${matchingForm.form_id}` : 'Columns inferred from stored data'}
          </p>
        </div>
        <button className="btn-outline" onClick={() => refetch()} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {isLoading && <div style={{ padding: '2rem', color: 'var(--color-text-muted)' }}>Loading…</div>}
      {error && <div style={{ padding: '2rem', color: 'var(--color-danger)' }}>Failed to load records.</div>}

      {!isLoading && !error && (!records || records.length === 0) && (
        <div className="glass" style={{ padding: '3rem', borderRadius: 'var(--radius)', textAlign: 'center', color: 'var(--color-text-muted)' }}>
          No records found for this entity.
        </div>
      )}

      {!isLoading && records && records.length > 0 && (
        <>
          <div style={{ overflowX: 'auto', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: 'var(--color-surface)' }}>
              <thead>
                <tr>
                  <th style={thS}>Asset</th>
                  <th style={thS}>Timestamp</th>
                  <th style={thS}>Status</th>
                  {dataColumns.map((c) => <th key={c.id} style={thS}>{c.label}</th>)}
                  <th style={{ ...thS, textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map((rec) => (
                  <tr key={rec.id}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    style={{ transition: 'background 0.15s' }}>
                    <td style={tdS}>
                      <div style={{ fontWeight: 500 }}>{assetMap[String(rec.asset_id)] || rec.asset_id || '—'}</div>
                      {assetMap[String(rec.asset_id)] && <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>ID: {rec.asset_id}</div>}
                    </td>
                    <td style={tdS}>{rec.timestamp ? new Date(rec.timestamp).toLocaleString() : '—'}</td>
                    <td style={tdS}>
                      <span className={rec.status?.toLowerCase() === 'open' ? 'badge badge-open' : 'badge badge-closed'}>
                        {rec.status || '—'}
                      </span>
                    </td>
                    {dataColumns.map((col) => (
                      <td key={col.id} style={tdS}>
                        <div style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--color-text-muted)' }}
                          title={resolveCell(col, rec.data_json?.[col.id])}>
                          {resolveCell(col, rec.data_json?.[col.id])}
                        </div>
                      </td>
                    ))}
                    <td style={{ ...tdS, textAlign: 'center' }}>
                      <div style={{ display: 'grid', gap: 8, alignItems: 'center' }}>
                        <RecordStateTransitionDropdown entityName={entityName} record={rec} />
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button className="btn-outline" style={{ padding: '0.3rem 0.5rem' }}
                            onClick={() => { if (!matchingForm) { toast.info('No form configured for this entity.'); return; } navigate(isPublic ? `/public/entities/${entityName}/records/${rec.id}/edit` : `/entities/${entityName}/records/${rec.id}/edit`); }}
                            title={matchingForm ? 'Edit' : 'No form configured'}>
                            <Edit2 size={14} />
                          </button>
                          <button className="btn-danger" style={{ padding: '0.3rem 0.5rem' }} disabled={deleteMut.isPending}
                            onClick={() => handleDelete(rec)} title="Delete">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', paddingBottom: '1rem' }}>
            {records.length} record{records.length !== 1 ? 's' : ''}
          </div>
        </>
      )}
    </div>
  );
}

const thS: CSSProperties = {
  padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)',
  borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap',
};
const tdS: CSSProperties = {
  padding: '0.75rem 1rem', fontSize: '0.875rem', borderBottom: '1px solid rgba(42,46,62,0.5)',
};

