/**
 * DatasetEditor — SQL editor with schema tab, params, result preview.
 * Reference: Databricks dashboard dataset editor with result table + schema tab.
 * Screenshot: dataset-assistant-5b90be648483a6e5fd6d6d378df07794.png (Genie icon)
 */

import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Play, Table2, AlignLeft, Loader2 } from 'lucide-react';
// CodeMirror imports — optional, fallback to textarea if unavailable
import { useDatasetQuery, useDatasetSchema } from '@/modules/dashboards/hooks/useDashboard';
import type { Dataset, DatasetField } from '@/types/dashboard';

function SqlEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        flex: 1,
        resize: 'none',
        fontFamily: 'monospace',
        fontSize: '0.8rem',
        border: 'none',
        padding: 12,
        background: 'var(--color-bg)',
        color: 'var(--color-text)',
        outline: 'none',
        width: '100%',
        height: '100%',
      }}
      spellCheck={false}
    />
  );
}

const TYPE_ICON: Record<string, string> = {
  string: 'T',
  varchar: 'T',
  text: 'T',
  int: '#',
  integer: '#',
  bigint: '#',
  float: '~',
  double: '~',
  decimal: '~',
  boolean: '⊤',
  date: '📅',
  timestamp: '⏱',
  default: '?',
};

interface Props {
  dataset: Dataset;
  onClose: () => void;
  onSave: (patch: Partial<Dataset>) => void | Promise<void>;
  onDraftChange?: (patch: Partial<Dataset>) => void;
  onSchemaChange?: (schema: DatasetField[]) => void;
}

export default function DatasetEditor({ dataset, onClose, onSave, onDraftChange, onSchemaChange }: Props) {
  const [sql_, setSql] = useState(dataset.sql);
  const [name, setName] = useState(dataset.name);
  const [activeTab, setActiveTab] = useState<'results' | 'schema'>('results');
  const [runTrigger, setRunTrigger] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const lastEmittedSchemaSignatureRef = useRef<string>('');
  const lastSchemaRunTriggerRef = useRef<number>(0);
  const lastDatasetIdRef = useRef(dataset.id);
  const lastDraftSignatureRef = useRef(JSON.stringify({ sql: dataset.sql, name: dataset.name }));

  useEffect(() => {
    if (lastDatasetIdRef.current === dataset.id) return;
    lastDatasetIdRef.current = dataset.id;
    setSql(dataset.sql);
    setName(dataset.name);
    setActiveTab('results');
    setRunTrigger(0);
    setIsSaving(false);
    lastEmittedSchemaSignatureRef.current = '';
    lastSchemaRunTriggerRef.current = 0;
    lastDraftSignatureRef.current = JSON.stringify({ sql: dataset.sql, name: dataset.name });
  }, [dataset.id, dataset.sql, dataset.name]);

  const { data: queryResult, isLoading: queryLoading, error: queryError } = useDatasetQuery(
    dataset.id, {}, {}, runTrigger > 0, sql_, runTrigger
  );
  const { data: schema } = useDatasetSchema(dataset.id);

  useEffect(() => {
    const signature = JSON.stringify({ sql: sql_, name });
    if (lastDraftSignatureRef.current === signature) return;
    lastDraftSignatureRef.current = signature;
    onDraftChange?.({ sql: sql_, name });
  }, [sql_, name, onDraftChange]);

  useEffect(() => {
    if (!queryResult?.columns?.length || runTrigger === 0) return;
    if (lastSchemaRunTriggerRef.current === runTrigger) return;

    const inferredSchema: DatasetField[] = queryResult.columns.map((column) => {
      const sample = queryResult.rows.find((row) => row[column] != null)?.[column];
      let type = 'string';
      if (typeof sample === 'number') type = 'number';
      else if (typeof sample === 'boolean') type = 'boolean';
      else if (sample instanceof Date) type = 'date';
      return { name: column, type };
    });

    const inferredSignature = JSON.stringify(inferredSchema);
    if (lastEmittedSchemaSignatureRef.current === inferredSignature) return;

    const currentSignature = JSON.stringify(dataset.schema ?? []);
    if (currentSignature === inferredSignature) {
      lastEmittedSchemaSignatureRef.current = inferredSignature;
      lastSchemaRunTriggerRef.current = runTrigger;
      return;
    }

    lastEmittedSchemaSignatureRef.current = inferredSignature;
    lastSchemaRunTriggerRef.current = runTrigger;
    onSchemaChange?.(inferredSchema);
  }, [queryResult, onSchemaChange, dataset.schema, runTrigger]);

  function handleRun() {
    setRunTrigger((n) => n + 1);
    setActiveTab('results');
  }

  async function handleSave() {
    try {
      setIsSaving(true);
      await onSave({ sql: sql_, name });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div style={{
      flex: 1,
      minHeight: 0,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignSelf: 'stretch',
      overflow: 'hidden',
      background: 'var(--color-surface)',
    }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        borderBottom: '1px solid var(--color-border)',
        flexShrink: 0,
      }}>
        <button className="btn-icon" onClick={onClose} title="Back">
          <ArrowLeft size={14} />
        </button>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{
            fontSize: '0.82rem',
            fontWeight: 600,
            border: '1px solid transparent',
            borderRadius: 4,
            padding: '2px 6px',
            background: 'transparent',
            color: 'var(--color-text)',
            width: 160,
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = 'transparent')}
        />
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '4px 12px' }} onClick={handleRun}>
          <Play size={12} style={{ marginRight: 4 }} /> Run
        </button>
        <button
          className="btn btn-secondary"
          style={{ fontSize: '0.75rem', padding: '4px 12px' }}
          onClick={handleSave}
          disabled={isSaving}
        >
          Save
        </button>
      </div>

      {/* SQL editor */}
      <div style={{ flex: '0 0 200px', display: 'flex', borderBottom: '1px solid var(--color-border)', overflow: 'hidden' }}>
        <SqlEditor value={sql_} onChange={setSql} />
      </div>

      {/* Result tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', flexShrink: 0 }}>
        {(['results', 'schema'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              fontSize: '0.75rem',
              fontWeight: activeTab === tab ? 600 : 400,
              color: activeTab === tab ? 'var(--color-primary)' : 'var(--color-text-muted)',
              borderBottom: activeTab === tab ? '2px solid var(--color-primary)' : '2px solid transparent',
              padding: '6px 14px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            {tab === 'results' ? <Table2 size={12} /> : <AlignLeft size={12} />}
            {tab === 'results' ? 'Results' : 'Schema'}
          </button>
        ))}
        {queryResult && (
          <span style={{ marginLeft: 'auto', padding: '6px 12px', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
            {queryResult.rowCount.toLocaleString()} rows · {queryResult.executionMs}ms
          </span>
        )}
      </div>

      {/* Results / Schema panel */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {activeTab === 'results' && (
          queryLoading ? (
            <div style={{ padding: 20, display: 'flex', gap: 8, color: 'var(--color-text-muted)', alignItems: 'center' }}>
              <Loader2 size={16} className="spin" /> Running query…
            </div>
          ) : queryError ? (
            <div style={{ padding: 16, color: 'var(--color-danger)', fontSize: '0.8rem' }}>
              Query error: {String(queryError)}
            </div>
          ) : queryResult ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
              <thead>
                <tr style={{ background: 'var(--color-bg)' }}>
                  {queryResult.columns.map((col) => (
                    <th key={col} style={{
                      padding: '4px 10px',
                      textAlign: 'left',
                      fontWeight: 600,
                      borderBottom: '1px solid var(--color-border)',
                      whiteSpace: 'nowrap',
                      color: 'var(--color-text-muted)',
                    }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queryResult.rows.slice(0, 100).map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    {queryResult.columns.map((col) => (
                      <td key={col} style={{ padding: '3px 10px', whiteSpace: 'nowrap', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {String(row[col] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: 20, color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
              Click Run to execute query
            </div>
          )
        )}

        {activeTab === 'schema' && (
          <div>
            {(schema ?? dataset.schema).map((field: DatasetField) => (
              <div key={field.name} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '5px 12px',
                borderBottom: '1px solid var(--color-border)',
                fontSize: '0.78rem',
              }}>
                <span style={{
                  width: 18,
                  height: 18,
                  borderRadius: 3,
                  background: 'var(--color-primary-bg)',
                  color: 'var(--color-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  {TYPE_ICON[field.type?.toLowerCase()] ?? TYPE_ICON.default}
                </span>
                <span style={{ fontWeight: 500 }}>{field.name}</span>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '0.72rem' }}>{field.type}</span>
                {field.comment && (
                  <span style={{ color: 'var(--color-text-subtle)', fontSize: '0.7rem', marginLeft: 'auto' }}>
                    {field.comment}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

