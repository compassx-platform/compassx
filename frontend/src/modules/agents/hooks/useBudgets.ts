import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface Budget {
  id: number;
  scope_type: string;
  scope_id: string;
  period: "daily" | "monthly";
  limit_amount: number;
  warn_threshold_pct: number;
  on_exceeded: "alert_only" | "block_new_calls" | "block_and_pause_agent";
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by?: string;
}

export interface BudgetStatus {
  id: number;
  scope_type: string;
  scope_id: string;
  period: "daily" | "monthly";
  period_start: string;
  period_end: string;
  amount_spent: number;
  status: string;
  warning_fired_at_pct?: number;
  exceeded_fired: boolean;
  last_updated_at: string;
}

export function useBudgets(scopeType?: string, scopeId?: string) {
  return useQuery({
    queryKey: ["budgets", scopeType, scopeId],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (scopeType) params.scope_type = scopeType;
      if (scopeId) params.scope_id = scopeId;
      const { data } = await api.get<Budget[]>("/budgets", { params });
      return data;
    },
    staleTime: 30_000,
  });
}

export function useBudgetStatuses(scopeType: string, scopeId?: string, workspaceId?: string) {
  return useQuery({
    queryKey: ["budget-statuses", scopeType, scopeId, workspaceId],
    queryFn: async () => {
      const params: Record<string, string> = { scope_type: scopeType };
      if (scopeId) params.scope_id = scopeId;
      if (workspaceId) params.workspace_id = workspaceId;
      const { data } = await api.get<BudgetStatus[]>("/budgets/status", { params });
      return data;
    },
    staleTime: 10_000,
  });
}

export function useCreateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      scope_type: string;
      scope_id: string;
      period: "daily" | "monthly";
      limit_amount: number;
      warn_threshold_pct?: number;
      on_exceeded?: "alert_only" | "block_new_calls" | "block_and_pause_agent";
      is_active?: boolean;
    }) => {
      const { data } = await api.post<Budget>("/budgets", payload);
      return data;
    },
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["budget-statuses"] });
      qc.invalidateQueries({ queryKey: ["agents"] }); // Refetch agents as status might change
    },
  });
}

export function useUpdateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      budgetId,
      payload,
    }: {
      budgetId: number;
      payload: {
        limit_amount?: number;
        warn_threshold_pct?: number;
        on_exceeded?: "alert_only" | "block_new_calls" | "block_and_pause_agent";
        is_active?: boolean;
      };
    }) => {
      const { data } = await api.put<Budget>(`/budgets/${budgetId}`, payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["budget-statuses"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}

export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (budgetId: number) => {
      await api.delete(`/budgets/${budgetId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budgets"] });
      qc.invalidateQueries({ queryKey: ["budget-statuses"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}
