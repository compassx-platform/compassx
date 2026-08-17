/**
 * React Query hooks for the time-series data editor module.
 *
 * Covers:
 *   - useTimeseriesQuery      – paginated query with filters
 *   - useTagDefinitions       – list available tags
 *   - useBatchUpdate          – inline save dirty rows
 *   - useUploadFile           – step 1: upload CSV/Excel
 *   - useValidateBatch        – step 2: validate staging batch
 *   - useDiff                 – step 3: get diff preview
 *   - useApplyBatch           – step 4: apply batch to raw_data
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TimeseriesRow {
  ts: string;
  asset_id: number;
  asset_name: string;
  tag_def_id: number;
  tag_name: string;
  value: number | null;
  // client-side only
  original_value?: number | null;
  isDirty?: boolean;
}

export interface TimeseriesQueryResponse {
  items: TimeseriesRow[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface TimeseriesFilters {
  asset_ids?: number[];
  tag_def_ids?: number[];
  start_time?: string;
  end_time?: string;
  page?: number;
  size?: number;
}

export interface BatchUpdateItem {
  ts: string;
  asset_id: number;
  tag_def_id: number;
  value: number;
}

export interface TagDefinition {
  id: number;
  name: string;
}

export interface StagingRow {
  row_number: number;
  ts: string | null;
  asset_ref: string | null;
  tag_ref: string | null;
  value: number | null;
  asset_id: number | null;
  tag_def_id: number | null;
  status: string;
  error_message: string | null;
}

export interface DiffResponse {
  batch_id: string;
  new: StagingRow[];
  updated: StagingRow[];
  duplicate: StagingRow[];
  invalid: StagingRow[];
}

export interface ValidateResponse {
  batch_id: string;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  new_count: number;
  updated_count: number;
}

export interface ApplyResponse {
  batch_id: string;
  applied: number;
  skipped: number;
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const tsKeys = {
  all: ["timeseries"] as const,
  list: (filters: TimeseriesFilters) => ["timeseries", "list", filters] as const,
  tags: () => ["timeseries", "tags"] as const,
  diff: (batchId: string) => ["timeseries", "diff", batchId] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Paginated time-series query with filters. */
export function useTimeseriesQuery(filters: TimeseriesFilters, enabled = true) {
  return useQuery<TimeseriesQueryResponse>({
    queryKey: tsKeys.list(filters),
    enabled,
    queryFn: async () => {
      const params = new URLSearchParams();

      (filters.asset_ids ?? []).forEach((id) => params.append("asset_ids[]", String(id)));
      (filters.tag_def_ids ?? []).forEach((id) => params.append("tag_def_ids[]", String(id)));
      if (filters.start_time) params.set("start_time", filters.start_time);
      if (filters.end_time) params.set("end_time", filters.end_time);
      params.set("page", String(filters.page ?? 1));
      params.set("size", String(filters.size ?? 100));

      const { data } = await api.get<TimeseriesQueryResponse>(
        `/timeseries?${params.toString()}`
      );
      return data;
    },
    staleTime: 30_000,
  });
}

/** List all tag definitions. */
export function useTagDefinitions() {
  return useQuery<TagDefinition[]>({
    queryKey: tsKeys.tags(),
    queryFn: async () => {
      const { data } = await api.get<TagDefinition[]>("/timeseries/tags");
      return data;
    },
    staleTime: 5 * 60_000,
  });
}

/** Batch-update (UPSERT) dirty rows from inline editing. */
export function useBatchUpdate() {
  const qc = useQueryClient();
  return useMutation<
    { updated: number; inserted: number },
    Error,
    { rows: BatchUpdateItem[] }
  >({
    mutationFn: async ({ rows }) => {
      const { data } = await api.post("/timeseries/batch-update", { rows });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tsKeys.all });
    },
  });
}

/** Step 1: Upload CSV/Excel file → returns batch_id. */
export function useUploadFile() {
  return useMutation<{ batch_id: string; row_count: number }, Error, File>({
    mutationFn: async (file) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/timeseries/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
  });
}

/** Step 2: Validate a batch. */
export function useValidateBatch() {
  return useMutation<ValidateResponse, Error, { batchId: string }>({
    mutationFn: async ({ batchId }) => {
      const { data } = await api.post(`/timeseries/upload/${batchId}/validate`);
      return data;
    },
  });
}

/** Step 3: Get diff preview for a validated batch. */
export function useDiff(batchId: string | null) {
  return useQuery<DiffResponse>({
    queryKey: tsKeys.diff(batchId ?? ""),
    enabled: !!batchId,
    queryFn: async () => {
      const { data } = await api.get<DiffResponse>(
        `/timeseries/upload/${batchId}/diff`
      );
      return data;
    },
  });
}

/** Step 4: Apply a validated batch. */
export function useApplyBatch() {
  const qc = useQueryClient();
  return useMutation<ApplyResponse, Error, { batchId: string }>({
    mutationFn: async ({ batchId }) => {
      const { data } = await api.post(`/timeseries/upload/${batchId}/apply`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tsKeys.all });
    },
  });
}