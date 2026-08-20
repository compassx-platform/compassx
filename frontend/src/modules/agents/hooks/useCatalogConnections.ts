import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ConnectionFieldSchema {
  name: string;
  label: string;
  type: string;
  required: boolean;
  default?: any;
  placeholder?: string;
  help_text?: string;
  options?: Array<{ value: string; label: string }>;
}

export interface ProviderMetadata {
  type_id: string;
  name: string;
  category: string;
  description: string;
  is_popular: boolean;
  logo: string;
  default_port?: number | null;
  config_fields: ConnectionFieldSchema[];
  auth_fields: ConnectionFieldSchema[];
}

export interface CatalogConnection {
  id: string;
  catalog: string;
  schema_name: string;
  name: string;
  full_name: string;
  category: string;
  connector_type: string;
  description?: string | null;
  config: Record<string, any>;
  status: string;
  owner: string;
  created_at: string;
  updated_at: string;
}

export interface CreateCatalogConnectionPayload {
  catalog?: string;
  schema?: string;
  name: string;
  connector_type: string;
  category?: string;
  description?: string;
  config?: Record<string, any>;
  auth_config?: Record<string, any> | string;
  status?: string;
}

export interface UpdateCatalogConnectionPayload {
  description?: string;
  config?: Record<string, any>;
  auth_config?: Record<string, any> | string;
  status?: string;
}

export interface TestConnectionPayload {
  connector_type?: string;
  config?: Record<string, any>;
  auth_config?: Record<string, any> | string;
  connection_id?: string;
}

export interface TestConnectionResult {
  success: boolean;
  message: string;
  latency_ms: number;
  details?: Record<string, any>;
}

export function useConnectionProviders(category?: string) {
  return useQuery({
    queryKey: ["connection-providers", category],
    queryFn: async () => {
      const params = category ? { category } : undefined;
      const { data } = await api.get<ProviderMetadata[]>("/connections/providers", { params });
      return data;
    },
    staleTime: 300_000,
  });
}

export function useCatalogConnections(filters?: {
  catalog?: string;
  schema?: string;
  category?: string;
  connector_type?: string;
  status?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: ["catalog-connections", filters],
    queryFn: async () => {
      const { data } = await api.get<CatalogConnection[]>("/connections", { params: filters });
      return data;
    },
    staleTime: 30_000,
  });
}

export function useCreateCatalogConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateCatalogConnectionPayload) => {
      const { data } = await api.post<CatalogConnection>("/connections", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalog-connections"] });
      qc.invalidateQueries({ queryKey: ["external-connections"] });
      qc.invalidateQueries({ queryKey: ["db-connections"] });
      qc.invalidateQueries({ queryKey: ["catalogs"] });
    },
  });
}

export function useUpdateCatalogConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: string;
      payload: UpdateCatalogConnectionPayload;
    }) => {
      const { data } = await api.put<CatalogConnection>(`/connections/${id}`, payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalog-connections"] });
      qc.invalidateQueries({ queryKey: ["external-connections"] });
      qc.invalidateQueries({ queryKey: ["db-connections"] });
    },
  });
}

export function useToggleConnectionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post<CatalogConnection>(`/connections/${id}/toggle-status`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalog-connections"] });
    },
  });
}

export function useDeleteCatalogConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/connections/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["catalog-connections"] });
      qc.invalidateQueries({ queryKey: ["catalogs"] });
    },
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: async (payload: TestConnectionPayload) => {
      const { data } = await api.post<TestConnectionResult>("/connections/test", payload);
      return data;
    },
  });
}

export interface CatalogSummary {
  name: string;
  catalog_type: string;
  comment?: string | null;
  schemas: Array<{
    name: string;
    comment?: string | null;
  }>;
}

export function useCatalogs() {
  return useQuery({
    queryKey: ["catalog-summaries"],
    queryFn: async () => {
      const { data } = await api.get<CatalogSummary[]>("/catalog/catalogs");
      return data;
    },
    staleTime: 60_000,
  });
}
