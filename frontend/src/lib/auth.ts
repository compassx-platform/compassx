/**
 * Auth Helpers — real JWT token management.
 * Replaces the previous mock that always returned a dummy token.
 */

export interface PrincipalInfo {
  principal_id: string;
  name: string;
  email: string | null;
  is_account_admin: boolean;
  account_id: string;
  expires_at: string;
}

const ACCESS_KEY  = "um_access_token";
const REFRESH_KEY = "um_refresh_token";
const INFO_KEY    = "um_principal_info";

// ── Token storage ─────────────────────────────────────────────────────────────

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(ACCESS_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(ACCESS_KEY);
}

export function getAccessToken(): string | null {
  return getToken();
}

export function setAccessToken(token: string): void {
  setToken(token);
}

export function clearAccessToken(): void {
  clearToken();
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_KEY, token);
}

export function clearRefreshToken(): void {
  localStorage.removeItem(REFRESH_KEY);
}

export function saveTokens(access: string, refresh: string): void {
  setToken(access);
  setRefreshToken(refresh);
}

export function clearTokens(): void {
  clearToken();
  clearRefreshToken();
}

// ── Principal info ────────────────────────────────────────────────────────────

export function getPrincipalInfo(): PrincipalInfo | null {
  try {
    const raw = localStorage.getItem(INFO_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setPrincipalInfo(info: PrincipalInfo): void {
  localStorage.setItem(INFO_KEY, JSON.stringify(info));
}

export function clearPrincipalInfo(): void {
  localStorage.removeItem(INFO_KEY);
}

import axios from "axios";
import { purgeAllClientState } from './queryClient';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/api\/v1\/?$/, "") || "";

export function saveSession(token: string, info: PrincipalInfo): void {
  setToken(token);
  setPrincipalInfo(info);
}

export function clearSession(): void {
  clearTokens();
  clearPrincipalInfo();
  purgeAllClientState();
}

// ── Auth state & Refresh ──────────────────────────────────────────────────────

let _refreshTokenPromise: Promise<string> | null = null;

export function refreshAccessToken(): Promise<string> {
  if (_refreshTokenPromise) {
    return _refreshTokenPromise;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    clearSession();
    return Promise.reject(new Error("No refresh token available"));
  }

  _refreshTokenPromise = axios
    .post(`${BASE}/api/um/auth/refresh`, { refresh_token: refreshToken })
    .then((r) => {
      const newToken = r.data.access_token;
      setToken(newToken);
      return newToken;
    })
    .catch((err) => {
      const status = err?.response?.status;
      // Only clear session and redirect if token was explicitly rejected (400, 401, 403)
      if (status && status >= 400 && status < 500) {
        clearSession();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login";
        }
      }
      throw err;
    })
    .finally(() => {
      _refreshTokenPromise = null;
    });

  return _refreshTokenPromise;
}

export function isTokenExpired(token: string, bufferSeconds = 0): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;
    const payload = JSON.parse(atob(parts[1]));
    if (!payload.exp) return false;
    return Date.now() >= (payload.exp - bufferSeconds) * 1000;
  } catch {
    return true;
  }
}

export function isLoggedIn(): boolean {
  const token = getToken();
  const refreshToken = getRefreshToken();
  if (token && !isTokenExpired(token)) {
    return true;
  }
  // If access token is missing or expired, but we have a refresh token, session is still active
  return !!refreshToken;
}

export function getAuthKey(): string | null {
  return getToken();
}

// Legacy export kept for backward compat
export const AUTH_BYPASS = false;
