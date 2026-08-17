/** React hooks for breakdown event CRUD + explorer queries */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ExplorerResponse } from '@/types';

interface ExplorerQueryParams {
  dataset: string;
  filters: Record<string, unknown>;
  pagination: { page: number; size: number };
  sort?: Record<string, string>;
}

export function useExplorerQuery(params: ExplorerQueryParams) {
  return useQuery({
    queryKey: ['explorer', params],
    queryFn: async () => {
      const { data } = await api.post<ExplorerResponse>('/explorer/query', params);
      return data;
    },
  });
}

export function useCreateBreakdown() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { asset_id: string; timestamp?: string; data: Record<string, unknown> }) => {
      const { data } = await api.post('/entities/breakdown_event/records', body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['explorer'] }),
  });
}

export function useUpdateBreakdown() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: number; data: Record<string, unknown>; status?: string }) => {
      const { data } = await api.put(`/entities/breakdown_event/records/${id}`, body);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['explorer'] }),
  });
}

export function useDeleteBreakdown() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/entities/breakdown_event/records/${id}`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['explorer'] }),
  });
}
