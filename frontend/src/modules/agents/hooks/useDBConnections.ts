import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface DBConnection {
  id: number;
  name: string;
  db_type: string;
  host?: string;
  port?: number;
  db_name?: string;
  ssl_config?: Record<string, unknown>;
  profiler_agent_id?: number;
  scoped_tables?: string[];
  created_at: string;
  updated_at: string;
}

export function useDBConnections() {
  return useQuery({
    queryKey: ["db-connections"],
    queryFn: async () => {
      const { data } = await api.get<DBConnection[]>("/db-connections");
      return data;
    },
    staleTime: 60_000,
  });
}

export function useCreateDBConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      payload,
    }: {
      payload: {
        name: string;
        db_type: string;
        host?: string;
        port?: number;
        db_name?: string;
        username?: string;
        password?: string;
        ssl_config?: Record<string, unknown>;
        profiler_agent_id?: number;
        scoped_tables?: string[];
      };
    }) => {
      const { data } = await api.post<DBConnection>("/db-connections", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["db-connections"] }),
  });
}

export function useUpdateDBConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connId,
      payload,
    }: {
      connId: number;
      payload: {
        name?: string;
        host?: string;
        port?: number;
        db_name?: string;
        username?: string;
        password?: string;
        ssl_config?: Record<string, unknown>;
        profiler_agent_id?: number | null;
        scoped_tables?: string[];
      };
    }) => {
      const { data } = await api.put<DBConnection>(`/db-connections/${connId}`, payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["db-connections"] }),
  });
}

export function useDeleteDBConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connId,
    }: {
      connId: number;
    }) => {
      await api.delete(`/db-connections/${connId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["db-connections"] }),
  });
}

export function useTestDBConnection() {
  return useMutation({
    mutationFn: async ({
      connId,
    }: {
      connId: number;
    }) => {
      const { data } = await api.post<{ success: boolean; message: string }>(`/db-connections/${connId}/test`, {});
      return data;
    },
  });
}

export function useReprofileDBConnection() {
  return useMutation({
    mutationFn: async ({ connId }: { connId: number }) => {
      const { data } = await api.post<{ status: string; message: string }>(`/db-connections/${connId}/reprofile`, {});
      return data;
    },
  });
}

export interface DataSourceProfile {
  id: number;
  connection_id: number;
  table_name: string;
  row_count?: number;
  last_profiled_at: string;
  profiled_by_agent_run_id?: number;
  columns: any[];
  candidate_relationships: any[];
  detected_layer?: string;
  prior_art_references: any[];
  unresolved_ambiguities: string[];
}

export function useDBConnectionProfiles(connId: number, enabled = true) {
  return useQuery({
    queryKey: ["db-connections", connId, "profiles"],
    queryFn: async () => {
      const { data } = await api.get<DataSourceProfile[]>(`/db-connections/${connId}/profiles`);
      return data;
    },
    enabled: !!connId && enabled,
    staleTime: 30_000,
  });
}

export function useDBSchema(
  connId: number | null,
  enabled = false
) {
  return useQuery({
    queryKey: ["db-connections", connId, "schema"],
    queryFn: async () => {
      const { data } = await api.get<{ tables: Record<string, string[]> }>(`/db-connections/${connId}/schema`);
      return data.tables;
    },
    enabled: connId != null && enabled,
    staleTime: 120_000,
  });
}
