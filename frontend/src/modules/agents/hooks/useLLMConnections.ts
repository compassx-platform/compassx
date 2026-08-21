import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface LLMConnection {
  id: number;
  name: string;
  provider: string;
  model_name: string;
  api_key_masked?: string;
  base_url?: string;
  config?: Record<string, unknown>;
  timeout_s: number;
  max_tokens: number;
  is_fallback: boolean;
  use_for_embedding: boolean;
  input_cost_per_1k_tokens?: number;
  output_cost_per_1k_tokens?: number;
  cost_currency?: string;
  cost_configured_at?: string;
  cost_configured_by?: string;
  created_at: string;
  updated_at: string;
}

export function useLLMConnections() {
  return useQuery({
    queryKey: ["llm-connections"],
    queryFn: async () => {
      const { data } = await api.get<LLMConnection[]>("/llm-connections");
      return data;
    },
    staleTime: 60_000,
  });
}

export function useCreateLLMConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      payload,
    }: {
      payload: {
        name: string;
        provider: string;
        model_name: string;
        api_key?: string;
        base_url?: string;
        use_for_embedding?: boolean;
        input_cost_per_1k_tokens?: number;
        output_cost_per_1k_tokens?: number;
        cost_currency?: string;
      };
    }) => {
      const { data } = await api.post<LLMConnection>("/llm-connections", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-connections"] }),
  });
}

export function useUpdateLLMConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connId,
      payload,
    }: {
      connId: number;
      payload: {
        name?: string;
        provider?: string;
        model_name?: string;
        api_key?: string;
        base_url?: string;
        use_for_embedding?: boolean;
        input_cost_per_1k_tokens?: number;
        output_cost_per_1k_tokens?: number;
        cost_currency?: string;
      };
    }) => {
      const { data } = await api.put<LLMConnection>(`/llm-connections/${connId}`, payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-connections"] }),
  });
}

export function useDeleteLLMConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connId,
    }: {
      connId: number;
    }) => {
      await api.delete(`/llm-connections/${connId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-connections"] }),
  });
}

export function useSetEmbeddingLLMConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ connId }: { connId: number }) => {
      const { data } = await api.post<LLMConnection>(`/llm-connections/${connId}/set-embedding`, {});
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm-connections"] }),
  });
}

export function usePingLLMConnection() {
  return useMutation({
    mutationFn: async ({
      connId,
    }: {
      connId: number;
    }) => {
      const { data } = await api.post<{ success: boolean; message: string }>(`/llm-connections/${connId}/ping`, {});
      return data;
    },
  });
}
