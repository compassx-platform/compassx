import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/appsApi";

export function useApps(workspaceId: string) {
  return useQuery({
    queryKey: ["apps", workspaceId],
    queryFn: () => api.listApps(workspaceId),
    enabled: !!workspaceId,
  });
}

export function useApp(appId: string) {
  return useQuery({
    queryKey: ["apps", appId],
    queryFn: () => api.getApp(appId),
    enabled: !!appId,
  });
}

export function useCreateApp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createApp,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }),
  });
}
