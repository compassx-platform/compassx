import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Dashboard, DashboardMeta, Dataset } from '@/types/dashboard';

// ── Keys ──────────────────────────────────────────────────────────────────────

const KEYS = {
  list: ['dashboards'] as const,
  detail: (id: string) => ['dashboards', id] as const,
  datasetQuery: (id: string, params: Record<string, unknown>) => ['dataset-query', id, params] as const,
  datasetSchema: (id: string) => ['dataset-schema', id] as const,
};

// ── List ──────────────────────────────────────────────────────────────────────

export function useDashboards() {
  return useQuery<DashboardMeta[]>({
    queryKey: KEYS.list,
    queryFn: async () => {
      const { data } = await api.get('/dashboards');
      return data;
    },
  });
}

// ── Detail ────────────────────────────────────────────────────────────────────

export function useDashboard(id: string | undefined) {
  return useQuery<Dashboard>({
    queryKey: KEYS.detail(id ?? ''),
    enabled: !!id,
    queryFn: async () => {
      const { data } = await api.get(`/dashboards/${id}`);
      return data;
    },
  });
}

// ── Create ────────────────────────────────────────────────────────────────────

export function useCreateDashboard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => {
      const { data } = await api.post('/dashboards', { name });
      return data as Dashboard;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.list }),
  });
}

// ── Save (draft) ──────────────────────────────────────────────────────────────

export function useSaveDashboard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dashboard: Dashboard) => {
      const { data } = await api.put(`/dashboards/${dashboard.id}`, dashboard);
      return data as Dashboard;
    },
    onSuccess: (d) => {
      qc.setQueryData(KEYS.detail(d.id), d);
    },
  });
}

// ── Publish ───────────────────────────────────────────────────────────────────

export function usePublishDashboard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/dashboards/${id}/publish`);
      return data as Dashboard;
    },
    onSuccess: (d) => {
      qc.setQueryData(KEYS.detail(d.id), d);
      qc.invalidateQueries({ queryKey: KEYS.list });
    },
  });
}

// ── Discard draft ─────────────────────────────────────────────────────────────

export function useDiscardDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/dashboards/${id}/discard`);
      return data as Dashboard;
    },
    onSuccess: (d) => {
      qc.setQueryData(KEYS.detail(d.id), d);
    },
  });
}

// ── Clone ─────────────────────────────────────────────────────────────────────

export function useCloneDashboard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/dashboards/${id}/clone`);
      return data as Dashboard;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.list }),
  });
}

// ── Delete ────────────────────────────────────────────────────────────────────

export function useDeleteDashboard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/dashboards/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.list }),
  });
}

// ── Dataset query (run SQL + return rows) ─────────────────────────────────────

export interface DatasetQueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  executionMs: number;
}

function normalizeDatasetQueryResult(raw: any): DatasetQueryResult {
  const columns: string[] = Array.isArray(raw?.columns) ? raw.columns : [];
  const rows = Array.isArray(raw?.rows)
    ? raw.rows.map((row: any) => {
        if (row && typeof row === 'object' && !Array.isArray(row)) {
          return row as Record<string, unknown>;
        }
        if (Array.isArray(row)) {
          return Object.fromEntries(columns.map((col, idx) => [col, row[idx]]));
        }
        return { value: row };
      })
    : [];

  return {
    columns,
    rows,
    rowCount: typeof raw?.rowCount === 'number' ? raw.rowCount : rows.length,
    executionMs: typeof raw?.executionMs === 'number' ? raw.executionMs : 0,
  };
}

export function useDatasetQuery(
  datasetId: string | undefined,
  params: Record<string, unknown> = {},
  filters: Record<string, unknown> = {},
  enabled = true,
  sql?: string,
  refreshKey?: string | number
) {
  return useQuery<DatasetQueryResult>({
    queryKey: KEYS.datasetQuery(datasetId ?? '', { ...params, ...filters, sql, refreshKey }),
    enabled: !!datasetId && enabled,
    queryFn: async () => {
      const { data } = await api.post(`/dashboards/datasets/${datasetId}/query`, { params, filters, sql });
      return normalizeDatasetQueryResult(data);
    },
    staleTime: 30_000,
  });
}

// ── Dataset schema ────────────────────────────────────────────────────────────

export function useDatasetSchema(datasetId: string | undefined) {
  return useQuery({
    queryKey: KEYS.datasetSchema(datasetId ?? ''),
    enabled: !!datasetId,
    queryFn: async () => {
      const { data } = await api.get(`/dashboards/datasets/${datasetId}/schema`);
      return data as Array<{ name: string; type: string; comment?: string }>;
    },
    staleTime: 5 * 60_000,
  });
}

// ── Export dataset ────────────────────────────────────────────────────────────

export function useExportDataset() {
  return useMutation({
    mutationFn: async ({ datasetId, format }: { datasetId: string; format: 'csv' | 'tsv' | 'excel' }) => {
      const { data } = await api.get(`/dashboards/datasets/${datasetId}/export`, {
        params: { format },
        responseType: 'blob',
      });
      const ext = format === 'excel' ? 'xlsx' : format;
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dataset.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
}

// ── Dataset field distinct values (for dynamic param lists) ───────────────────

export function useFieldValues(datasetId: string | undefined, field: string | undefined) {
  return useQuery<string[]>({
    queryKey: ['field-values', datasetId, field],
    enabled: !!datasetId && !!field,
    queryFn: async () => {
      const { data } = await api.get(`/dashboards/datasets/${datasetId}/field-values`, {
        params: { field },
      });
      return data;
    },
    staleTime: 60_000,
  });
}

// ── Save layout (persist grid positions) ─────────────────────────────────────

export function useSaveLayout() {
  return useMutation({
    mutationFn: async ({ dashboardId, pageId, layout }: { dashboardId: string; pageId: string; layout: unknown[] }) => {
      await api.put(`/dashboards/${dashboardId}/pages/${pageId}/layout`, { layout });
    },
  });
}
