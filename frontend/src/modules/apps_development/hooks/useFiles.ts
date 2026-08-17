import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "../lib/appsApi";

const isUuid = (str: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);

export function useFiles(appId: string, branchId: string) {
  return useQuery({
    queryKey: ["files", appId, branchId],
    queryFn: () => api.listFiles(appId, branchId),
    enabled: !!appId && !!branchId && isUuid(branchId),
    refetchInterval: 5000,  // poll every 5s for status marker updates
  });
}

export function useFileContent(appId: string, branchId: string, path: string) {
  return useQuery({
    queryKey: ["file-content", appId, branchId, path],
    queryFn: () => api.readFile(appId, branchId, path),
    enabled: !!appId && !!branchId && isUuid(branchId) && !!path,
  });
}

export function useWriteFile(appId: string, branchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) =>
      api.writeFile(appId, branchId, path, content),
    onSuccess: (_data, { path }) => {
      qc.invalidateQueries({ queryKey: ["file-content", appId, branchId, path] });
      qc.invalidateQueries({ queryKey: ["files", appId, branchId] });
    },
  });
}

export function useDeleteFile(appId: string, branchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => api.deleteFile(appId, branchId, path),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["files", appId, branchId] }),
  });
}
