import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export interface WorkflowTransition {
  from: string;
  to: string;
}

export interface WorkflowDefinition {
  entity_name: string;
  initial_state: string;
  is_enabled: boolean;
  states: string[];
  transitions: WorkflowTransition[];
}

export interface AvailableTransitionsResponse {
  available: string[];
}

export interface WorkflowCreatePayload {
  entity_name: string;
  initial_state: string;
  states: string[];
  transitions: WorkflowTransition[];
  is_enabled?: boolean;
}

export function useWorkflow(entityName: string) {
  return useQuery({
    queryKey: ['workflow', entityName],
    queryFn: async () => {
      const { data } = await api.get<WorkflowDefinition>(`/workflows/${entityName}`);
      return data;
    },
    enabled: Boolean(entityName),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateOrUpdateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: WorkflowCreatePayload) => {
      const { data } = await api.post<WorkflowDefinition>('/workflows', payload);
      return data;
    },
    onSuccess: (_data, { entity_name }) => {
      qc.invalidateQueries({ queryKey: ['workflow', entity_name] });
    },
  });
}

export function useWorkflowTransitions(entityName: string, currentState: string) {
  return useQuery({
    queryKey: ['workflowTransitions', entityName, currentState],
    queryFn: async () => {
      if (!entityName || !currentState) return { available: [] };
      const { data } = await api.get<AvailableTransitionsResponse>(
        `/workflows/${entityName}/transitions`,
        { params: { current_state: currentState } },
      );
      return data;
    },
    enabled: Boolean(entityName && currentState),
    staleTime: 2 * 60 * 1000,
  });
}
