import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface Skill {
  id: number;
  name: string;
  description: string;
  body: string;
  trigger_hints: string[];
  version: number;
  is_active: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentSkill {
  id: number;
  agent_id: number;
  skill_id: number;
  position: number;
  attached_at: string;
  skill: Skill;
}

export function useSkills(search?: string) {
  return useQuery({
    queryKey: ["skills", { search }],
    queryFn: async () => {
      const { data } = await api.get<Skill[]>("/skills", {
        params: search ? { search } : undefined,
      });
      return data;
    },
    staleTime: 30_000,
  });
}

export function useSkill(skillId: number | null) {
  return useQuery({
    queryKey: ["skills", skillId],
    queryFn: async () => {
      const { data } = await api.get<Skill>(`/skills/${skillId}`);
      return data;
    },
    enabled: skillId != null,
    staleTime: 30_000,
  });
}

export function useCreateSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      name: string;
      description: string;
      body: string;
      trigger_hints: string[];
    }) => {
      const { data } = await api.post<Skill>("/skills", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useUpdateSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      skillId,
      payload,
    }: {
      skillId: number;
      payload: {
        name?: string;
        description?: string;
        body?: string;
        trigger_hints?: string[];
      };
    }) => {
      const { data } = await api.put<Skill>(`/skills/${skillId}`, payload);
      return data;
    },
    onSuccess: (_, { skillId }) => {
      qc.invalidateQueries({ queryKey: ["skills"] });
      qc.invalidateQueries({ queryKey: ["skills", skillId] });
      qc.invalidateQueries({ queryKey: ["agents"] }); // Agents might have cached skill changes
    },
  });
}

export function useDeleteSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (skillId: number) => {
      await api.delete(`/skills/${skillId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skills"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}

export function useAttachSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      skillId,
      agentId,
    }: {
      skillId: number;
      agentId: number;
    }) => {
      const { data } = await api.post<AgentSkill>(`/skills/${skillId}/attach/${agentId}`);
      return data;
    },
    onSuccess: (_, { agentId }) => {
      qc.invalidateQueries({ queryKey: ["agents", agentId] });
    },
  });
}

export function useDetachSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      skillId,
      agentId,
    }: {
      skillId: number;
      agentId: number;
    }) => {
      await api.post(`/skills/${skillId}/detach/${agentId}`);
    },
    onSuccess: (_, { agentId }) => {
      qc.invalidateQueries({ queryKey: ["agents", agentId] });
    },
  });
}
