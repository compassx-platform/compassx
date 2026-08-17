import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────────────

export type AssetCategory = 'SITE' | 'EQUIPMENT' | 'COMPONENT' | 'TAG' | 'EVENT_TYPE';
export type AssetStatus = 'ACTIVE' | 'INACTIVE' | 'DECOMMISSIONED' | 'PLANNED' | 'MAINTENANCE';
export type EventSeverity = 'INFO' | 'WARNING' | 'CRITICAL';
export type DocumentType = 'MANUAL' | 'CERTIFICATE' | 'DRAWING' | 'REPORT' | 'CONTRACT' | 'OTHER';
export type MetadataFieldType = 'STRING' | 'INTEGER' | 'FLOAT' | 'BOOLEAN' | 'DATETIME' | 'DATE' | 'ENUM' | 'URL' | 'EMAIL' | 'UOM';
export type RelationshipDirection = 'UNIDIRECTIONAL' | 'BIDIRECTIONAL';

export interface FieldValidation {
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  message?: string;
}

export interface MetadataField {
  key: string;
  label: string;
  type: MetadataFieldType;
  required: boolean;
  default?: unknown;
  unit?: string;
  enum_values?: string[];
  validation?: FieldValidation;
  group?: string;
  order: number;
  is_searchable: boolean;
  is_filterable: boolean;
  tooltip?: string;
}

export interface MetadataSchema {
  version: number;
  fields: MetadataField[];
}

export interface AssetTypeTag {
  id: number;
  asset_type_id: number;
  tag_key: string;
  name: string;
  description?: string;
  parameter?: string;
  unit?: string;
  is_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssetType {
  id: number;
  name: string;
  slug: string;
  category: AssetCategory;
  description?: string;
  industry_tags: string[];
  icon?: string;
  allowed_parents: number[];
  allowed_children: number[];
  metadata_schema: MetadataSchema;
  is_root: boolean;
  is_leaf: boolean;
  schema_version: number;
  tag_definitions: AssetTypeTag[];
  is_deleted?: boolean;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetTypeCreateRequest {
  name: string;
  slug: string;
  category: AssetCategory;
  description?: string;
  industry_tags?: string[];
  icon?: string;
  allowed_parents?: number[];
  allowed_children?: number[];
  metadata_schema?: MetadataSchema;
  is_root?: boolean;
  is_leaf?: boolean;
  tag_definitions?: Partial<AssetTypeTag>[];
}

function normalizeAssetType(type: AssetType): AssetType {
  return {
    ...type,
    industry_tags: Array.isArray(type.industry_tags) ? type.industry_tags : [],
    allowed_parents: Array.isArray(type.allowed_parents) ? type.allowed_parents : [],
    allowed_children: Array.isArray(type.allowed_children) ? type.allowed_children : [],
    metadata_schema: type.metadata_schema ?? { version: 1, fields: [] },
    tag_definitions: Array.isArray(type.tag_definitions) ? type.tag_definitions : [],
  };
}

export interface AssetInstance {
  id: number;
  asset_type_id: number;
  asset_type_name?: string;
  asset_type_slug?: string;
  parent_id?: number;
  name: string;
  code?: string;
  description?: string;
  status: AssetStatus;
  latitude?: number;
  longitude?: number;
  altitude?: number;
  address?: string;
  commissioned_at?: string;
  decommissioned_at?: string;
  metadata: Record<string, unknown>;
  metadata_schema_version: number;
  path: string;
  depth: number;
  created_at: string;
  updated_at: string;
  created_by?: string;
  updated_by?: string;
}

export interface HierarchyNode {
  id: number;
  name: string;
  code?: string;
  status: AssetStatus;
  asset_type_id: number;
  asset_type_name?: string;
  asset_type_slug?: string;
  icon?: string;
  path: string;
  depth: number;
  has_children: boolean;
  children?: HierarchyNode[];
}

export interface AssetVersion {
  id: number;
  asset_id: number;
  version: number;
  snapshot: Record<string, unknown>;
  change_summary?: string;
  changed_by?: string;
  changed_at: string;
}

export interface AssetEvent {
  id: number;
  asset_id: number;
  linked_assets: number[];
  event_type: string;
  title: string;
  description?: string;
  severity?: EventSeverity;
  started_at: string;
  ended_at?: string;
  metadata?: Record<string, unknown>;
  source?: string;
  external_ref?: string;
  created_by?: string;
  created_at: string;
}

export interface AssetTag {
  id: number;
  asset_id: number;
  asset_type_tag_id?: number;
  tag_id: string;
  tag_name: string;
  parameter?: string;
  unit?: string;
  source?: string;
  is_primary: boolean;
  created_at: string;
  asset_type_tag?: AssetTypeTag;
}

export interface AssetDocument {
  id: number;
  asset_id: number;
  title: string;
  type: DocumentType;
  url: string;
  mime_type?: string;
  file_size?: number;
  version?: string;
  uploaded_at: string;
  uploaded_by?: string;
}

export interface AssetRelationship {
  id: number;
  from_asset_id: number;
  to_asset_id: number;
  type: string;
  direction: RelationshipDirection;
  metadata?: Record<string, unknown>;
  description?: string;
  created_at: string;
  created_by?: string;
}

export interface PaginatedAssets {
  data: AssetInstance[];
  pagination: {
    cursor?: number;
    limit: number;
    total: number;
    has_more: boolean;
  };
}

// ── Asset Types ───────────────────────────────────────────────────────────────

export function useAssetTypes(params?: { industry_tag?: string; category?: string; include_deleted?: boolean }) {
  return useQuery({
    queryKey: ['asset-types', params],
    queryFn: async () => {
      const { data } = await api.get<AssetType[]>('/asset-types', { params });
      return data.map(normalizeAssetType);
    },
  });
}

export function useAssetType(id: number | undefined) {
  return useQuery({
    queryKey: ['asset-types', id],
    queryFn: async () => {
      const { data } = await api.get<AssetType>(`/asset-types/${id}`);
      return normalizeAssetType(data);
    },
    enabled: id !== undefined,
  });
}

export function useCreateAssetType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: AssetTypeCreateRequest) => {
      const { data } = await api.post<AssetType>('/asset-types', body);
      return normalizeAssetType(data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-types'] }),
  });
}

export function useUpdateAssetType(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<AssetType>) => {
      const { data } = await api.put<AssetType>(`/asset-types/${id}`, body);
      return normalizeAssetType(data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-types'] }),
  });
}

export function useUpdateAssetTypeById() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: Partial<AssetType> }) => {
      const { data } = await api.put<AssetType>(`/asset-types/${id}`, body);
      return normalizeAssetType(data);
    },
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ['asset-types'] });
      qc.invalidateQueries({ queryKey: ['asset-types', variables.id] });
    },
  });
}

export function useDeleteAssetType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/asset-types/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-types'] }),
  });
}

export function usePurgeDeletedAssets() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.delete<{ deleted: number }>('/asset-instances/deleted/permanent');
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-children'] });
      qc.invalidateQueries({ queryKey: ['asset-hierarchy'] });
    },
  });
}

export function usePurgeDeletedAssetTypes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.delete<{ deleted: number }>('/asset-types/deleted/permanent');
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-types'] }),
  });
}

export function useUpdateAssetTypeSchema(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (schema: MetadataSchema) => {
      const { data } = await api.put<AssetType>(`/asset-types/${id}/schema`, schema);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-types', id] }),
  });
}

export function useCreateAssetTypeTag(typeId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<AssetTypeTag, 'id' | 'asset_type_id' | 'created_at' | 'updated_at'>) => {
      const { data } = await api.post<AssetTypeTag>(`/asset-types/${typeId}/tags`, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-types'] });
      qc.invalidateQueries({ queryKey: ['asset-types', typeId] });
    },
  });
}

export function useDeleteAssetTypeTag(typeId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (tagDefId: number) => {
      await api.delete(`/asset-types/${typeId}/tags/${tagDefId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-types'] });
      qc.invalidateQueries({ queryKey: ['asset-types', typeId] });
    },
  });
}

// ── Asset Instances ───────────────────────────────────────────────────────────

export interface ListInstancesParams {
  q?: string;
  type_id?: number;
  status?: string[];
  parent_id?: number;
  path_prefix?: string;
  industry?: string;
  cursor?: number;
  limit?: number;
  sort?: string;
}

export function useAssetInstances(params?: ListInstancesParams) {
  return useQuery({
    queryKey: ['asset-instances', params],
    queryFn: async () => {
      const { data } = await api.get<PaginatedAssets>('/asset-instances', { params });
      return data;
    },
  });
}

export function useAssetInstance(id: number | undefined) {
  return useQuery({
    queryKey: ['asset-instances', id],
    queryFn: async () => {
      const { data } = await api.get<AssetInstance>(`/asset-instances/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

export function useCreateAssetInstance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<AssetInstance> & { asset_type_id: number; name: string }) => {
      const { data } = await api.post<AssetInstance>('/asset-instances', body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-children'] });
      qc.invalidateQueries({ queryKey: ['asset-hierarchy'] });
    },
  });
}

export function useUpdateAssetInstance(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<AssetInstance> & { change_summary?: string }) => {
      const { data } = await api.put<AssetInstance>(`/asset-instances/${id}`, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-hierarchy'] });
    },
  });
}

export function useUpdateAssetStatus(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { status: AssetStatus; change_summary?: string }) => {
      const { data } = await api.patch<AssetInstance>(`/asset-instances/${id}/status`, body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-instances'] }),
  });
}

export function useReparentAsset(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { parent_id?: number; change_summary?: string }) => {
      const { data } = await api.patch<AssetInstance>(`/asset-instances/${id}/parent`, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-hierarchy'] });
    },
  });
}

export function useDeleteAssetInstance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/asset-instances/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-children'] });
      qc.invalidateQueries({ queryKey: ['asset-hierarchy'] });
    },
  });
}

export function useAssetByPath(path: string | undefined) {
  return useQuery({
    queryKey: ['asset-by-path', path],
    queryFn: async () => {
      const { data } = await api.get<AssetInstance>(`/asset-instances/by-path/${path}`);
      return data;
    },
    enabled: Boolean(path),
  });
}

export function useAssetChildren(id: number | undefined, includeDeleted = false) {
  return useQuery({
    queryKey: ['asset-children', id, includeDeleted],
    queryFn: async () => {
      const { data } = await api.get<AssetInstance[]>(`/asset-instances/${id}/children`, {
        params: { include_deleted: includeDeleted },
      });
      return data;
    },
    enabled: id !== undefined,
  });
}

export function useAssetSubtree(id: number | undefined) {
  return useQuery({
    queryKey: ['asset-subtree', id],
    queryFn: async () => {
      const { data } = await api.get<AssetInstance[]>(`/asset-instances/${id}/subtree`);
      return data;
    },
    enabled: id !== undefined,
  });
}

export function useAssetAncestors(id: number | undefined) {
  return useQuery({
    queryKey: ['asset-ancestors', id],
    queryFn: async () => {
      const { data } = await api.get<AssetInstance[]>(`/asset-instances/${id}/ancestors`);
      return data;
    },
    enabled: id !== undefined,
  });
}

export function useAssetVersions(id: number | undefined) {
  return useQuery({
    queryKey: ['asset-versions', id],
    queryFn: async () => {
      const { data } = await api.get<AssetVersion[]>(`/asset-instances/${id}/versions`);
      return data;
    },
    enabled: id !== undefined,
  });
}

// ── Hierarchy ─────────────────────────────────────────────────────────────────

export function useHierarchyRoots(includeDeleted = false) {
  return useQuery({
    queryKey: ['asset-hierarchy', 'roots', includeDeleted],
    queryFn: async () => {
      const { data } = await api.get<HierarchyNode[]>('/asset-hierarchy/roots', {
        params: { include_deleted: includeDeleted },
      });
      return data;
    },
  });
}

export function useHierarchyTree(id: number | undefined, maxDepth = 3, includeDeleted = false) {
  return useQuery({
    queryKey: ['asset-hierarchy', 'tree', id, maxDepth, includeDeleted],
    queryFn: async () => {
      const { data } = await api.get<HierarchyNode>(`/asset-hierarchy/${id}/tree`, {
        params: { max_depth: maxDepth, include_deleted: includeDeleted },
      });
      return data;
    },
    enabled: id !== undefined,
  });
}

// ── Events ────────────────────────────────────────────────────────────────────

export function useAssetEvents(params?: {
  asset_id?: number;
  event_type?: string;
  severity?: string;
  started_after?: string;
  started_before?: string;
}) {
  return useQuery({
    queryKey: ['asset-events', params],
    queryFn: async () => {
      const { data } = await api.get<AssetEvent[]>('/asset-events', { params });
      return data;
    },
  });
}

export function useCreateAssetEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<AssetEvent> & { asset_id: number; title: string; event_type: string; started_at: string }) => {
      const { data } = await api.post<AssetEvent>('/asset-events', body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-events'] }),
  });
}

export function useDeleteAssetEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/asset-events/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-events'] }),
  });
}

// ── Asset Tags ─────────────────────────────────────────────────────────────────

export function useAssetTags(assetId?: number) {
  return useQuery({
    queryKey: ['asset-tags', assetId],
    queryFn: async () => {
      const params = assetId !== undefined ? { asset_id: assetId } : undefined;
      const { data } = await api.get<AssetTag[]>('/asset-tags', { params });
      return data;
    },
  });
}

export function useCreateAssetTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<AssetTag, 'id' | 'created_at'>) => {
      const { data } = await api.post<AssetTag>('/asset-tags', body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-tags'] });
    },
  });
}

export function useDeleteAssetTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/asset-tags/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-instances'] });
      qc.invalidateQueries({ queryKey: ['asset-tags'] });
    },
  });
}

// ── Relationships ─────────────────────────────────────────────────────────────

export function useAssetRelationships(params?: { from_asset_id?: number; to_asset_id?: number; type?: string }) {
  return useQuery({
    queryKey: ['asset-relationships', params],
    queryFn: async () => {
      const { data } = await api.get<AssetRelationship[]>('/asset-relationships', { params });
      return data;
    },
  });
}

export function useCreateRelationship() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<AssetRelationship, 'id' | 'created_at' | 'created_by'>) => {
      const { data } = await api.post<AssetRelationship>('/asset-relationships', body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-relationships'] }),
  });
}

export function useDeleteRelationship() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/asset-relationships/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-relationships'] }),
  });
}
