import { type ReactNode, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Box, GitBranch, ChevronRight, ChevronDown, Layers, Link2, MoreVertical, Pencil, Plus, Search, Settings, Tag, Trash2, Unlink, Upload, X } from 'lucide-react';
import {
  useHierarchyRoots,
  useAssetChildren,
  useAssetType,
  useDeleteAssetInstance,
  useAssetTypes,
  useUpdateAssetTypeById,
  useDeleteAssetType,
  usePurgeDeletedAssets,
  usePurgeDeletedAssetTypes,
  useCreateAssetTypeTag,
  useDeleteAssetTypeTag,
  type AssetType,
  type HierarchyNode,
  type AssetTypeTag,
} from '@/modules/asset_manager/hooks/useAssetManager';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import api from '@/lib/api';
import { SecondarySplitLayout } from '@/components/layout/SecondarySplitLayout';
import { PageTabs } from '@/components/common/PageTabs';
import ConfirmDialog from '@/components/common/ConfirmDialog';
import AssetDetailPage from './AssetDetailPage';
import AssetSearchPage from './AssetSearchPage';

type TreeMenuState = {
  node: HierarchyNode;
  x: number;
  y: number;
};

type TypeMenuState = {
  type: AssetType;
  x: number;
  y: number;
};

type ExplorerMode = 'assets' | 'asset-types';
type MainView = 'detail' | 'search' | 'types';
type AssetTypeDetailTab = 'details' | 'schema' | 'tags' | 'hierarchy';

const ASSET_TYPE_DETAIL_TABS = [
  { value: 'details' },
  { value: 'schema' },
  { value: 'tags' },
  { value: 'hierarchy' },
] as const satisfies readonly { value: AssetTypeDetailTab }[];

function TreeNode({
  node,
  level = 0,
  selectedId,
  includeDeleted,
  onOpenMenu,
}: {
  node: HierarchyNode;
  level?: number;
  selectedId?: number;
  includeDeleted: boolean;
  onOpenMenu: (node: HierarchyNode, x: number, y: number) => void;
}) {
  const navigate = useScopedNavigate();
  const [expanded, setExpanded] = useState(false);
  const { data: children, isLoading } = useAssetChildren(expanded && node.has_children ? node.id : undefined, includeDeleted);
  const isSelected = selectedId === node.id;
  const isDeleted = Boolean((node as HierarchyNode & { is_deleted?: boolean; deleted_at?: string | null }).is_deleted || (node as HierarchyNode & { deleted_at?: string | null }).deleted_at);
  const isDecommissioned = node.status === 'DECOMMISSIONED';

  return (
    <div>
      <div
        className={`tree-node-row asset-tree-row${isSelected ? ' is-selected' : ''}${isDeleted ? ' is-deleted' : ''}${isDecommissioned ? ' is-decommissioned' : ''}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          paddingLeft: level * 20 + 8,
          paddingRight: 8,
          cursor: 'pointer',
          borderRadius: 6,
          userSelect: 'none',
        }}
        onClick={() => navigate(`/assets/${node.id}`)}
        onContextMenu={(e) => {
          e.preventDefault();
          onOpenMenu(node, e.clientX, e.clientY);
        }}
      >
        <span
          className="asset-tree-toggle"
          onClick={(e) => {
            e.stopPropagation();
            if (node.has_children) setExpanded((v) => !v);
          }}
        >
          {node.has_children ? (
            expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />
          ) : (
            <span style={{ width: 13 }} />
          )}
        </span>
        <span style={{ display: 'inline-flex', width: 16, justifyContent: 'center', fontSize: 14 }}>
          {node.icon ?? <Box size={14} />}
        </span>
        <span className="asset-node-label" style={{ fontSize: 13, fontWeight: 500 }}>{node.name}</span>
        {node.code && <span className="asset-code">{node.code}</span>}
        <button
          className="icon-btn asset-tree-action"
          title="Asset actions"
          aria-label={`Actions for ${node.name}`}
          onClick={(e) => {
            e.stopPropagation();
            const rect = e.currentTarget.getBoundingClientRect();
            onOpenMenu(node, rect.right - 180, rect.bottom + 4);
          }}
        >
          <MoreVertical size={13} />
        </button>
      </div>
      {expanded && (
        <div>
          {isLoading && <div style={{ paddingLeft: (level + 1) * 20 + 8, fontSize: 12, color: 'var(--color-text-muted)' }}>Loading...</div>}
          {(children ?? []).map((child) => (
            <TreeNode
              key={child.id}
              node={{ ...child, has_children: true }}
              level={level + 1}
              selectedId={selectedId}
              includeDeleted={includeDeleted}
              onOpenMenu={onOpenMenu}
            />
          ))}
        </div>
      )}
    </div>
  );
}

type AssetTypeTreeNodeProps = {
  type: AssetType;
  typesById: Map<number, AssetType>;
  level?: number;
  selectedId?: number;
  seen?: Set<number>;
  onSelect: (type: AssetType) => void;
  onOpenMenu: (type: AssetType, x: number, y: number) => void;
};

function AssetTypeTreeNode({ type, typesById, level = 0, selectedId, seen = new Set(), onSelect, onOpenMenu }: AssetTypeTreeNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const nextSeen = new Set(seen).add(type.id);
  const children = type.allowed_children
    .map((id) => typesById.get(id))
    .filter((child): child is AssetType => child !== undefined && !nextSeen.has(child.id));
  const isSelected = selectedId === type.id;
  const isDeleted = Boolean(type.is_deleted || type.deleted_at);

  return (
    <div>
      <div
        className={`tree-node-row asset-tree-row${isSelected ? ' is-selected' : ''}${isDeleted ? ' is-deleted' : ''}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          paddingLeft: level * 20 + 8,
          paddingRight: 8,
          cursor: 'pointer',
          borderRadius: 6,
          userSelect: 'none',
        }}
        onClick={() => onSelect(type)}
        onContextMenu={(event) => {
          event.preventDefault();
          onOpenMenu(type, event.clientX, event.clientY);
        }}
      >
        <span
          className="asset-tree-toggle"
          onClick={(event) => {
            event.stopPropagation();
            if (children.length > 0) setExpanded((value) => !value);
          }}
        >
          {children.length > 0 ? expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} /> : <span style={{ width: 13 }} />}
        </span>
        <span style={{ display: 'inline-flex', width: 16, justifyContent: 'center', fontSize: 14 }}>
          {type.icon ?? <Box size={14} />}
        </span>
        <span className="asset-node-label" style={{ fontSize: 13, fontWeight: 600 }}>{type.name}</span>
        {type.is_root && <span className="asset-pill">ROOT</span>}
        {type.is_leaf && <span className="asset-pill">LEAF</span>}
        <button
          className="icon-btn asset-tree-action"
          title="Asset type actions"
          aria-label={`Actions for ${type.name}`}
          onClick={(event) => {
            event.stopPropagation();
            const rect = event.currentTarget.getBoundingClientRect();
            onOpenMenu(type, rect.right - 180, rect.bottom + 4);
          }}
        >
          <MoreVertical size={13} />
        </button>
      </div>
      {expanded && children.map((child) => (
        <AssetTypeTreeNode
          key={`${type.id}-${child.id}`}
          type={child}
          typesById={typesById}
          level={level + 1}
          selectedId={selectedId}
          seen={nextSeen}
          onSelect={onSelect}
          onOpenMenu={onOpenMenu}
        />
      ))}
    </div>
  );
}

// â”€â”€ Inline Add Tag Definition Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AddTagDefForm({
  typeId,
  onDone,
}: {
  typeId: number;
  onDone: () => void;
}) {
  const toast = useToast();
  const createTagDef = useCreateAssetTypeTag(typeId);
  const [tagKey, setTagKey] = useState('');
  const [name, setName] = useState('');
  const [parameter, setParameter] = useState('');
  const [unit, setUnit] = useState('');
  const [description, setDescription] = useState('');
  const [isRequired, setIsRequired] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tagKey.trim() || !name.trim()) return;
    try {
      await createTagDef.mutateAsync({
        tag_key: tagKey.trim(),
        name: name.trim(),
        parameter: parameter.trim() || undefined,
        unit: unit.trim() || undefined,
        description: description.trim() || undefined,
        is_required: isRequired,
      });
      toast.success('Tag definition created');
      onDone();
    } catch {
      toast.error('Failed to create tag definition');
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>New Tag Definition</span>
        <button type="button" className="icon-btn" onClick={onDone}><X size={14} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <label className="form-label">Tag Key *</label>
          <input className="form-input" placeholder="e.g. active_power" value={tagKey} onChange={e => setTagKey(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Display Name *</label>
          <input className="form-input" placeholder="e.g. Active Power" value={name} onChange={e => setName(e.target.value)} required />
        </div>
        <div>
          <label className="form-label">Parameter</label>
          <input className="form-input" placeholder="e.g. Active Power" value={parameter} onChange={e => setParameter(e.target.value)} />
        </div>
        <div>
          <label className="form-label">Unit</label>
          <input className="form-input" placeholder="e.g. kW" value={unit} onChange={e => setUnit(e.target.value)} />
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <label className="form-label">Description</label>
          <input className="form-input" placeholder="e.g. Inverter active power output" value={description} onChange={e => setDescription(e.target.value)} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 10 }}>
          <input type="checkbox" id="is-required" checked={isRequired} onChange={e => setIsRequired(e.target.checked)} />
          <label htmlFor="is-required" style={{ fontSize: 13 }}>Required</label>
        </div>
      </div>
      <button className="btn btn-primary" type="submit" disabled={createTagDef.isPending}>
        {createTagDef.isPending ? 'Savingâ€¦' : 'Add Tag Definition'}
      </button>
    </form>
  );
}

// â”€â”€ Asset Type Detail Panel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AssetTypeDetailPanel({
  selectedType,
  selectedTypeChildren,
  availableChildren,
  childTypeId,
  setChildTypeId,
  onAddChild,
  onRemoveChild,
  headerActions,
}: {
  selectedType: AssetType;
  selectedTypeChildren: AssetType[];
  availableChildren: AssetType[];
  childTypeId: string;
  setChildTypeId: (value: string) => void;
  onAddChild: () => void;
  onRemoveChild: (child: AssetType) => void;
  headerActions?: ReactNode;
}) {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const [tab, setTab] = useState<AssetTypeDetailTab>('details');
  const [menuOpen, setMenuOpen] = useState(false);
  const [showAddTagDef, setShowAddTagDef] = useState(false);
  const [tagDefPendingDelete, setTagDefPendingDelete] = useState<AssetTypeTag | null>(null);

  const schemaFields = selectedType.metadata_schema?.fields ?? [];
  const deleteTagDef = useDeleteAssetTypeTag(selectedType.id);

  async function handleDeleteTagDef(tagDef: AssetTypeTag) {
    try {
      await deleteTagDef.mutateAsync(tagDef.id);
      toast.success('Tag definition removed');
      setTagDefPendingDelete(null);
    } catch {
      toast.error('Failed to remove tag definition');
    }
  }

  return (
    <div>
      <div className="asset-detail-breadcrumb">
        <span>Asset Types</span>
        <span>/</span>
        <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>{selectedType.name}</span>
      </div>

      <div className="db-page-header">
        <div className="asset-detail-title-row">
          <h1 className="db-page-title" style={{ margin: 0 }}>{selectedType.name}</h1>
          <span style={{ fontSize: 12, background: 'var(--color-bg)', border: '1px solid var(--color-border)', padding: '2px 8px', borderRadius: 4 }}>{selectedType.category}</span>
          {selectedType.is_root && <span className="asset-pill">ROOT</span>}
          {selectedType.is_leaf && <span className="asset-pill">LEAF</span>}
        </div>
        <div className="asset-page-actions" style={{ position: 'relative' }}>
          <button className="icon-btn" onClick={() => setMenuOpen((open) => !open)} title="Asset type actions">
            <MoreVertical size={16} />
          </button>
          {headerActions}
          {menuOpen && (
            <div className="asset-inline-menu">
              <button
                onClick={() => {
                  setMenuOpen(false);
                  navigate(`/assets/types/${selectedType.id}/edit`);
                }}
              >
                <Pencil size={14} /> Edit
              </button>
            </div>
          )}
        </div>
      </div>

      <PageTabs tabs={ASSET_TYPE_DETAIL_TABS} value={tab} onChange={setTab} />

      {tab === 'details' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <section style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600 }}>Core Info</h3>
            <table style={{ width: '100%', fontSize: 13 }}>
              <tbody>
                {[
                  ['Slug', selectedType.slug],
                  ['Category', selectedType.category],
                  ['Description', selectedType.description ?? '-'],
                  ['Schema version', String(selectedType.schema_version)],
                  ['Icon', selectedType.icon ?? '-'],
                ].map(([key, value]) => (
                  <tr key={key}>
                    <td style={{ color: 'var(--color-text-muted)', paddingBottom: 6, paddingRight: 12, whiteSpace: 'nowrap' }}>{key}</td>
                    <td style={{ paddingBottom: 6, wordBreak: 'break-all' }}>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600 }}>Classification</h3>
            <table style={{ width: '100%', fontSize: 13 }}>
              <tbody>
                <tr>
                  <td style={{ color: 'var(--color-text-muted)', paddingBottom: 6, paddingRight: 12 }}>Industry tags</td>
                  <td style={{ paddingBottom: 6 }}>{selectedType.industry_tags.join(', ') || '-'}</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--color-text-muted)', paddingBottom: 6, paddingRight: 12 }}>Root type</td>
                  <td style={{ paddingBottom: 6 }}>{selectedType.is_root ? 'Yes' : 'No'}</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--color-text-muted)', paddingBottom: 6, paddingRight: 12 }}>Leaf type</td>
                  <td style={{ paddingBottom: 6 }}>{selectedType.is_leaf ? 'Yes' : 'No'}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>
      )}

      {tab === 'schema' && (
        schemaFields.length === 0 ? (
          <div className="empty-state" style={{ minHeight: 160 }}>
            <Box size={32} color="var(--color-text-muted)" />
            <p>No metadata schema fields are configured for this type.</p>
          </div>
        ) : (
          <div className="asset-table-wrap">
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Label</th>
                  <th>Type</th>
                  <th>Unit</th>
                  <th>Required</th>
                </tr>
              </thead>
              <tbody>
                {schemaFields.map((field) => (
                  <tr key={field.key}>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{field.key}</td>
                    <td>{field.label}</td>
                    <td>{field.type}</td>
                    <td>{field.unit ?? '-'}</td>
                    <td>{field.required ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === 'tags' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            {!showAddTagDef && (
              <button className="btn btn-primary" onClick={() => setShowAddTagDef(true)}>
                <Plus size={13} /> Add Tag Definition
              </button>
            )}
          </div>
          {showAddTagDef && (
            <AddTagDefForm typeId={selectedType.id} onDone={() => setShowAddTagDef(false)} />
          )}
          
          {(selectedType.tag_definitions ?? []).length === 0 && !showAddTagDef ? (
            <div className="empty-state" style={{ minHeight: 160 }}>
              <Tag size={32} color="var(--color-text-muted)" />
              <p>No tag definitions are configured for this type. Add one to get started.</p>
            </div>
          ) : (
            <div className="asset-table-wrap">
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Tag Key</th>
                    <th>Display Name</th>
                    <th>Parameter</th>
                    <th>Unit</th>
                    <th>Description</th>
                    <th>Required</th>
                    <th style={{ width: 50 }} />
                  </tr>
                </thead>
                <tbody>
                  {(selectedType.tag_definitions ?? []).map((t) => (
                    <tr key={t.id ?? t.tag_key}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{t.tag_key}</td>
                      <td style={{ fontWeight: 500 }}>{t.name}</td>
                      <td>{t.parameter ?? '-'}</td>
                      <td>{t.unit ?? '-'}</td>
                      <td>{t.description ?? '-'}</td>
                      <td>{t.is_required ? 'Yes' : 'No'}</td>
                      <td>
                        <button className="icon-btn danger" onClick={() => setTagDefPendingDelete(t)} title="Remove">
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tagDefPendingDelete && (
            <ConfirmDialog
              title="Remove Tag Definition"
              message={`Remove tag definition "${tagDefPendingDelete.name}" (${tagDefPendingDelete.tag_key})?`}
              confirmLabel="Remove"
              onCancel={() => setTagDefPendingDelete(null)}
              onConfirm={() => handleDeleteTagDef(tagDefPendingDelete)}
              isLoading={deleteTagDef.isPending}
            />
          )}
        </div>
      )}

      {tab === 'hierarchy' && (
        <>
          <div className="asset-filter-row" style={{ marginBottom: 16 }}>
            <select
              className="form-input"
              value={childTypeId}
              onChange={(event) => setChildTypeId(event.target.value)}
              disabled={selectedType.is_leaf}
              style={{ maxWidth: 340 }}
            >
              <option value="">Select child type...</option>
              {availableChildren.map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={onAddChild} disabled={!childTypeId || selectedType.is_leaf}>
              <Link2 size={14} /> Add Child Type
            </button>
          </div>

          {selectedType.is_leaf && (
            <p style={{ margin: '0 0 16px', color: 'var(--color-text-muted)', fontSize: 13 }}>
              Leaf types cannot have child types.
            </p>
          )}

          {selectedTypeChildren.length === 0 ? (
            <div className="empty-state" style={{ minHeight: 160 }}>
              <Box size={32} color="var(--color-text-muted)" />
              <p>No child types are configured below this type.</p>
            </div>
          ) : (
            <div className="asset-table-wrap">
              <table className="data-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>Child Type</th>
                    <th>Category</th>
                    <th>Slug</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTypeChildren.map((child) => (
                    <tr key={child.id}>
                      <td style={{ fontWeight: 600 }}>{child.icon && <span style={{ marginRight: 6 }}>{child.icon}</span>}{child.name}</td>
                      <td>{child.category}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>{child.slug}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="icon-btn danger" onClick={() => onRemoveChild(child)} title="Remove from hierarchy">
                          <Unlink size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

type AssetExplorerPageProps = {
  view?: MainView;
};

export default function AssetExplorerPage({ view = 'detail' }: AssetExplorerPageProps = {}) {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const { instanceId } = useParams<{ instanceId: string }>();
  const deleteAsset = useDeleteAssetInstance();
  const deleteType = useDeleteAssetType();
  const purgeAssets = usePurgeDeletedAssets();
  const purgeTypes = usePurgeDeletedAssetTypes();
  const updateType = useUpdateAssetTypeById();
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [includeDeletedTypes, setIncludeDeletedTypes] = useState(false);
  const { data: types, isLoading: isLoadingTypes } = useAssetTypes({ include_deleted: includeDeletedTypes });
  const [mode, setMode] = useState<ExplorerMode>(view === 'types' ? 'asset-types' : 'assets');
  const [search, setSearch] = useState('');
  const [sidebarMenuOpen, setSidebarMenuOpen] = useState(false);
  const { data: roots, isLoading } = useHierarchyRoots(includeDeleted);
  const [treeMenu, setTreeMenu] = useState<TreeMenuState | null>(null);
  const [typeMenu, setTypeMenu] = useState<TypeMenuState | null>(null);
  const [assetPendingDelete, setAssetPendingDelete] = useState<HierarchyNode | null>(null);
  const [typePendingDelete, setTypePendingDelete] = useState<AssetType | null>(null);
  const [purgeTarget, setPurgeTarget] = useState<ExplorerMode | null>(null);
  const [selectedTypeId, setSelectedTypeId] = useState<number | undefined>();
  const [childTypeId, setChildTypeId] = useState('');
  const selectedId = instanceId ? Number(instanceId) : undefined;
  const rootCount = roots?.length ?? 0;
  const mainView = view;
  const { data: selectedTypeDetail } = useAssetType(selectedTypeId);
  const selectedType = selectedTypeDetail ?? types?.find((type) => type.id === selectedTypeId);
  const typesById = new Map((types ?? []).map((type) => [type.id, type]));
  const typeRoots = (() => {
    const childIds = new Set((types ?? []).flatMap((type) => type.allowed_children));
    return (types ?? []).filter((type) => type.is_root || (!childIds.has(type.id) && type.allowed_parents.length === 0));
  })();

  useEffect(() => {
    if (!treeMenu && !typeMenu) return;
    const close = () => {
      setTreeMenu(null);
      setTypeMenu(null);
    };
    window.addEventListener('click', close);
    window.addEventListener('scroll', close, true);
    return () => {
      window.removeEventListener('click', close);
      window.removeEventListener('scroll', close, true);
    };
  }, [treeMenu, typeMenu]);

  useEffect(() => {
    if (!sidebarMenuOpen) return;
    const close = () => setSidebarMenuOpen(false);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [sidebarMenuOpen]);

  const filteredRoots = (roots ?? []).filter(
    (r) => !search.trim() || r.name.toLowerCase().includes(search.toLowerCase())
  );

  const filteredTypeRoots = typeRoots.filter(
    (type) => !search.trim() || type.name.toLowerCase().includes(search.toLowerCase()) || type.slug.toLowerCase().includes(search.toLowerCase())
  );

  function hasDescendant(root: AssetType, targetId: number, seen = new Set<number>()): boolean {
    if (seen.has(root.id)) return false;
    seen.add(root.id);
    return root.allowed_children.some((id) => {
      if (id === targetId) return true;
      const child = typesById.get(id);
      return child ? hasDescendant(child, targetId, seen) : false;
    });
  }

  const availableChildren = (types ?? []).filter((type) => {
    if (!selectedType || type.id === selectedType.id) return false;
    if (selectedType.allowed_children.includes(type.id)) return false;
    if (hasDescendant(type, selectedType.id)) return false;
    return true;
  });

  const selectedTypeChildren = selectedType
    ? selectedType.allowed_children.map((id) => typesById.get(id)).filter(Boolean) as AssetType[]
    : [];

  async function addChildType() {
    if (!selectedType || !childTypeId) return;
    const childType = typesById.get(Number(childTypeId));
    if (!childType) return;
    try {
      await updateType.mutateAsync({
        id: selectedType.id,
        body: { allowed_children: Array.from(new Set([...selectedType.allowed_children, childType.id])) },
      });
      await updateType.mutateAsync({
        id: childType.id,
        body: { allowed_parents: [selectedType.id], is_root: false },
      });
      setChildTypeId('');
      toast.success(`Added ${childType.name} under ${selectedType.name}`);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update hierarchy';
      toast.error(msg);
    }
  }

  async function removeChildType(child: AssetType) {
    if (!selectedType) return;
    try {
      await updateType.mutateAsync({
        id: selectedType.id,
        body: { allowed_children: selectedType.allowed_children.filter((id) => id !== child.id) },
      });
      await updateType.mutateAsync({
        id: child.id,
        body: { allowed_parents: child.allowed_parents.filter((id) => id !== selectedType.id) },
      });
      toast.success(`Removed ${child.name} from ${selectedType.name}`);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update hierarchy';
      toast.error(msg);
    }
  }

  async function handleDeleteAsset(node: HierarchyNode) {
    try {
      await deleteAsset.mutateAsync(node.id);
      toast.success('Asset deleted');
      setTreeMenu(null);
      setAssetPendingDelete(null);
      if (selectedId === node.id) navigate('/assets');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Delete failed';
      setAssetPendingDelete(null);
      toast.error(msg);
    }
  }

  async function handleDeleteType(type: AssetType) {
    try {
      await deleteType.mutateAsync(type.id);
      toast.success('Asset type deleted');
      setTypePendingDelete(null);
      if (selectedTypeId === type.id) setSelectedTypeId(undefined);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Delete failed';
      setTypePendingDelete(null);
      toast.error(msg);
    }
  }

  async function handlePurgeDeleted(target: ExplorerMode) {
    try {
      const result = target === 'assets'
        ? await purgeAssets.mutateAsync()
        : await purgeTypes.mutateAsync();
      toast.success(`Permanently deleted ${result.deleted} ${target === 'assets' ? 'asset' : 'asset type'}${result.deleted === 1 ? '' : 's'}`);
      setPurgeTarget(null);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Permanent delete failed';
      setTypePendingDelete(null);
      toast.error(msg);
    }
  }

  async function requestDeleteAsset(node: HierarchyNode) {
    try {
      const { data: children } = await api.get(`/asset-instances/${node.id}/children`);
      setAssetPendingDelete({ ...node, has_children: Array.isArray(children) && children.length > 0 });
      setTreeMenu(null);
    } catch {
      setAssetPendingDelete(node);
      setTreeMenu(null);
    }
  }

  const assetWorkspaceActions = (
    <>
      {mainView === 'search' ? (
        <button className="btn btn-secondary" onClick={() => navigate('/assets')}>
          <GitBranch size={14} /> Details
        </button>
      ) : (
        <button className="btn btn-secondary" onClick={() => navigate('/assets/search')}>
          <Search size={14} /> Search
        </button>
      )}
      <button className="btn btn-secondary" onClick={() => navigate('/assets/import')}>
        <Upload size={14} /> Bulk Upload
      </button>
      <button className="btn btn-primary" onClick={() => navigate('/assets/new')}>
        <Plus size={14} /> New Asset
      </button>
    </>
  );

  const typeWorkspaceActions = (
    <>
      {mainView === 'types' ? (
        <button className="btn btn-secondary" onClick={() => navigate('/assets')}>
          <GitBranch size={14} /> Hierarchy
        </button>
      ) : (
        <button className="btn btn-secondary" onClick={() => navigate('/assets/types')}>
          <Layers size={14} /> Manage Types
        </button>
      )}
      <button className="btn btn-primary" onClick={() => navigate('/assets/types/new')}>
        <Plus size={14} /> New Type
      </button>
    </>
  );

  const showSplitHeader = !(
    (mode === 'assets' && mainView === 'detail' && selectedId) ||
    (mode === 'asset-types' && selectedType)
  );

  return (
    <div className="page-section asset-page" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <SecondarySplitLayout
        className="asset-workspace"
        storageKey="asset-explorer-sidebar-width-v3"
        sidebarHeader={
          <>
            <div className="asset-page-title">
              <div>
                <h1 className="db-page-title">Asset Explorer</h1>
                <div className="asset-summary-bar">
                  {mode === 'assets' ? (
                    <>
                      <span>{rootCount} root asset{rootCount === 1 ? '' : 's'}</span>
                      {selectedId && <span>Selected #{selectedId}</span>}
                    </>
                  ) : (
                    <>
                      <span>{types?.length ?? 0} type{types?.length === 1 ? '' : 's'}</span>
                      <span>{typeRoots.length} root type{typeRoots.length === 1 ? '' : 's'}</span>
                    </>
                  )}
                </div>
              </div>
              <div style={{ position: 'relative', marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
                <button
                  className="icon-btn"
                  title="Explorer settings"
                  aria-label="Explorer settings"
                  onClick={(event) => {
                    event.stopPropagation();
                    setSidebarMenuOpen((open) => !open);
                  }}
                >
                  <Settings size={14} />
                </button>
                <button
                  className="icon-btn"
                  title={mode === 'assets' ? 'Add asset' : 'Add asset type'}
                  aria-label={mode === 'assets' ? 'Add asset' : 'Add asset type'}
                  onClick={() => navigate(mode === 'assets' ? '/assets/import' : '/assets/types/new')}
                >
                  <Plus size={14} />
                </button>
                {sidebarMenuOpen && (
                  <div className="asset-inline-menu asset-settings-menu" onClick={(event) => event.stopPropagation()}>
                    <label className="asset-menu-check">
                      <input
                        className="asset-checkbox"
                        type="checkbox"
                        checked={mode === 'assets' ? includeDeleted : includeDeletedTypes}
                        onChange={(event) => {
                          if (mode === 'assets') setIncludeDeleted(event.target.checked);
                          else setIncludeDeletedTypes(event.target.checked);
                        }}
                      />
                      {mode === 'assets' ? 'Show deleted assets' : 'Show deleted asset types'}
                    </label>
                    <button
                      className="danger"
                      onClick={() => {
                        setSidebarMenuOpen(false);
                        setPurgeTarget(mode);
                      }}
                    >
                      <Trash2 size={14} /> Permanently delete deleted {mode === 'assets' ? 'assets' : 'types'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </>
        }
        sidebar={
          <>
            <div className="asset-sidebar-tabs">
              <button className={mode === 'assets' ? 'is-active' : ''} onClick={() => setMode('assets')}>
                Assets
              </button>
              <button className={mode === 'asset-types' ? 'is-active' : ''} onClick={() => setMode('asset-types')}>
                Asset Types
              </button>
            </div>
            <div className="asset-panel-toolbar">
              <div className="search-bar-wrapper" style={{ flex: 1 }}>
                <Search size={14} className="search-icon" />
                <input
                  className="search-bar"
                  placeholder={mode === 'assets' ? 'Filter root assets...' : 'Filter asset types...'}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
            <div className="asset-tree-scroll">
              {mode === 'assets' ? (
                isLoading ? (
                  <div className="loading-state">Loading hierarchy...</div>
                ) : filteredRoots.length === 0 ? (
                  <div className="empty-state asset-empty">
                    <GitBranch size={36} color="var(--color-text-muted)" />
                    <p>No assets yet. Create one to start building the hierarchy.</p>
                  </div>
                ) : (
                  filteredRoots.map((root) => (
                    <TreeNode
                      key={root.id}
                      node={root}
                      selectedId={selectedId}
                      includeDeleted={includeDeleted}
                      onOpenMenu={(node, x, y) => setTreeMenu({ node, x, y })}
                    />
                  ))
                )
              ) : (
                isLoadingTypes ? (
                  <div className="loading-state">Loading type hierarchy...</div>
                ) : filteredTypeRoots.length === 0 ? (
                  <div className="empty-state asset-empty">
                    <GitBranch size={36} color="var(--color-text-muted)" />
                    <p>No root asset types yet. Create a type or mark one as root.</p>
                  </div>
                ) : (
                  filteredTypeRoots.map((root) => (
                    <AssetTypeTreeNode
                      key={root.id}
                      type={root}
                      typesById={typesById}
                      selectedId={selectedTypeId}
                      onSelect={(type) => setSelectedTypeId(type.id)}
                      onOpenMenu={(type, x, y) => setTypeMenu({ type, x, y })}
                    />
                  ))
                )
              )}
            </div>
          </>
        }
        mainHeader={showSplitHeader ? (
          <>
            <div />
            <div className="asset-page-actions">
              {mode === 'assets' ? assetWorkspaceActions : typeWorkspaceActions}
            </div>
          </>
        ) : undefined}
      >
        <div className="asset-detail-scroll">
          {mainView === 'search' ? (
            <AssetSearchPage embedded />
          ) : mode === 'assets' ? selectedId ? (
            <AssetDetailPage assetId={selectedId} embedded headerActions={assetWorkspaceActions} />
          ) : (
            <div className="empty-state asset-empty">
              <GitBranch size={36} color="var(--color-text-muted)" />
              <p>Select an asset from the hierarchy to view details.</p>
            </div>
          ) : !selectedType ? (
            <div className="empty-state asset-empty">
              <GitBranch size={36} color="var(--color-text-muted)" />
              <p>Select an asset type to view and manage its hierarchy.</p>
            </div>
          ) : (
            <AssetTypeDetailPanel
              selectedType={selectedType}
              selectedTypeChildren={selectedTypeChildren}
              availableChildren={availableChildren}
              childTypeId={childTypeId}
              setChildTypeId={setChildTypeId}
              onAddChild={addChildType}
              onRemoveChild={removeChildType}
              headerActions={typeWorkspaceActions}
            />
          )}
        </div>
      </SecondarySplitLayout>
      {treeMenu && (
        <div
          className="asset-context-menu"
          style={{ left: treeMenu.x, top: treeMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => {
              navigate(`/assets/${treeMenu.node.id}`);
              setTreeMenu(null);
            }}
          >
            <GitBranch size={14} /> View details
          </button>
          <button
            onClick={() => {
              navigate(`/assets/new?parentId=${treeMenu.node.id}`);
              setTreeMenu(null);
            }}
          >
            <Plus size={14} /> Add child
          </button>
          <button
            onClick={() => {
              navigate(`/assets/${treeMenu.node.id}/edit`);
              setTreeMenu(null);
            }}
          >
            <Pencil size={14} /> Edit asset
          </button>
          <button
            onClick={() => {
              requestDeleteAsset(treeMenu.node);
            }}
          >
            <Trash2 size={14} /> Delete asset
          </button>
        </div>
      )}
      {typeMenu && (
        <div
          className="asset-context-menu"
          style={{ left: typeMenu.x, top: typeMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => {
              setSelectedTypeId(typeMenu.type.id);
              setTypeMenu(null);
            }}
          >
            <Layers size={14} /> View details
          </button>
          <button
            onClick={() => {
              navigate(`/assets/types/new?parentTypeId=${typeMenu.type.id}`);
              setTypeMenu(null);
            }}
          >
            <Plus size={14} /> Add child type
          </button>
          <button
            onClick={() => {
              navigate(`/assets/types/${typeMenu.type.id}/edit`);
              setTypeMenu(null);
            }}
          >
            <Pencil size={14} /> Edit type
          </button>
          <button
            onClick={() => {
              setTypePendingDelete(typeMenu.type);
              setTypeMenu(null);
            }}
          >
            <Trash2 size={14} /> Delete type
          </button>
        </div>
      )}
      {assetPendingDelete && (
        <ConfirmDialog
          title={assetPendingDelete.has_children ? "Cannot delete asset" : "Delete asset"}
          message={
            assetPendingDelete.has_children
              ? `"${assetPendingDelete.name}" has child assets. Move or delete its child assets first, then try again.`
              : `Delete "${assetPendingDelete.name}"? This action cannot be undone.`
          }
          confirmLabel="Delete"
          onCancel={() => setAssetPendingDelete(null)}
          onConfirm={() => handleDeleteAsset(assetPendingDelete)}
          isLoading={deleteAsset.isPending}
          hideConfirm={assetPendingDelete.has_children}
        />
      )}
      {typePendingDelete && (
        <ConfirmDialog
          title="Delete asset type"
          message={`Delete "${typePendingDelete.name}"? This soft deletes the asset type and is only allowed when it has no active asset instances.`}
          confirmLabel="Delete"
          onCancel={() => setTypePendingDelete(null)}
          onConfirm={() => handleDeleteType(typePendingDelete)}
          isLoading={deleteType.isPending}
        />
      )}
      {purgeTarget && (
        <ConfirmDialog
          title="Permanently delete deleted items"
          message={`This will permanently remove deleted ${purgeTarget === 'assets' ? 'assets' : 'asset types'} that are safe to purge. This cannot be undone.`}
          confirmLabel="Permanently delete"
          onCancel={() => setPurgeTarget(null)}
          onConfirm={() => handlePurgeDeleted(purgeTarget)}
          isLoading={purgeAssets.isPending || purgeTypes.isPending}
        />
      )}
    </div>
  );
}

