import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Save,
  History,
  GitCommit,
  Check,
  AlertCircle,
  Loader2,
  X,
  Database,
} from 'lucide-react';
import api from '@/lib/api';
import { ModularSqlEditor, SqlQueryResult, SqlWarehouseItem } from '../../sql_warehouse/components/ModularSqlEditor';

export interface CatalogQueryVersion {
  id: string;
  query_id: string;
  version: number;
  sql_text: string;
  description?: string | null;
  change_summary?: string | null;
  created_by: string;
  created_at: string;
}

export interface CatalogQueryData {
  id: string;
  catalog_name: string;
  schema_name: string;
  name: string;
  full_name: string;
  sql_text: string;
  owner: string;
  description?: string | null;
  current_version: number;
  versions?: CatalogQueryVersion[];
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface CatalogQueryEditorTabProps {
  catalog: string;
  schema: string;
  queryName: string;
  onDelete?: () => void;
}

export const CatalogQueryEditorTab: React.FC<CatalogQueryEditorTabProps> = ({
  catalog,
  schema,
  queryName,
}) => {
  const qc = useQueryClient();

  // 1. Fetch Query Metadata and Content
  const queryDataQuery = useQuery<CatalogQueryData>({
    queryKey: ['uc-query', catalog, schema, queryName],
    queryFn: () =>
      api.get<CatalogQueryData>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/queries/${encodeURIComponent(queryName)}`)
        .then((r: any) => r.data),
  });

  // 2. Fetch Query Versions
  const versionsQuery = useQuery<CatalogQueryVersion[]>({
    queryKey: ['uc-query-versions', catalog, schema, queryName],
    queryFn: () =>
      api.get<CatalogQueryVersion[]>(`/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/queries/${encodeURIComponent(queryName)}/versions`)
        .then((r: any) => r.data),
  });

  // 3. Fetch Warehouses for execution
  const warehousesQuery = useQuery<SqlWarehouseItem[]>({
    queryKey: ['sql-warehouses'],
    queryFn: () => api.get<SqlWarehouseItem[]>('/warehouses').then((r: any) => r.data),
  });

  const queryObj = queryDataQuery.data;
  const versions = versionsQuery.data || queryObj?.versions || [];
  const warehouses = warehousesQuery.data || [];

  const [activeWarehouseId, setActiveWarehouseId] = useState<string>('');
  const [currentSql, setCurrentSql] = useState<string>('');
  const [selectedVersion, setSelectedVersion] = useState<number>(1);
  const [isModified, setIsModified] = useState<boolean>(false);

  // Execution state
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [result, setResult] = useState<SqlQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Save version modal state
  const [showSaveModal, setShowSaveModal] = useState<boolean>(false);
  const [changeSummary, setChangeSummary] = useState<string>('');
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Set default warehouse
  useEffect(() => {
    if (warehouses.length > 0 && !activeWarehouseId) {
      const running = warehouses.find((w: SqlWarehouseItem) => w.status === 'running') || warehouses[0];
      setActiveWarehouseId(running.id);
    }
  }, [warehouses, activeWarehouseId]);

  // Sync initial SQL and version
  useEffect(() => {
    if (queryObj) {
      setCurrentSql(queryObj.sql_text);
      setSelectedVersion(queryObj.current_version || 1);
      setIsModified(false);
    }
  }, [queryObj]);

  const handleVersionChange = (vNum: number) => {
    setSelectedVersion(vNum);
    const target = versions.find((v: CatalogQueryVersion) => v.version === vNum);
    if (target) {
      setCurrentSql(target.sql_text);
      setIsModified(target.sql_text !== queryObj?.sql_text);
    }
  };

  const handleSqlChange = (val: string) => {
    setCurrentSql(val);
    const currentVersionObj = versions.find((v: CatalogQueryVersion) => v.version === selectedVersion);
    const baseSql = currentVersionObj ? currentVersionObj.sql_text : queryObj?.sql_text;
    setIsModified(val !== baseSql);
  };

  // Run Query
  const handleRun = async (options?: { limit?: number }) => {
    if (!activeWarehouseId || !currentSql.trim()) return;
    setIsExecuting(true);
    setError(null);
    try {
      const res = await api.post<SqlQueryResult>('/sql/query', {
        warehouse_id: activeWarehouseId,
        sql: currentSql,
        catalog,
        schema_name: schema,
        source: `catalog_query:${catalog}.${schema}.${queryName}`,
        max_rows: options?.limit ?? 1000,
      });
      setResult(res.data);
      if (res.data.error_message) {
        setError(res.data.error_message);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to execute query');
    } finally {
      setIsExecuting(false);
    }
  };

  // Save New Version Mutation
  const saveVersionMutation = useMutation({
    mutationFn: async (payload: { sql_text: string; change_summary?: string }) => {
      return api.post<CatalogQueryVersion>(
        `/catalog/catalogs/${encodeURIComponent(catalog)}/schemas/${encodeURIComponent(schema)}/queries/${encodeURIComponent(queryName)}/versions`,
        payload
      ).then((r: any) => r.data);
    },
    onSuccess: (newVersion) => {
      qc.invalidateQueries({ queryKey: ['uc-query', catalog, schema, queryName] });
      qc.invalidateQueries({ queryKey: ['uc-query-versions', catalog, schema, queryName] });
      qc.invalidateQueries({ queryKey: ['uc-schema-queries', catalog, schema] });
      setSelectedVersion(newVersion.version);
      setIsModified(false);
      setShowSaveModal(false);
      setChangeSummary('');
      setFeedback({ type: 'success', message: `Saved as version ${newVersion.version}` });
      setTimeout(() => setFeedback(null), 3000);
    },
    onError: (err: any) => {
      setFeedback({
        type: 'error',
        message: err?.response?.data?.detail || 'Failed to save new version',
      });
    },
  });

  const handleSaveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    saveVersionMutation.mutate({
      sql_text: currentSql,
      change_summary: changeSummary.trim() || undefined,
    });
  };

  if (queryDataQuery.isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8, color: 'var(--color-text-muted)' }}>
        <Loader2 size={20} className="spin" />
        <span>Loading catalog query...</span>
      </div>
    );
  }

  if (queryDataQuery.isError || !queryObj) {
    return (
      <div style={{ padding: 24, color: 'var(--color-danger)' }}>
        <AlertCircle size={20} style={{ display: 'inline', marginRight: 8 }} />
        <span>Failed to load query {catalog}.{schema}.{queryName}</span>
      </div>
    );
  }

  const latestVersion = queryObj.current_version || 1;

  const toolbarActions = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {/* Version Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 6, padding: '0 8px', height: 30, boxSizing: 'border-box' }}>
        <GitCommit size={12} style={{ color: 'var(--color-primary)' }} />
        <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>v</span>
        <select
          value={selectedVersion}
          onChange={e => handleVersionChange(Number(e.target.value))}
          style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: 12, fontWeight: 600, outline: 'none', cursor: 'pointer' }}
          title="Select Query Version"
        >
          {versions.map((v: CatalogQueryVersion) => (
            <option key={v.version} value={v.version}>
              v{v.version} {v.version === latestVersion ? '(latest)' : ''} {v.change_summary ? `— ${v.change_summary.slice(0, 20)}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Save New Version Button */}
      <button
        onClick={() => {
          setChangeSummary('');
          setShowSaveModal(true);
        }}
        className="swh-btn"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          height: 30,
          padding: '0 12px',
          boxSizing: 'border-box',
          borderRadius: 6,
          fontSize: 12,
          fontWeight: 600,
          background: isModified ? 'var(--color-primary)' : 'var(--color-surface)',
          color: isModified ? '#ffffff' : 'inherit',
          border: isModified ? 'none' : '1px solid var(--color-border)',
          cursor: 'pointer',
        }}
        title="Save SQL as a new version"
      >
        <Save size={13} />
        <span>{isModified ? 'Save New Version *' : 'Save Version'}</span>
      </button>

      {/* Feedback message */}
      {feedback && (
        <span style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 4, color: feedback.type === 'success' ? 'var(--color-success, #10b981)' : 'var(--color-danger, #ef4444)' }}>
          {feedback.type === 'success' ? <Check size={12} /> : <AlertCircle size={12} />}
          {feedback.message}
        </span>
      )}
    </div>
  );

  const headerMeta = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--color-text-muted)' }}>
      <span style={{ fontWeight: 500, color: 'var(--color-text)' }}>{catalog}.{schema}.{queryName}</span>
      <span>•</span>
      <span>Governed Catalog Asset</span>
    </div>
  );

  return (
    <div style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <ModularSqlEditor
        sql={currentSql}
        onSqlChange={handleSqlChange}
        warehouses={warehouses}
        activeWarehouseId={activeWarehouseId}
        onWarehouseChange={setActiveWarehouseId}
        onRun={handleRun}
        isExecuting={isExecuting}
        result={result}
        error={error}
        canRun={!!activeWarehouseId && currentSql.trim().length > 0}
        queryName={queryName}
        toolbarActions={toolbarActions}
        headerMeta={headerMeta}
      />

      {/* Save Version Modal */}
      {showSaveModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            backdropFilter: 'blur(2px)',
          }}
          onClick={() => setShowSaveModal(false)}
        >
          <div
            style={{
              background: 'var(--color-surface, #1e293b)',
              border: '1px solid var(--color-border, #334155)',
              borderRadius: 8,
              width: 460,
              maxWidth: '90vw',
              padding: 20,
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <GitCommit size={18} style={{ color: 'var(--color-primary)' }} />
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Save New Query Version</h3>
              </div>
              <button
                onClick={() => setShowSaveModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
              Saving will create <strong style={{ color: 'var(--color-text)' }}>version {latestVersion + 1}</strong> of{' '}
              <span style={{ color: 'var(--color-primary)' }}>{catalog}.{schema}.{queryName}</span>. Previous versions remain preserved in history.
            </div>

            <form onSubmit={handleSaveSubmit}>
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 12, fontWeight: 500, marginBottom: 6, display: 'block' }}>
                  Change Summary / Note (optional)
                </label>
                <input
                  type="text"
                  value={changeSummary}
                  onChange={e => setChangeSummary(e.target.value)}
                  placeholder="e.g. Added date filter, updated joins..."
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 6,
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2, rgba(0,0,0,0.2))',
                    color: 'inherit',
                    outline: 'none',
                    fontSize: 13,
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setShowSaveModal(false)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 6,
                    border: '1px solid var(--color-border)',
                    background: 'transparent',
                    color: 'inherit',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saveVersionMutation.isPending}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 6,
                    border: 'none',
                    background: 'var(--color-primary)',
                    color: '#ffffff',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 12,
                  }}
                >
                  {saveVersionMutation.isPending && <Loader2 size={13} className="spin" />}
                  <span>Save Version {latestVersion + 1}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
