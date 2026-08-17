import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/appsApi";

export function useCheckpoint(appId: string, branchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api.checkpointBranch(appId, branchId, message),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["branches", appId] });
      qc.invalidateQueries({ queryKey: ["files", appId, branchId] });
    },
  });
}
