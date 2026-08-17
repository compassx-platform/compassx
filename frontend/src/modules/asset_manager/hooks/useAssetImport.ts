import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export type ImportJob = {
  import_job_id: string;
  name: string;
  status: string;
  stage: string;
  industry_tag: string;
  total_records: number;
  parsed_records: number;
  valid_records: number;
  failed_records: number;
  imported_records: number;
  merged_dataset_id?: string | null;
  mapping?: ImportMapping[] | null;
  created_at?: string;
  updated_at?: string;
  created_by?: string | null;
};

export type ImportMapping = {
  source_column: string;
  target_field: string;
  transform?: string;
  confidence?: string;
  reasoning?: string;
};

export type FilePreview = {
  file_id: string;
  file_name: string;
  file_size_kb: number;
  format: string;
  sheet_count: number;
  sheets: Array<{
    sheet_name: string;
    total_rows: number;
    total_columns: number;
    column_names: string[];
    preview_rows: unknown[][];
  }>;
  parse_warnings: string[];
};

export type ImportFileSummary = {
  file_id: string;
  file_name: string;
  file_size_kb: number;
  uploaded_at: string;
  status: string;
  active_sheet?: string | null;
  column_names?: string[];
};

export type AssetTypeMatchSummary = {
  column_name: string;
  total_rows: number;
  matched_rows: number;
  unmatched_rows: number;
  matched_types: Array<{
    asset_type_id: number;
    name: string;
    category: string;
    matched_rows: number;
  }>;
  unmatched_values: Array<{
    value: string;
    rows: number;
  }>;
};

export type AssetHierarchyMappingSummary = {
  asset_type_column: string;
  parent_column?: string | null;
  parent_column_required: boolean;
  total_matched_type_rows: number;
  steps: Array<{
    asset_type_id: number;
    name: string;
    category: string;
    is_root: boolean;
    rows: number;
    parent_matched_rows: number;
    parent_unmatched_rows: number;
    ready_to_add_rows: number;
    unmatched_parent_values: Array<{
      value: string;
      rows: number;
    }>;
  }>;
};

export function useAssetImportJobs() {
  return useQuery({
    queryKey: ['asset-imports'],
    queryFn: async () => {
      const { data } = await api.get<{ jobs: ImportJob[] }>('/asset-imports');
      return data.jobs;
    },
  });
}

export function useCreateAssetImportJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; industry_tag: string; source_format: string }) => {
      const { data } = await api.post<ImportJob>('/asset-imports', body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-imports'] }),
  });
}

export function useAssetImportJob(id?: string) {
  return useQuery({
    queryKey: ['asset-imports', id],
    queryFn: async () => {
      const { data } = await api.get<ImportJob>(`/asset-imports/${id}`);
      return data;
    },
    enabled: Boolean(id),
  });
}

export function useAssetImportFiles(importJobId?: string) {
  return useQuery({
    queryKey: ['asset-imports', importJobId, 'files'],
    queryFn: async () => {
      const { data } = await api.get<{ files: ImportFileSummary[] }>(`/asset-imports/${importJobId}/files`);
      return data.files;
    },
    enabled: Boolean(importJobId),
  });
}

export function useAssetImportFilePreview(importJobId?: string, fileId?: string) {
  return useQuery({
    queryKey: ['asset-imports', importJobId, 'files', fileId, 'preview'],
    queryFn: async () => {
      const { data } = await api.get<FilePreview>(`/asset-imports/${importJobId}/files/${fileId}/preview`);
      return data;
    },
    enabled: Boolean(importJobId && fileId),
  });
}

export function useAssetTypeMatchSummary(importJobId?: string, column?: string) {
  return useQuery({
    queryKey: ['asset-imports', importJobId, 'asset-type-match', column],
    queryFn: async () => {
      const { data } = await api.get<AssetTypeMatchSummary>(`/asset-imports/${importJobId}/asset-type-match`, {
        params: { column },
      });
      return data;
    },
    enabled: Boolean(importJobId && column),
  });
}

export function useAssetHierarchyMappingSummary(importJobId?: string, assetTypeColumn?: string, parentColumn?: string) {
  return useQuery({
    queryKey: ['asset-imports', importJobId, 'hierarchy-mapping', assetTypeColumn, parentColumn],
    queryFn: async () => {
      const { data } = await api.get<AssetHierarchyMappingSummary>(`/asset-imports/${importJobId}/hierarchy-mapping`, {
        params: { asset_type_column: assetTypeColumn, parent_column: parentColumn || undefined },
      });
      return data;
    },
    enabled: Boolean(importJobId && assetTypeColumn),
  });
}

export function useAssetImportActions(importJobId?: string) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['asset-imports'] });
    qc.invalidateQueries({ queryKey: ['asset-imports', importJobId] });
    qc.invalidateQueries({ queryKey: ['asset-imports', importJobId, 'files'] });
    qc.invalidateQueries({ queryKey: ['asset-instances'] });
    qc.invalidateQueries({ queryKey: ['asset-children'] });
    qc.invalidateQueries({ queryKey: ['asset-hierarchy'] });
  };

  const uploadFile = useMutation({
    mutationFn: async (file: File) => {
      if (!importJobId) throw new Error('Import job is required');
      const form = new FormData();
      form.append('file', file);
      const { data } = await api.post<FilePreview>(`/asset-imports/${importJobId}/files`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data;
    },
    onSuccess: invalidate,
  });

  const setFileStatus = useMutation({
    mutationFn: async ({ fileId, status }: { fileId: string; status: 'accepted' | 'rejected' }) => {
      await api.post(`/asset-imports/${importJobId}/files/${fileId}/status`, { status });
    },
    onSuccess: invalidate,
  });

  const merge = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/asset-imports/${importJobId}/merge`, { merge_strategy: 'append' });
      return data;
    },
    onSuccess: invalidate,
  });

  const suggestMapping = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ suggested_mapping: ImportMapping[]; missing_required_fields: string[] }>(`/asset-imports/${importJobId}/suggest-mapping`);
      return data;
    },
  });

  const applyMapping = useMutation({
    mutationFn: async (field_mappings: ImportMapping[]) => {
      const { data } = await api.post<ImportJob>(`/asset-imports/${importJobId}/mapping`, { field_mappings });
      return data;
    },
    onSuccess: invalidate,
  });

  const dryRun = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/asset-imports/${importJobId}/dry-run`);
      return data;
    },
    onSuccess: invalidate,
  });

  const summary = useMutation({
    mutationFn: async () => {
      const { data } = await api.get(`/asset-imports/${importJobId}/summary`);
      return data;
    },
  });

  const approve = useMutation({
    mutationFn: async (confirmation_statement: string) => {
      const { data } = await api.post(`/asset-imports/${importJobId}/approve`, { confirmation_statement });
      return data;
    },
    onSuccess: invalidate,
  });

  const verification = useMutation({
    mutationFn: async () => {
      const { data } = await api.get(`/asset-imports/${importJobId}/verification`);
      return data;
    },
  });

  return { uploadFile, setFileStatus, merge, suggestMapping, applyMapping, dryRun, summary, approve, verification };
}
