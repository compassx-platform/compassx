import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/appsApi";

export function useBranches(appId: string) {
  return useQuery({
    queryKey: ["branches", appId],
    queryFn: () => api.listBranches(appId),
    enabled: !!appId,
  });
}

export function useCreateBranch(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: api.BranchCreate) => api.createBranch(appId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["branches", appId] }),
  });
}

export function useDeleteBranch(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (branchId: string) => api.deleteBranch(appId, branchId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["branches", appId] }),
  });
}
