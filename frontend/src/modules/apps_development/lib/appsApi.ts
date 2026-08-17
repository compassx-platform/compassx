/**
 * Typed API client for all CompassX Apps v1 endpoints (§10).
 * All functions return typed responses using the schemas from the backend.
 */

const API_BASE = "/apps";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AppRead {
  app_id: string;
  name: string;
  catalog_fqn: string;
  workspace_id: string;
  owner_id: string;
  versioning_backend: "git" | "native";
  terminal_enabled_prod: boolean;
  max_concurrent_branches: number;
  created_at: string;
}

export interface AppCreate {
  name: string;
  catalog_fqn: string;
  workspace_id: string;
  versioning_backend?: "git" | "native";
  terminal_enabled_prod?: boolean;
  max_concurrent_branches?: number;
  catalog_grants?: object[];
  volume_grants?: object[];
}

export interface BranchRead {
  branch_id: string;
  app_id: string;
  name: string;
  head_commit_id: string | null;
  created_by: string;
  created_at: string;
}

export interface BranchCreate {
  name: string;
  from_branch_id?: string | null;
}

export interface CheckpointResponse {
  commit_id: string;
  branch_id: string;
  author: string;
  message: string | null;
  tree_manifest_hash: string;
  created_at: string;
}

export interface FileMeta {
  path: string;
  size_bytes: number;
  status: "clean" | "modified" | "untracked" | "deleted";
  last_modified: string | null;
}

export interface FileTree {
  files: FileMeta[];
}

export interface FileContent {
  path: string;
  content: string;
}

export interface FileDiff {
  path: string;
  status: "added" | "modified" | "deleted";
  diff_lines?: string[];
}

export interface DiffResult {
  commit_a: string;
  commit_b: string;
  changes: FileDiff[];
}

export interface PublishResponse {
  app_id: string;
  commit_id: string;
  production_pod_id: string;
  preview_url: string;
  status: string;
}

export interface ProductionStatus {
  app_id: string;
  current_commit_id: string | null;
  source_branch_id: string | null;
  switched_at: string | null;
  switched_by: string | null;
  pod_status: string | null;
  preview_url: string | null;
}

import api from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(url: string, options?: any): Promise<T> {
  const method = options?.method?.toLowerCase() || "get";
  let data = undefined;
  if (options?.body) {
    try {
      data = JSON.parse(options.body);
    } catch {
      data = options.body;
    }
  }

  const res = await api.request({
    url,
    method,
    data,
  });
  return res.data;
}

// ---------------------------------------------------------------------------
// Apps
// ---------------------------------------------------------------------------

export const listApps = (workspaceId: string): Promise<AppRead[]> =>
  apiFetch(`${API_BASE}?workspace_id=${workspaceId}`);

export const getApp = (appId: string): Promise<AppRead> =>
  apiFetch(`${API_BASE}/${appId}`);

export const createApp = (data: AppCreate): Promise<AppRead> =>
  apiFetch(API_BASE, { method: "POST", body: JSON.stringify(data) });

// ---------------------------------------------------------------------------
// Branches
// ---------------------------------------------------------------------------

export const listBranches = (appId: string): Promise<BranchRead[]> =>
  apiFetch(`${API_BASE}/${appId}/branches`);

export const createBranch = (appId: string, data: BranchCreate): Promise<BranchRead> =>
  apiFetch(`${API_BASE}/${appId}/branches`, { method: "POST", body: JSON.stringify(data) });

export const deleteBranch = (appId: string, branchId: string): Promise<void> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}`, { method: "DELETE" });

export const checkpointBranch = (
  appId: string,
  branchId: string,
  message: string,
): Promise<CheckpointResponse> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}/checkpoint`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export const diffBranch = (
  appId: string,
  branchId: string,
  against: string,
  detail = false,
): Promise<DiffResult> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}/diff?against=${against}&detail=${detail}`);

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export const listFiles = (appId: string, branchId: string): Promise<FileTree> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}/files`);

export const readFile = (appId: string, branchId: string, path: string): Promise<FileContent> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}/files/${path}`);

export const writeFile = (
  appId: string,
  branchId: string,
  path: string,
  content: string,
): Promise<void> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}/files/${path}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });

export const deleteFile = (appId: string, branchId: string, path: string): Promise<void> =>
  apiFetch(`${API_BASE}/${appId}/branches/${branchId}/files/${path}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Publish
// ---------------------------------------------------------------------------

export const publishApp = (
  appId: string,
  commitId: string,
  sourceBranchId: string,
): Promise<PublishResponse> =>
  apiFetch(`${API_BASE}/${appId}/publish`, {
    method: "POST",
    body: JSON.stringify({ commit_id: commitId, source_branch_id: sourceBranchId }),
  });

export const getProductionStatus = (appId: string): Promise<ProductionStatus> =>
  apiFetch(`${API_BASE}/${appId}/production`);

// ---------------------------------------------------------------------------
// WebSocket helpers (terminal + agent)
// ---------------------------------------------------------------------------

export function openTerminalSocket(appId: string, branchId: string): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(
    `${proto}://${window.location.host}/api/v1/apps/${appId}/branches/${branchId}/terminal`,
  );
}

export function openAgentSocket(appId: string, branchId: string): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(
    `${proto}://${window.location.host}/api/v1/apps/${appId}/branches/${branchId}/agent`,
  );
}
