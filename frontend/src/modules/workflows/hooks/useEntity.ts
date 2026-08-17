import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type {
  EntityDefinition,
  EntityDefinitionCreate,
  EntityField,
} from '@/types';

// Re-export types for convenience
export type { EntityDefinition, EntityField };

export interface EntityRecord {
  id: number;
  entity_id: number;
  asset_id: string;
  timestamp: string;
  status: string;
  data_json: Record<string, any>;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// ── Entity definitions ────────────────────────────────────────────────────────

export function useEntityDefinitions() {
  return useQuery({
    queryKey: ['entityDefinitions'],
    queryFn: async () => {
      const { data } = await api.get<EntityDefinition[]>('/entities');
      return data;
    },
  });
}

export function useEntityDefinition(entityName: string) {
  return useQuery({
    queryKey: ['entityDefinition', entityName],
    queryFn: async () => {
      const { data } = await api.get<EntityDefinition>(`/entities/${entityName}`);
      return data;
    },
    enabled: Boolean(entityName),
  });
}

export function useCreateEntityDefinition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: EntityDefinitionCreate) => {
      const { data } = await api.post<EntityDefinition>('/entities', payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entityDefinitions'] });
    },
  });
}

export interface EntityDefinitionUpdatePayload {
  entity_type?: string;
  asset_scoped?: boolean;
  time_based?: boolean;
  time_series?: boolean;
}

export function useUpdateEntityDefinition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      entityName,
      payload,
    }: {
      entityName: string;
      payload: EntityDefinitionUpdatePayload;
    }) => {
      const { data } = await api.patch<EntityDefinition>(`/entities/${entityName}`, payload);
      return data;
    },
    onSuccess: (_data, { entityName }) => {
      qc.invalidateQueries({ queryKey: ['entityDefinitions'] });
      qc.invalidateQueries({ queryKey: ['entityDefinition', entityName] });
    },
  });
}

// ── Entity fields ─────────────────────────────────────────────────────────────

export function useEntityFields(entityName: string) {
  return useQuery({
    queryKey: ['entityFields', entityName],
    queryFn: async () => {
      const { data } = await api.get<EntityField[]>(`/entities/${entityName}/fields`);
      return data;
    },
    enabled: Boolean(entityName),
  });
}

export interface EntityFieldCreatePayload {
  field_name: string;
  field_type: string;
  is_required?: boolean;
  is_indexed?: boolean;
  field_source?: string;
  is_system?: boolean;
  system_generated?: boolean;
  default_value?: string | null;
}

export interface EntityFieldUpdatePayload {
  new_field_name?: string;
  field_type?: string;
  is_required?: boolean;
  is_indexed?: boolean;
  default_value?: string | null;
  system_generated?: boolean;
}

export function useAddEntityField(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: EntityFieldCreatePayload) => {
      const { data } = await api.post<EntityField>(
        `/entities/${entityName}/fields`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entityFields', entityName] });
      qc.invalidateQueries({ queryKey: ['entityDefinition', entityName] });
      qc.invalidateQueries({ queryKey: ['entityDefinitions'] });
    },
  });
}

export function useUpdateEntityField(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      fieldName,
      payload,
    }: {
      fieldName: string;
      payload: EntityFieldUpdatePayload;
    }) => {
      const { data } = await api.patch<EntityField>(
        `/entities/${entityName}/fields/${fieldName}`,
        payload,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entityFields', entityName] });
      qc.invalidateQueries({ queryKey: ['entityDefinition', entityName] });
    },
  });
}

export function useDeleteEntityField(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (fieldName: string) => {
      const { data } = await api.delete(
        `/entities/${entityName}/fields/${fieldName}`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entityFields', entityName] });
      qc.invalidateQueries({ queryKey: ['entityDefinition', entityName] });
    },
  });
}

// ── Projection ────────────────────────────────────────────────────────────────

export interface ProjectionStatus {
  entity_name: string;
  enabled: boolean;
  table: string | null;
  records_synced?: number;
}

export function useProjectionStatus(entityName: string) {
  return useQuery({
    queryKey: ['projectionStatus', entityName],
    queryFn: async () => {
      const { data } = await api.get<ProjectionStatus>(`/entities/${entityName}/projection`);
      return data;
    },
    enabled: Boolean(entityName),
  });
}

export function useEnableProjection(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<ProjectionStatus>(`/entities/${entityName}/projection`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projectionStatus', entityName] });
    },
  });
}

export function useSyncProjectionSchema(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/entities/${entityName}/projection/sync-schema`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projectionStatus', entityName] });
    },
  });
}

export interface OrphanedColumnsResponse {
  entity_name: string;
  orphaned_columns: string[];
}

export function useOrphanedProjectionColumns(entityName: string) {
  return useQuery({
    queryKey: ['orphanedProjectionColumns', entityName],
    queryFn: async () => {
      const { data } = await api.get<OrphanedColumnsResponse>(
        `/entities/${entityName}/projection/orphaned-columns`,
      );
      return data;
    },
    enabled: Boolean(entityName),
  });
}

export function useDropProjectionColumns(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (columns: string[]) => {
      const { data } = await api.delete(
        `/entities/${entityName}/projection/columns`,
        { data: { columns } },
      );
      return data as { dropped: string[]; message: string };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orphanedProjectionColumns', entityName] });
      qc.invalidateQueries({ queryKey: ['projectionStatus', entityName] });
    },
  });
}

// ── Entity records ────────────────────────────────────────────────────────────

export function useEntityRecords(entityName: string) {
  return useQuery({
    queryKey: ['entityRecords', entityName],
    queryFn: async () => {
      if (!entityName) return [];
      const { data } = await api.get<EntityRecord[]>(`/entities/${entityName}/records`);
      return data;
    },
    enabled: !!entityName,
  });
}

export function useEntityRecord(entityName: string, recordId: number) {
  return useQuery({
    queryKey: ['entityRecord', entityName, recordId],
    queryFn: async () => {
      const { data } = await api.get<EntityRecord>(
        `/entities/${entityName}/records/${recordId}`,
      );
      return data;
    },
    enabled: Boolean(entityName && recordId),
  });
}

export function useUpdateEntityRecord(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      asset_id,
      data,
      status,
    }: {
      id: number;
      asset_id?: string;
      data: Record<string, any>;
      status?: string;
    }) => {
      const resp = await api.put(`/entities/${entityName}/records/${id}`, {
        asset_id,
        data,
        status,
      });
      return resp.data;
    },
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['entityRecords', entityName] });
      qc.invalidateQueries({ queryKey: ['entityRecord', entityName, id] });
    },
  });
}

export function useDeleteEntityRecord(entityName: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const resp = await api.delete(`/entities/${entityName}/records/${id}`);
      return resp.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['entityRecords', entityName] }),
  });
}
