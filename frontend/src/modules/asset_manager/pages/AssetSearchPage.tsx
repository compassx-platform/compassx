import { useState } from 'react';
import { Search, Box, Filter, GitBranch } from 'lucide-react';
import {
  useAssetInstances,
  useAssetTypes,
  type AssetStatus,
  type ListInstancesParams,
} from '@/modules/asset_manager/hooks/useAssetManager';
import { useScopedNavigate } from '@/lib/appNavigation';

const STATUS_COLOR: Record<AssetStatus, string> = {
  ACTIVE: '#10b981',
  INACTIVE: '#9ca3af',
  DECOMMISSIONED: '#6b7280',
  PLANNED: '#3b82f6',
  MAINTENANCE: '#f59e0b',
};

type AssetSearchPageProps = {
  embedded?: boolean;
};

export default function AssetSearchPage({ embedded = false }: AssetSearchPageProps = {}) {
  const navigate = useScopedNavigate();
  const { data: types } = useAssetTypes();

  const [search, setSearch] = useState('');
  const [typeId, setTypeId] = useState('');
  const [status, setStatus] = useState('');
  const [submitted, setSubmitted] = useState<ListInstancesParams>({});

  const { data, isLoading } = useAssetInstances(
    Object.keys(submitted).length > 0 ? submitted : undefined
  );

  function handleSearch() {
    const params: ListInstancesParams = {};
    if (search.trim()) params.q = search.trim();
    if (typeId) params.type_id = Number(typeId);
    if (status) params.status = [status];
    params.limit = 100;
    setSubmitted(params);
  }

  return (
    <div className={embedded ? 'asset-embedded-view' : 'page-section asset-page'}>
      {!embedded && (
        <div className="db-page-header">
          <div className="asset-page-title">
            <Search size={22} color="var(--color-primary)" />
            <div>
              <h1 className="db-page-title">Asset Search</h1>
              <div className="asset-summary-bar">
                {data ? <span>{data.pagination.total} result{data.pagination.total === 1 ? '' : 's'}</span> : <span>Find assets by name, type, status, or path</span>}
              </div>
            </div>
          </div>
          <div className="asset-page-actions">
            <button className="btn btn-secondary" onClick={() => navigate('/assets')}>
              <GitBranch size={14} /> Explorer
            </button>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="asset-filter-row" style={{ marginBottom: 16 }}>
        <div className="search-bar-wrapper" style={{ flex: '0 0 320px' }}>
          <Search size={14} className="search-icon" />
          <input
            className="search-bar"
            placeholder="Search by name, code, description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <select
          className="form-input"
          style={{ width: 180, height: 32 }}
          value={typeId}
          onChange={(e) => setTypeId(e.target.value)}
        >
          <option value="">All types</option>
          {(types ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select
          className="form-input"
          style={{ width: 160, height: 32 }}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          {(['ACTIVE', 'INACTIVE', 'PLANNED', 'MAINTENANCE', 'DECOMMISSIONED'] as AssetStatus[]).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button className="btn btn-primary" onClick={handleSearch}>
          <Filter size={13} /> Search
        </button>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="loading-state">Searching…</div>
      ) : !data ? (
        <div className="empty-state">
          <Search size={36} color="var(--color-text-muted)" />
          <p>Enter search criteria and click Search.</p>
        </div>
      ) : data.data.length === 0 ? (
        <div className="empty-state">
          <Box size={36} color="var(--color-text-muted)" />
          <p>No assets found matching your criteria.</p>
        </div>
      ) : (
        <>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>
            {data.pagination.total} result{data.pagination.total !== 1 ? 's' : ''}
            {data.pagination.has_more && ` (showing first ${data.data.length})`}
          </div>
          <div className="asset-table-wrap">
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Type</th>
                <th>Status</th>
                <th>Path</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((a) => (
                <tr
                  key={a.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/assets/${a.id}`)}
                >
                  <td style={{ fontWeight: 500 }}>{a.name}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{a.code ?? '—'}</td>
                  <td style={{ fontSize: 12 }}>{a.asset_type_name ?? String(a.asset_type_id)}</td>
                  <td>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: STATUS_COLOR[a.status] }}>
                      <span style={{ width: 7, height: 7, borderRadius: '50%', background: STATUS_COLOR[a.status] }} />
                      {a.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{a.path}</td>
                  <td style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                    {new Date(a.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}
    </div>
  );
}
