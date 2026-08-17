import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface MemoryItem {
  id: string;
  fact: string;
  fact_type: string;
  tags: string[];
  confidence: number;
  tier: number;
  source: string;
  created_at: string | null;
  last_reinforced_at: string | null;
}

export function useMemory() {
  return useQuery({
    queryKey: ["agent-memory"],
    queryFn: async () => {
      const { data } = await api.get<MemoryItem[]>("/agents/memory");
      return data;
    },
    staleTime: 30_000,
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (memoryId: string) => {
      await api.delete(`/agents/memory/${memoryId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-memory"] });
      queryClient.invalidateQueries({ queryKey: ["agent-memory-logs"] });
    },
  });
}

export interface MemoryExtractionLogItem {
  id: string;
  session_id: string;
  trigger: string;
  turns_processed: number;
  facts_extracted: number;
  facts_created: number;
  facts_merged: number;
  status: string;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export function useMemoryLogs() {
  return useQuery({
    queryKey: ["agent-memory-logs"],
    queryFn: async () => {
      const { data } = await api.get<MemoryExtractionLogItem[]>("/agents/memory/logs");
      return data;
    },
    staleTime: 10_000,
  });
}
