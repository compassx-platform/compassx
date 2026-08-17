/**
 * API calls for workspace/account management.
 * All workspace-scoped calls go to /api/w/:slug/api/...
 * Account-admin calls go to /api/account/...
 * Auth calls go to /api/auth/...
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { clearSession, getToken, refreshAccessToken } from "./auth";
import type { PrincipalInfo } from "./auth";

const BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/api\/v1\/?$/, "") || "";

// Raw axios for workspace/auth APIs (no /api/v1 prefix — lives at /api/auth/*)
const authApi = axios.create({ baseURL: BASE, timeout: 15000, headers: { "Content-Type": "application/json" } });
authApi.interceptors.request.use((c) => {
  const token = getToken();
  if (token) c.headers["Authorization"] = `Bearer ${token}`;
  return c;
});

authApi.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      try {
        const newToken = await refreshAccessToken();
        original.headers["Authorization"] = `Bearer ${newToken}`;
        return authApi(original);
      } catch (refreshErr) {
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(err);
  }
);

export interface WorkspaceSlim {
  id: string;
  name: string;
  slug: string;
  status: string;
  url: string;
  role: string | null;
}

export interface WorkspaceCreatePayload {
  name: string;
  slug: string;
  storage_backend: string;
  storage_config: Record<string, string>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<PrincipalInfo & { token: string }> {
  const { data } = await authApi.post("/api/auth/login", { email, password });
  return data;
}

export async function logout(): Promise<void> {
  try {
    await authApi.post("/api/auth/logout");
  } finally {
    clearSession();
  }
}

export async function fetchMyWorkspaces(): Promise<WorkspaceSlim[]> {
  const { data } = await authApi.get("/api/auth/workspaces");
  return data;
}

// ── Account admin — workspace CRUD ───────────────────────────────────────────

export async function createWorkspace(payload: WorkspaceCreatePayload): Promise<WorkspaceSlim> {
  const { data } = await authApi.post("/api/account/workspaces", payload);
  return {
    id: data.id,
    name: data.name,
    slug: data.slug,
    status: data.status,
    url: data.url,
    role: "admin",
  };
}

// ── React Query hooks ─────────────────────────────────────────────────────────

export function useMyWorkspaces() {
  return useQuery<WorkspaceSlim[]>({
    queryKey: ["my-workspaces"],
    queryFn: fetchMyWorkspaces,
    staleTime: 30_000,
    retry: false,
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createWorkspace,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-workspaces"] }),
  });
}
