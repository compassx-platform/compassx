import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Play,
  Loader2,
  Clock,
  Download,
  AlertCircle,
  ChevronDown,
  Check,
} from 'lucide-react';

export interface SqlQueryResult {
  id?: string;
  query_text?: string;
  status?: string;
  duration_ms: number;
  rows_returned: number;
  columns: string[];
  rows: any[][];
  error_message?: string | null;
  executed_at?: string;
}

export interface SqlWarehouseItem {
  id: string;
  name: string;
  status: string;
  engine?: string;
}

export interface CatalogItem {
  name: string;
}

export interface RunOptions {
  limit?: number;
}

export interface ModularSqlEditorProps {
  sql: string;
  onSqlChange: (val: string) => void;
  warehouses: SqlWarehouseItem[];
  activeWarehouseId?: string;
  onWarehouseChange: (whId: string) => void;
  catalogs?: CatalogItem[];
  activeCatalog?: string;
  onCatalogChange?: (cat: string) => void;
  schemas?: string[];
  activeSchema?: string;
  onSchemaChange?: (sch: string) => void;
  onRun: (options?: RunOptions) => void;
  isExecuting?: boolean;
  result?: SqlQueryResult | null;
  error?: string | null;
  canRun?: boolean;
  queryName?: string;
  toolbarActions?: React.ReactNode;
  headerMeta?: React.ReactNode;
  onPerformanceClick?: (result: SqlQueryResult) => void;
  readOnly?: boolean;
}

export const ModularSqlEditor: React.FC<ModularSqlEditorProps> = ({
  sql,
  onSqlChange,
  warehouses,
  activeWarehouseId,
  onWarehouseChange,
  catalogs,
  activeCatalog,
  onCatalogChange,
  schemas,
  activeSchema,
  onSchemaChange,
  onRun,
  isExecuting = false,
  result,
  error,
  canRun = true,
  queryName = 'query_result',
  toolbarActions,
  headerMeta,
  onPerformanceClick,
  readOnly = false,
}) => {
  const [runMode, setRunMode] = useState<'1000' | 'all'>('1000');
  const [isRunMenuOpen, setIsRunMenuOpen] = useState<boolean>(false);
  const runMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (runMenuRef.current && !runMenuRef.current.contains(e.target as Node)) {
        setIsRunMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const lineNumbers = useMemo(() => {
    const lines = sql.split('\n').length;
    return Array.from({ length: Math.max(lines, 1) }, (_, i) => i + 1);
  }, [sql]);

  const activeWarehouse = warehouses.find(w => w.id === activeWarehouseId) || warehouses[0];

  const handleExecute = (mode?: '1000' | 'all') => {
    const targetMode = mode || runMode;
    const limit = targetMode === '1000' ? 1000 : 50000;
    onRun({ limit });
  };

  const getHeaderIcon = (colName: string) => {
    const lower = colName.toLowerCase();
    if (lower.includes('id') || lower.includes('count') || lower.includes('quantity')) {
      return <span style={{ color: 'var(--color-primary)', marginRight: 4, fontWeight: 'bold', fontSize: 10 }}>123</span>;
    }
    if (lower.includes('ts') || lower.includes('date') || lower.includes('time') || lower.includes('at')) {
      return <Clock size={11} style={{ marginRight: 4, color: 'var(--color-text-muted)' }} />;
    }
    return <span style={{ color: '#ec4899', marginRight: 4, fontWeight: 'bold', fontSize: 10 }}>abc</span>;
  };

  const handleDownloadCsv = () => {
    if (!result || !result.columns || !result.rows || result.rows.length === 0) return;
    const header = result.columns.join(',');
    const rows = result.rows.map(r => r.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','));
    const csvContent = 'data:text/csv;charset=utf-8,' + [header, ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${queryName}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', minHeight: 0, overflow: 'hidden' }}>
      {/* Editor Toolbar */}
      <div className="swh-editor-toolbar-db">
        <div className="swh-toolbar-left" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Split Run Button */}
          <div className="swh-run-split-btn-container" ref={runMenuRef}>
            <button
              className="swh-btn-run-main"
              onClick={() => handleExecute()}
              disabled={!canRun || isExecuting}
              title={`Execute Query (Ctrl + Enter) — ${runMode === '1000' ? 'Limit 1000' : 'Run All'}`}
            >
              {isExecuting ? <Loader2 size={13} className="spin" /> : <Play size={13} fill="currentColor" />}
              <span>{runMode === '1000' ? 'Run 1000' : 'Run all'}</span>
            </button>
            <div className="swh-btn-run-divider" />
            <button
              type="button"
              className="swh-btn-run-menu-trigger"
              onClick={() => setIsRunMenuOpen(prev => !prev)}
              disabled={!canRun || isExecuting}
              title="Execution limit options"
            >
              <ChevronDown size={12} />
            </button>

            {/* Run Options Dropdown */}
            {isRunMenuOpen && (
              <div className="swh-run-dropdown-menu">
                <button
                  type="button"
                  className={`swh-run-dropdown-item ${runMode === '1000' ? 'is-selected' : ''}`}
                  onClick={() => {
                    setRunMode('1000');
                    setIsRunMenuOpen(false);
                    handleExecute('1000');
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 600 }}>Run 1000</span>
                    <span style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>Limit to 1,000 records</span>
                  </div>
                  {runMode === '1000' && <Check size={13} />}
                </button>

                <button
                  type="button"
                  className={`swh-run-dropdown-item ${runMode === 'all' ? 'is-selected' : ''}`}
                  onClick={() => {
                    setRunMode('all');
                    setIsRunMenuOpen(false);
                    handleExecute('all');
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 600 }}>Run all</span>
                    <span style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>Fetch all query results</span>
                  </div>
                  {runMode === 'all' && <Check size={13} />}
                </button>
              </div>
            )}
          </div>

          {toolbarActions}

          <div className="swh-toolbar-meta">
            {isExecuting && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--color-primary)' }}>
                <Loader2 size={12} className="spin" /> Running
              </span>
            )}
            {!isExecuting && result && (
              <span className="text-success" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                ✓ {(result.duration_ms / 1000).toFixed(2)}s ({result.rows_returned} rows)
              </span>
            )}
            {!isExecuting && error && (
              <span className="text-danger" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <AlertCircle size={12} /> Error
              </span>
            )}

            {catalogs && onCatalogChange && schemas && onSchemaChange && (
              <div className="swh-catalog-schema-selector-db">
                <select value={activeCatalog} onChange={e => onCatalogChange(e.target.value)} title="Select Catalog">
                  {catalogs.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                </select>
                <span className="swh-separator">.</span>
                <select value={activeSchema} onChange={e => onSchemaChange(e.target.value)} title="Select Schema">
                  {schemas.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            )}

            {headerMeta}
          </div>
        </div>

        <div className="swh-toolbar-right">
          {warehouses.length > 0 && (
            <div className="swh-wh-selector-db">
              <div className={`swh-dot ${activeWarehouse?.status === 'running' ? 'is-running' : ''}`} />
              <select value={activeWarehouseId} onChange={e => onWarehouseChange(e.target.value)} title="Select Compute Warehouse">
                {warehouses.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Code Textarea Area */}
      <div className="swh-ide-editor-container" style={{ flex: 1, minHeight: '140px' }}>
        <div className="swh-line-numbers">
          {lineNumbers.map(n => <div key={n}>{n}</div>)}
        </div>
        <textarea
          className="swh-editor-textarea"
          value={sql}
          onChange={e => onSqlChange(e.target.value)}
          spellCheck={false}
          readOnly={readOnly}
          onKeyDown={e => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
              e.preventDefault();
              if (canRun && !isExecuting) handleExecute();
            }
          }}
        />
      </div>

      {/* Results Panel */}
      <div className="swh-results-pane-db" style={{ flex: 1, minHeight: '140px', display: 'flex', flexDirection: 'column' }}>
        <div className="swh-results-header-db">
          <div className="swh-results-tabs">
            <div className="swh-results-tab is-active">Results</div>
          </div>
        </div>

        <div className="swh-results-table-wrap" style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {isExecuting && (
            <div className="swh-empty">
              <Loader2 size={24} className="spin text-primary" />
              <span>Running query...</span>
            </div>
          )}
          {error && (
            <div className="swh-empty text-danger">
              <AlertCircle size={24} />
              <span>{error}</span>
            </div>
          )}
          {!isExecuting && !error && result && (
            <table className="swh-results-table">
              <thead>
                <tr>
                  <th>#</th>
                  {result.columns.map(c => (
                    <th key={c}>
                      <span style={{ display: 'inline-flex', alignItems: 'center' }}>
                        {getHeaderIcon(c)}
                        {c}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    {r.map((cell, j) => <td key={j}>{cell == null ? 'NULL' : String(cell)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!isExecuting && !error && !result && (
            <div className="swh-empty">
              <Play size={24} className="text-muted" />
              <span>Run a query to view results</span>
            </div>
          )}
        </div>

        {/* Results Footer */}
        {result && (
          <div className="swh-results-footer">
            <div className="swh-results-footer-left">
              <button
                onClick={handleDownloadCsv}
                title="Download CSV"
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)' }}
              >
                <Download size={13} className="hover:text-primary" />
              </button>
              <span>{result.rows_returned} rows | {(result.duration_ms / 1000).toFixed(2)}s runtime</span>
              {onPerformanceClick && (
                <a
                  href="#"
                  className="swh-performance-link"
                  onClick={e => {
                    e.preventDefault();
                    onPerformanceClick(result);
                  }}
                >
                  See performance
                </a>
              )}
            </div>
            <div className="swh-results-footer-right">
              <span>{result.executed_at ? new Date(result.executed_at).toLocaleTimeString() : 'Refreshed just now'}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
