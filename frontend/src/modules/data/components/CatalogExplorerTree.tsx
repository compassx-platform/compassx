import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Database,
  Layers,
  Table,
  FileCode,
  ChevronRight,
  ChevronDown,
  Search,
  Plus,
  Copy,
  Check,
  Columns,
} from 'lucide-react';
import api from '@/lib/api';

export interface CatalogExplorerTreeProps {
  mode?: 'navigation' | 'exploration';
  onInsert?: (identifier: string) => void;
  onSelect?: (item: { kind: 'catalog' | 'schema' | 'table' | 'query'; catalog: string; schema?: string; name?: string }) => void;
  className?: string;
}

interface TableColumnInfo {
  name: string;
  data_type: string;
}

interface CatalogEntry {
  name: string;
  catalog_type?: string;
}

export const CatalogExplorerTree: React.FC<CatalogExplorerTreeProps> = ({
  mode = 'exploration',
  onInsert,
  onSelect,
  className = '',
}) => {
  const [filter, setFilter] = useState('');
  const [expandedCatalogs, setExpandedCatalogs] = useState<Record<string, boolean>>({});
  const [expandedSchemas, setExpandedSchemas] = useState<Record<string, boolean>>({});
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // 1. Fetch catalogs
  const catalogsQuery = useQuery<CatalogEntry[]>({
    queryKey: ['explorer-catalogs'],
    queryFn: () =>
      api.get<{ catalogs: { name: string; catalog_type?: string }[] }>('/sql-warehouse/catalog/catalogs')
        .then((r: any) => r.data.catalogs || [])
        .catch(() => api.get<any[]>('/catalog/catalogs').then((r: any) => r.data.map((c: any) => ({ name: c.name, catalog_type: c.catalog_type }))))
  });

  const toggleCatalog = (catName: string) => {
    setExpandedCatalogs(prev => ({ ...prev, [catName]: !prev[catName] }));
  };

  const toggleSchema = (key: string) => {
    setExpandedSchemas(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleTable = (key: string) => {
    setExpandedTables(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleCopy = (e: React.MouseEvent, identifier: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(identifier);
    setCopiedId(identifier);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleItemClick = (
    e: React.MouseEvent,
    kind: 'catalog' | 'schema' | 'table' | 'query' | 'column',
    catalog: string,
    schema?: string,
    name?: string,
    fullIdentifier?: string
  ) => {
    e.stopPropagation();
    if (mode === 'exploration') {
      if (fullIdentifier && onInsert) {
        onInsert(fullIdentifier);
      }
    } else if (onSelect && kind !== 'column') {
      onSelect({ kind, catalog, schema, name });
    }
  };

  const catalogs = catalogsQuery.data || [];

  return (
    <div className={`catalog-explorer-tree ${className}`} style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Search Bar */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--color-border)' }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={13} style={{ position: 'absolute', left: 8, color: 'var(--color-text-muted)', pointerEvents: 'none' }} />
          <input
            type="text"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Filter catalog assets..."
            style={{
              width: '100%',
              padding: '4px 8px 4px 28px',
              fontSize: 11,
              borderRadius: 4,
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'inherit',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Tree View */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '6px 0', fontSize: 12 }}>
        {catalogsQuery.isLoading && (
          <div style={{ padding: '12px', fontSize: 11, color: 'var(--color-text-muted)' }}>
            Loading catalogs...
          </div>
        )}

        {!catalogsQuery.isLoading && catalogs.length === 0 && (
          <div style={{ padding: '12px', fontSize: 11, color: 'var(--color-text-muted)' }}>
            No catalogs available
          </div>
        )}

        {catalogs.map((catalog: CatalogEntry) => (
          <CatalogNode
            key={catalog.name}
            catalogName={catalog.name}
            catalogType={catalog.catalog_type}
            isExpanded={!!expandedCatalogs[catalog.name] || !!filter}
            onToggle={() => toggleCatalog(catalog.name)}
            expandedSchemas={expandedSchemas}
            onToggleSchema={toggleSchema}
            expandedTables={expandedTables}
            onToggleTable={toggleTable}
            filter={filter}
            mode={mode}
            onItemClick={handleItemClick}
            onCopy={handleCopy}
            copiedId={copiedId}
          />
        ))}
      </div>
    </div>
  );
};

interface CatalogNodeProps {
  catalogName: string;
  catalogType?: string;
  isExpanded: boolean;
  onToggle: () => void;
  expandedSchemas: Record<string, boolean>;
  onToggleSchema: (key: string) => void;
  expandedTables: Record<string, boolean>;
  onToggleTable: (key: string) => void;
  filter: string;
  mode: 'navigation' | 'exploration';
  onItemClick: (
    e: React.MouseEvent,
    kind: 'catalog' | 'schema' | 'table' | 'query' | 'column',
    catalog: string,
    schema?: string,
    name?: string,
    fullIdentifier?: string
  ) => void;
  onCopy: (e: React.MouseEvent, identifier: string) => void;
  copiedId: string | null;
}

const CatalogNode: React.FC<CatalogNodeProps> = ({
  catalogName,
  catalogType,
  isExpanded,
  onToggle,
  expandedSchemas,
  onToggleSchema,
  expandedTables,
  onToggleTable,
  filter,
  mode,
  onItemClick,
  onCopy,
  copiedId,
}) => {
  const schemasQuery = useQuery<string[]>({
    queryKey: ['explorer-schemas', catalogName],
    queryFn: () =>
      api.get<{ schemas: string[] }>('/sql-warehouse/catalog/schemas', { params: { catalog: catalogName } })
        .then((r: any) => r.data.schemas || [])
        .catch(() => api.get<any[]>(`/catalog/catalogs/${encodeURIComponent(catalogName)}/schemas`).then((r: any) => r.data.map((s: any) => s.name))),
    enabled: isExpanded || !!filter,
  });

  const schemas = schemasQuery.data || [];
  const matchesFilter = filter ? catalogName.toLowerCase().includes(filter.toLowerCase()) || schemas.some((s: string) => s.toLowerCase().includes(filter.toLowerCase())) : true;

  if (!matchesFilter && filter) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 10px',
          cursor: 'pointer',
          borderRadius: 4,
          userSelect: 'none',
        }}
        className="hover:bg-slate-800/40"
        title={`Catalog: ${catalogName}`}
      >
        <span style={{ color: 'var(--color-text-muted)', display: 'flex' }}>
          {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </span>
        <Database size={13} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        <span style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {catalogName}
        </span>
        {catalogType && (
          <span style={{ fontSize: 9, opacity: 0.6, textTransform: 'uppercase' }}>{catalogType}</span>
        )}
      </div>

      {isExpanded && (
        <div style={{ paddingLeft: 16 }}>
          {schemasQuery.isLoading && (
            <div style={{ padding: '4px 8px', fontSize: 11, color: 'var(--color-text-muted)' }}>Loading schemas...</div>
          )}
          {!schemasQuery.isLoading && schemas.length === 0 && (
            <div style={{ padding: '4px 8px', fontSize: 11, color: 'var(--color-text-muted)' }}>No schemas</div>
          )}
          {schemas.map((schema: string) => (
            <SchemaNode
              key={schema}
              catalogName={catalogName}
              schemaName={schema}
              isExpanded={!!expandedSchemas[`${catalogName}.${schema}`] || !!filter}
              onToggle={() => onToggleSchema(`${catalogName}.${schema}`)}
              expandedTables={expandedTables}
              onToggleTable={onToggleTable}
              filter={filter}
              mode={mode}
              onItemClick={onItemClick}
              onCopy={onCopy}
              copiedId={copiedId}
            />
          ))}
        </div>
      )}
    </div>
  );
};

interface SchemaNodeProps {
  catalogName: string;
  schemaName: string;
  isExpanded: boolean;
  onToggle: () => void;
  expandedTables: Record<string, boolean>;
  onToggleTable: (key: string) => void;
  filter: string;
  mode: 'navigation' | 'exploration';
  onItemClick: (
    e: React.MouseEvent,
    kind: 'catalog' | 'schema' | 'table' | 'query' | 'column',
    catalog: string,
    schema?: string,
    name?: string,
    fullIdentifier?: string
  ) => void;
  onCopy: (e: React.MouseEvent, identifier: string) => void;
  copiedId: string | null;
}

const SchemaNode: React.FC<SchemaNodeProps> = ({
  catalogName,
  schemaName,
  isExpanded,
  onToggle,
  expandedTables,
  onToggleTable,
  filter,
  mode,
  onItemClick,
  onCopy,
  copiedId,
}) => {
  const schemaKey = `${catalogName}.${schemaName}`;

  const tablesQuery = useQuery<string[]>({
    queryKey: ['explorer-tables', catalogName, schemaName],
    queryFn: () =>
      api.get<{ tables: string[] }>('/sql-warehouse/catalog/tables', { params: { catalog: catalogName, schema: schemaName } })
        .then((r: any) => r.data.tables || [])
        .catch(() => api.get<any[]>(`/catalog/tables`, { params: { catalog: catalogName, schema_name: schemaName } }).then((r: any) => r.data.map((t: any) => t.name))),
    enabled: isExpanded || !!filter,
  });

  const queriesQuery = useQuery<any[]>({
    queryKey: ['explorer-queries', catalogName, schemaName],
    queryFn: () =>
      api.get<any[]>(`/catalog/catalogs/${encodeURIComponent(catalogName)}/schemas/${encodeURIComponent(schemaName)}/queries`)
        .then((r: any) => r.data || [])
        .catch(() => []),
    enabled: isExpanded || !!filter,
  });

  const tables = tablesQuery.data || [];
  const queries = queriesQuery.data || [];

  const matches = !filter || schemaName.toLowerCase().includes(filter.toLowerCase()) || tables.some((t: string) => t.toLowerCase().includes(filter.toLowerCase()));
  if (!matches && filter) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 8px',
          cursor: 'pointer',
          borderRadius: 4,
          userSelect: 'none',
        }}
        className="hover:bg-slate-800/40"
        title={`Schema: ${schemaName}`}
      >
        <span style={{ color: 'var(--color-text-muted)', display: 'flex' }}>
          {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
        <Layers size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        <span style={{ fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {schemaName}
        </span>
      </div>

      {isExpanded && (
        <div style={{ paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {tablesQuery.isLoading && (
            <div style={{ padding: '2px 6px', fontSize: 11, color: 'var(--color-text-muted)' }}>Loading tables...</div>
          )}

          {tables.map((table: string) => (
            <TableNode
              key={table}
              catalogName={catalogName}
              schemaName={schemaName}
              tableName={table}
              isExpanded={!!expandedTables[`${schemaKey}.${table}`]}
              onToggle={() => onToggleTable(`${schemaKey}.${table}`)}
              mode={mode}
              onItemClick={onItemClick}
              onCopy={onCopy}
              copiedId={copiedId}
            />
          ))}

          {queries.map((q: any) => {
            const queryIdentifier = `/* ${q.name} */\n${q.sql_text}`;
            return (
              <div
                key={q.id || q.name}
                onClick={e => onItemClick(e, 'query', catalogName, schemaName, q.name, queryIdentifier)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '3px 6px',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
                className="hover:bg-slate-800/40 group"
                title={`Saved Query: ${q.name}`}
              >
                <FileCode size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>
                  {q.name}
                </span>
                <button
                  type="button"
                  onClick={e => onCopy(e, q.sql_text)}
                  style={{ opacity: 0, padding: 2, background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
                  className="group-hover:opacity-100"
                  title="Copy SQL"
                >
                  {copiedId === q.sql_text ? <Check size={11} className="text-success" /> : <Copy size={11} />}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

interface TableNodeProps {
  catalogName: string;
  schemaName: string;
  tableName: string;
  isExpanded: boolean;
  onToggle: () => void;
  mode: 'navigation' | 'exploration';
  onItemClick: (
    e: React.MouseEvent,
    kind: 'catalog' | 'schema' | 'table' | 'query' | 'column',
    catalog: string,
    schema?: string,
    name?: string,
    fullIdentifier?: string
  ) => void;
  onCopy: (e: React.MouseEvent, identifier: string) => void;
  copiedId: string | null;
}

const TableNode: React.FC<TableNodeProps> = ({
  catalogName,
  schemaName,
  tableName,
  isExpanded,
  onToggle,
  mode,
  onItemClick,
  onCopy,
  copiedId,
}) => {
  const fullTableIdentifier = `"${catalogName}"."${schemaName}"."${tableName}"`;

  const columnsQuery = useQuery<TableColumnInfo[]>({
    queryKey: ['explorer-columns', catalogName, schemaName, tableName],
    queryFn: () =>
      api.get<any>(`/catalog/tables/${encodeURIComponent(catalogName)}/${encodeURIComponent(schemaName)}/${encodeURIComponent(tableName)}`)
        .then((r: any) => (r.data?.columns || []) as TableColumnInfo[])
        .catch(() => []),
    enabled: isExpanded,
  });

  const columns = columnsQuery.data || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '2px 6px',
          borderRadius: 4,
          cursor: 'pointer',
        }}
        className="hover:bg-slate-800/40 group"
        onClick={e => {
          if (mode === 'exploration') {
            onItemClick(e, 'table', catalogName, schemaName, tableName, fullTableIdentifier);
          } else {
            onItemClick(e, 'table', catalogName, schemaName, tableName, fullTableIdentifier);
          }
        }}
        title={`Table: ${fullTableIdentifier} (Click to insert)`}
      >
        <span
          onClick={e => {
            e.stopPropagation();
            onToggle();
          }}
          style={{ color: 'var(--color-text-muted)', display: 'flex', cursor: 'pointer' }}
        >
          {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </span>
        <Table size={12} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>
          {tableName}
        </span>

        {/* Hover Action: Insert into query */}
        <button
          type="button"
          onClick={e => onItemClick(e, 'table', catalogName, schemaName, tableName, fullTableIdentifier)}
          style={{ opacity: 0, padding: '1px 4px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 3, cursor: 'pointer', color: 'inherit', fontSize: 10, display: 'flex', alignItems: 'center', gap: 2 }}
          className="group-hover:opacity-100"
          title="Insert table identifier into SQL"
        >
          <Plus size={10} /> Insert
        </button>

        <button
          type="button"
          onClick={e => onCopy(e, fullTableIdentifier)}
          style={{ opacity: 0, padding: 2, background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
          className="group-hover:opacity-100"
          title="Copy identifier"
        >
          {copiedId === fullTableIdentifier ? <Check size={11} className="text-success" /> : <Copy size={11} />}
        </button>
      </div>

      {isExpanded && (
        <div style={{ paddingLeft: 22, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {columnsQuery.isLoading && (
            <div style={{ fontSize: 10, color: 'var(--color-text-muted)' }}>Loading columns...</div>
          )}
          {columns.map((col: TableColumnInfo) => {
            const colIdentifier = `"${col.name}"`;
            return (
              <div
                key={col.name}
                onClick={e => onItemClick(e, 'column', catalogName, schemaName, col.name, colIdentifier)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '1px 4px',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: 10,
                }}
                className="hover:bg-slate-800/30 group"
                title={`Column: ${col.name} (${col.data_type}) - Click to insert`}
              >
                <Columns size={10} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {col.name}
                </span>
                <span style={{ fontSize: 9, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                  {col.data_type}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
