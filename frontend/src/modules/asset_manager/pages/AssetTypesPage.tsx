import { useState } from 'react';
import { Box, GitBranch, Layers, Plus, Trash2, Pencil, Search } from 'lucide-react';
import { useAssetTypes, useDeleteAssetType, type AssetType } from '@/modules/asset_manager/hooks/useAssetManager';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import ConfirmDialog from '@/components/common/ConfirmDialog';

const CATEGORY_COLORS: Record<string, string> = {
  SITE: '#3b82f6',
  EQUIPMENT: '#10b981',
  COMPONENT: '#f59e0b',
  TAG: '#8b5cf6',
  EVENT_TYPE: '#ef4444',
};

type AssetTypesPageProps = {
  embedded?: boolean;
};

export default function AssetTypesPage({ embedded = false }: AssetTypesPageProps = {}) {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const { data: types, isLoading } = useAssetTypes();
  const deleteMutation = useDeleteAssetType();
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [typePendingDelete, setTypePendingDelete] = useState<AssetType | null>(null);

  const filtered = (types ?? []).filter((t) => {
    const matchSearch = !search.trim() || t.name.toLowerCase().includes(search.toLowerCase()) || t.slug.includes(search.toLowerCase());
    const matchCat = !categoryFilter || t.category === categoryFilter;
    return matchSearch && matchCat;
  });

  async function handleDelete(t: AssetType) {
    try {
      await deleteMutation.mutateAsync(t.id);
      toast.success(`Deleted "${t.name}"`);
      setTypePendingDelete(null);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Delete failed';
      setTypePendingDelete(null);
      toast.error(msg);
    }
  }

  return (
    <div className={embedded ? 'asset-embedded-view' : 'page-section asset-page'}>
      {!embedded && (
        <div className="db-page-header">
          <div className="asset-page-title">
            <Layers size={22} color="var(--color-primary)" />
            <div>
              <h1 className="db-page-title">Asset Types</h1>
              <div className="asset-summary-bar">
                <span>{filtered.length} shown</span>
                <span>{types?.length ?? 0} total</span>
              </div>
            </div>
          </div>
          <div className="asset-page-actions">
            <button className="btn btn-secondary" onClick={() => navigate('/assets')}>
              <GitBranch size={14} /> Explorer
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/assets/types/new')}>
              <Plus size={14} /> New Type
            </button>
          </div>
        </div>
      )}

      <div className="asset-filter-row" style={{ marginBottom: 16 }}>
        <div className="search-bar-wrapper" style={{ flex: '0 0 280px' }}>
          <Search size={14} className="search-icon" />
          <input
            className="search-bar"
            placeholder="Search typesâ€¦"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="filter-select"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={{ height: 32, borderRadius: 6, border: '1px solid var(--color-border)', padding: '0 8px', fontSize: 13 }}
        >
          <option value="">All categories</option>
          {['SITE', 'EQUIPMENT', 'COMPONENT', 'TAG', 'EVENT_TYPE'].map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="loading-state">Loading asset typesâ€¦</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <Box size={40} color="var(--color-text-muted)" />
          <p>No asset types found. Create one to start.</p>
        </div>
      ) : (
        <div className="asset-table-wrap">
        <table className="data-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Slug</th>
              <th>Category</th>
              <th>Industry Tags</th>
              <th>Schema v</th>
              <th>Flags</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id}>
                <td style={{ fontWeight: 500 }}>{t.icon && <span style={{ marginRight: 6 }}>{t.icon}</span>}{t.name}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>{t.slug}</td>
                <td>
                  <span style={{
                    background: CATEGORY_COLORS[t.category] + '22',
                    color: CATEGORY_COLORS[t.category],
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 600,
                  }}>{t.category}</span>
                </td>
                <td style={{ fontSize: 12 }}>{t.industry_tags.join(', ') || 'â€”'}</td>
                <td style={{ textAlign: 'center' }}>{t.schema_version}</td>
                <td style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                  {t.is_root && <span style={{ marginRight: 4 }}>ROOT</span>}
                  {t.is_leaf && <span>LEAF</span>}
                </td>
                <td style={{ textAlign: 'right' }}>
                  <button
                    className="icon-btn"
                    onClick={() => navigate(`/assets/types/${t.id}/edit`)}
                    title="Edit"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    className="icon-btn danger"
                    onClick={() => setTypePendingDelete(t)}
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
      {typePendingDelete && (
        <ConfirmDialog
          title="Delete asset type"
          message={`Delete asset type "${typePendingDelete.name}"? This is only possible if no active asset instances use it.`}
          confirmLabel="Delete"
          onCancel={() => setTypePendingDelete(null)}
          onConfirm={() => handleDelete(typePendingDelete)}
          isLoading={deleteMutation.isPending}
        />
      )}
    </div>
  );
}

