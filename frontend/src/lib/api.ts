import axios, { AxiosError } from "axios";
import { getToken, refreshAccessToken } from "./auth";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// ── Request: attach Bearer token and X-Workspace-Slug ─────────────────────────
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  const match = window.location.pathname.match(/^\/w\/([^/]+)/);
  if (match) {
    config.headers["X-Workspace-Slug"] = match[1];
  }
  return config;
});

// ── Response: silent token refresh on 401 ─────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retry?: boolean });
    const isAuthEndpoint = Boolean(
      original?.url && (
        original.url.includes("/auth/login") ||
        original.url.includes("/auth/refresh") ||
        original.url.includes("/setup") ||
        original.url.includes("/invites/")
      )
    );
    if (error.response?.status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        const newToken = await refreshAccessToken();
        if (original.headers) {
          original.headers["Authorization"] = `Bearer ${newToken}`;
        }
        return api(original);
      } catch {
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
