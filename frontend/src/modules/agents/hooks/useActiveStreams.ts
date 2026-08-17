import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ActiveStream {
  id: string;
  kind: "agent";
  status: string;
  started_at: string;
  updated_at: string;
  agent_id?: number | null;
  session_id?: number | null;
  user_id?: string | null;
  llm_connection_id?: number | null;
  context_type?: string | null;
  detail?: string | null;
  event_count: number;
  metadata?: Record<string, unknown>;
}

export function useActiveStreams() {
  return useQuery({
    queryKey: ["active-streams"],
    queryFn: async () => {
      const { data } = await api.get<{ streams: ActiveStream[] }>("/streams/active");
      return data.streams;
    },
    refetchInterval: 5000,
    staleTime: 2000,
  });
}
