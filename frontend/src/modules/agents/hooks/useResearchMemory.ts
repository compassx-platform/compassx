import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ResearchMemoryItem {
  id: string;
  fact: string;
  fact_type: string;
  confidence: number;
  source_agent?: string | null;
  source_session_id?: string | null;
  source_type: string;
  promoted_via: string;
  scope: string;
  tags: string[];
  valid_from: string | null;
  last_confirmed_at: string | null;
  confirmation_count: number;
  created_at: string | null;
}

export function useResearchMemory() {
  return useQuery({
    queryKey: ["research-memory"],
    queryFn: async () => {
      const { data } = await api.get<ResearchMemoryItem[]>("/research-engine/memory");
      return data;
    },
    staleTime: 15_000,
  });
}
