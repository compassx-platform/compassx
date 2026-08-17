import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/appsApi";

export function usePublish(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      commitId,
      sourceBranchId,
    }: {
      commitId: string;
      sourceBranchId: string;
    }) => api.publishApp(appId, commitId, sourceBranchId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["production", appId] }),
  });
}

export function useProductionStatus(appId: string) {
  return useQuery({
    queryKey: ["production", appId],
    queryFn: () => api.getProductionStatus(appId),
    enabled: !!appId,
    refetchInterval: 10000,
  });
}
