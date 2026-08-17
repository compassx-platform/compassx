import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ResearchEngineRun {
  id: string;
  agent_id: number | null;
  trigger_type: string;
  status: string;
  context_package: Record<string, unknown>;
  changes_since_last_run: unknown[];
  maturity_assessment: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface TriggerResearchRunResponse {
  run_id: string;
  agent_id: number;
  session_id: number;
  session_title: string;
  initial_prompt: string;
}

export function useResearchEngineRuns() {
  return useQuery({
    queryKey: ["research-engine", "runs"],
    queryFn: async () => {
      const { data } = await api.get<ResearchEngineRun[]>("/research-engine/runs");
      return data;
    },
    staleTime: 15_000,
  });
}

export function useTriggerResearchEngineRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ agentId, title, prompt }: { agentId: number; title?: string; prompt?: string }) => {
      const { data } = await api.post<TriggerResearchRunResponse>("/research-engine/trigger", {
        agent_id: agentId,
        title,
        prompt,
      });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["research-engine", "runs"] });
    },
  });
}
