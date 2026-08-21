/**
 * WorkspaceGuard — wraps all /w/:workspaceSlug/* routes.
 * - Checks user is logged in; redirects to /login if not.
 * - Fetches workspace info from /api/w/:slug/api/workspace.
 * - Injects WorkspaceContext for child routes.
 */
import { useEffect } from "react";
import { Navigate, Outlet, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { getToken, getRefreshToken, isLoggedIn, refreshAccessToken } from "@/lib/auth";
import api from "@/lib/api";
import { WorkspaceContext, type WorkspaceInfo } from "@/lib/workspaceContext";
import { setDefaultWorkspace } from "@/lib/userManagerApi";

export default function WorkspaceGuard() {
  const { workspaceSlug } = useParams<{ workspaceSlug: string }>();

  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }

  const { data, isLoading, error } = useQuery<WorkspaceInfo>({
    queryKey: ["workspace-info", workspaceSlug],
    queryFn: async () => {
      if (!getToken() && getRefreshToken()) {
        await refreshAccessToken();
      }
      const { data } = await api.get(`/api/w/${workspaceSlug}/api/workspace`, { baseURL: "" });
      return data;
    },
    staleTime: 30_000,
    retry: 1,
    enabled: !!workspaceSlug,
  });

  useEffect(() => {
    if (data?.id) {
      setDefaultWorkspace(data.id).catch(() => {});
      try {
        localStorage.setItem("compassx_last_workspace", data.id);
      } catch {}
    }
  }, [data?.id]);

  if (isLoading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--color-bg)" }}>
        <Loader2 size={24} className="spin" style={{ color: "var(--color-text-muted)" }} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--color-bg)" }}>
        <div style={{ textAlign: "center", color: "var(--color-text-muted)" }}>
          <div style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 8 }}>Workspace not found</div>
          <div style={{ fontSize: "0.85rem" }}>"{workspaceSlug}" does not exist or you don't have access.</div>
          <a href="/" style={{ marginTop: 16, display: "inline-block", color: "var(--color-primary)" }}>Back to home</a>
        </div>
      </div>
    );
  }

  return (
    <WorkspaceContext.Provider value={data}>
      <Outlet />
    </WorkspaceContext.Provider>
  );
}
