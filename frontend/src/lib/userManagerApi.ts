/**
 * User Manager v1 — typed API client + React Query hooks.
 * All routes are prefixed with /api/um/* (new system).
 */
import axios, { AxiosInstance } from "axios";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getToken, saveTokens, clearSession, setToken,
  getRefreshToken, isTokenExpired, refreshAccessToken,
} from "./auth";

const BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/api\/v1\/?$/, "") || "";

const api: AxiosInstance = axios.create({ baseURL: BASE, timeout: 20000 });

// ── Request interceptor: attach Bearer token ───────────────────────────────
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers["Authorization"] = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: silent token refresh on 401 ─────────────────────
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      try {
        const newToken = await refreshAccessToken();
        original.headers["Authorization"] = `Bearer ${newToken}`;
        return api(original);
      } catch (refreshErr) {
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(err);
  }
);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SetupStatus { needs_setup: boolean; }

export interface SetupCompletePayload {
  account_name: string; workspace_name?: string;
  admin_email: string; admin_password: string; admin_display_name: string;
}

export interface LoginPayload { email: string; password: string; }

export interface LoginResult {
  access_token: string; refresh_token: string;
  user_id: string; email: string; display_name: string | null;
  account_id: string; is_account_admin: boolean;
}

export interface UserOut {
  id: string; email: string; display_name: string | null;
  account_id: string; status: string; account_role: string | null;
  is_account_admin?: boolean;
  last_login_at: string | null; created_at: string;
}

export interface WorkspaceMembershipOut {
  workspace_id: string; workspace_name: string | null;
  workspace_slug?: string | null;
  role_id: string; is_default: boolean;
}

export interface EntryPointResult {
  workspace_id: string | null; section: string; route: string;
}

export interface UserListItem extends UserOut {
  workspace_count: number;
}

export interface InviteOut {
  id: string; email: string; target_scope: string;
  target_workspace_id: string | null; proposed_account_role_id: string | null;
  proposed_workspace_role_id: string | null;
  status: string; expires_at: string; created_at: string; invite_url: string;
}

export interface InviteIn {
  email: string; target_scope: string;
  target_workspace_id?: string; proposed_account_role_id?: string;
  proposed_workspace_role_id?: string;
}

export interface GroupOut { id: string; name: string; source: string; member_count: number; created_at: string; }
export interface GroupMemberOut { user_id: string; email: string; display_name: string | null; added_at: string; }

export interface WorkspaceAdminOut {
  id: string; name: string; slug: string; status: string; member_count: number; created_at: string;
}

export interface WorkspaceMemberOut {
  assignment_id: string; user_id: string | null; group_id: string | null;
  principal_type: string; email: string | null; display_name: string | null;
  role_id: string; is_default: boolean; granted_at: string;
}

export interface AuditLogItem {
  id: string; actor_user_id: string | null; action: string;
  target_type: string; target_id: string | null; workspace_id: string | null;
  metadata: Record<string, unknown> | null; created_at: string;
}

export interface InviteDetailsOut {
  id: string; email: string; target_scope: string;
  target_workspace_id: string | null; proposed_account_role_id: string | null;
  proposed_workspace_role_id: string | null; status: string; expires_at: string;
}

// ── Setup ─────────────────────────────────────────────────────────────────────

export const fetchSetupStatus = async (): Promise<SetupStatus> =>
  (await api.get("/api/um/setup/status")).data;

export const completeSetup = async (payload: SetupCompletePayload): Promise<LoginResult> => {
  const { data } = await api.post("/api/um/setup/complete", payload);
  return { ...data, email: payload.admin_email, display_name: payload.admin_display_name, is_account_admin: true };
};

import { purgeAllClientState } from "./queryClient";

export const login = async (payload: LoginPayload): Promise<LoginResult> => {
  purgeAllClientState();
  return (await api.post("/api/um/auth/login", payload)).data;
};

export const logout = async (refreshToken: string): Promise<void> => {
  await api.post("/api/um/auth/logout", { refresh_token: refreshToken }).catch(() => {});
  clearSession();
  purgeAllClientState();
};

export const fetchMe = async (): Promise<UserOut> => (await api.get("/api/um/auth/me")).data;

export const fetchMyWorkspaces = async (): Promise<WorkspaceMembershipOut[]> =>
  (await api.get("/api/um/auth/workspaces")).data;

export const fetchEntryPoint = async (deepLinkWorkspaceId?: string): Promise<EntryPointResult> => {
  const params = deepLinkWorkspaceId ? { deep_link_workspace_id: deepLinkWorkspaceId } : {};
  return (await api.get("/api/um/entry-point", { params })).data;
};

// ── Account admin — users ──────────────────────────────────────────────────────

export const fetchUsers = async (): Promise<UserListItem[]> =>
  (await api.get("/api/um/account/users")).data;

export const createUser = async (payload: {
  email: string; display_name: string; password: string; account_role?: string;
}): Promise<UserListItem> =>
  (await api.post("/api/um/account/users", payload)).data;

export const suspendUser = async (userId: string) =>
  (await api.post(`/api/um/account/users/${userId}/suspend`)).data;

export const reactivateUser = async (userId: string) =>
  (await api.post(`/api/um/account/users/${userId}/reactivate`)).data;

export const deactivateUser = async (userId: string) =>
  (await api.post(`/api/um/account/users/${userId}/deactivate`)).data;

export const changeAccountRole = async (userId: string, roleId: string) =>
  (await api.patch(`/api/um/account/roles/${userId}`, { role_id: roleId })).data;

// ── Account admin — invites ────────────────────────────────────────────────────

export const fetchInvites = async (): Promise<InviteOut[]> =>
  (await api.get("/api/um/account/invites")).data;

export const createInvite = async (payload: InviteIn): Promise<InviteOut> =>
  (await api.post("/api/um/account/invites", payload)).data;

export const revokeInvite = async (inviteId: string) =>
  (await api.delete(`/api/um/account/invites/${inviteId}`)).data;

// ── Account admin — groups ─────────────────────────────────────────────────────

export const fetchGroups = async (): Promise<GroupOut[]> =>
  (await api.get("/api/um/account/groups")).data;

export const createGroup = async (name: string): Promise<GroupOut> =>
  (await api.post("/api/um/account/groups", { name })).data;

export const fetchGroupMembers = async (groupId: string): Promise<GroupMemberOut[]> =>
  (await api.get(`/api/um/account/groups/${groupId}/members`)).data;

export const addGroupMember = async (groupId: string, userId: string) =>
  (await api.post(`/api/um/account/groups/${groupId}/members`, { user_id: userId })).data;

export const removeGroupMember = async (groupId: string, userId: string) =>
  (await api.delete(`/api/um/account/groups/${groupId}/members/${userId}`)).data;

// ── Account admin — workspaces ─────────────────────────────────────────────────

export const fetchWorkspacesAdmin = async (): Promise<WorkspaceAdminOut[]> =>
  (await api.get("/api/um/account/workspaces")).data;

// ── Account admin — audit log ──────────────────────────────────────────────────

export const fetchAuditLog = async (params?: {
  actor_user_id?: string; action?: string; workspace_id?: string;
  limit?: number; offset?: number;
}): Promise<AuditLogItem[]> =>
  (await api.get("/api/um/account/audit-log", { params })).data;

// ── Workspace members ──────────────────────────────────────────────────────────

export const fetchWorkspaceMembers = async (workspaceId: string): Promise<WorkspaceMemberOut[]> =>
  (await api.get(`/api/um/workspaces/${workspaceId}/members`)).data;

export const inviteToWorkspace = async (
  workspaceId: string, emailOrUserId: string, roleId: string
) => (await api.post(`/api/um/workspaces/${workspaceId}/members/invite`, {
  email_or_user_id: emailOrUserId, role_id: roleId,
})).data;

export const createWorkspaceUser = async (
  workspaceId: string, payload: { email: string; display_name: string; password: string; role_id: string }
) => (await api.post(`/api/um/workspaces/${workspaceId}/members/create`, payload)).data;

export const updateMemberRole = async (workspaceId: string, userId: string, roleId: string) =>
  (await api.patch(`/api/um/workspaces/${workspaceId}/members/${userId}/role`, { role_id: roleId })).data;

export const removeWorkspaceMember = async (workspaceId: string, userId: string) =>
  (await api.delete(`/api/um/workspaces/${workspaceId}/members/${userId}`)).data;

export const setDefaultWorkspace = async (workspaceId: string) =>
  (await api.post(`/api/um/workspaces/${workspaceId}/set-default`)).data;

// ── Invites (public) ───────────────────────────────────────────────────────────

export const fetchInviteDetails = async (token: string): Promise<InviteDetailsOut> =>
  (await api.get(`/api/um/invites/${token}`)).data;

export const acceptInvite = async (
  token: string, payload: { password: string; confirm_password: string; display_name: string }
): Promise<LoginResult> => (await api.post(`/api/um/invites/${token}/accept`, payload)).data;

// ── React Query hooks ─────────────────────────────────────────────────────────

export const useSetupStatus = () =>
  useQuery({ queryKey: ["setup-status"], queryFn: fetchSetupStatus, staleTime: 30_000, retry: false });

export const useMe = () =>
  useQuery({ queryKey: ["um-me"], queryFn: fetchMe, retry: false, enabled: !!getToken() });

export const useMyWorkspaces = () =>
  useQuery({ queryKey: ["um-my-workspaces"], queryFn: fetchMyWorkspaces, staleTime: 30_000, retry: false, enabled: !!getToken() });

export const useEntryPoint = (deepLink?: string) =>
  useQuery({
    queryKey: ["um-entry-point", deepLink],
    queryFn: () => fetchEntryPoint(deepLink),
    retry: false, enabled: !!getToken(), staleTime: 60_000,
  });

export const useUsers = () =>
  useQuery({ queryKey: ["um-users"], queryFn: fetchUsers, staleTime: 30_000 });

export const useInvites = () =>
  useQuery({ queryKey: ["um-invites"], queryFn: fetchInvites, staleTime: 30_000 });

export const useGroups = () =>
  useQuery({ queryKey: ["um-groups"], queryFn: fetchGroups, staleTime: 30_000 });

export const useGroupMembers = (groupId: string) =>
  useQuery({ queryKey: ["um-group-members", groupId], queryFn: () => fetchGroupMembers(groupId), enabled: !!groupId });

export const useWorkspacesAdmin = () =>
  useQuery({ queryKey: ["um-workspaces-admin"], queryFn: fetchWorkspacesAdmin, staleTime: 30_000 });

export const useAuditLog = (params?: Parameters<typeof fetchAuditLog>[0]) =>
  useQuery({ queryKey: ["um-audit-log", params], queryFn: () => fetchAuditLog(params), staleTime: 15_000 });

export const useWorkspaceMembers = (workspaceId: string) =>
  useQuery({
    queryKey: ["um-ws-members", workspaceId],
    queryFn: () => fetchWorkspaceMembers(workspaceId),
    enabled: !!workspaceId,
  });

export const useInviteDetails = (token: string) =>
  useQuery({ queryKey: ["um-invite", token], queryFn: () => fetchInviteDetails(token), enabled: !!token, retry: false });

// ── Mutations ─────────────────────────────────────────────────────────────────

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: createUser, onSuccess: () => qc.invalidateQueries({ queryKey: ["um-users"] }) });
};

export const useSuspendUser = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: suspendUser, onSuccess: () => qc.invalidateQueries({ queryKey: ["um-users"] }) });
};

export const useReactivateUser = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: reactivateUser, onSuccess: () => qc.invalidateQueries({ queryKey: ["um-users"] }) });
};

export const useCreateInvite = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: createInvite, onSuccess: () => qc.invalidateQueries({ queryKey: ["um-invites"] }) });
};

export const useRevokeInvite = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: revokeInvite, onSuccess: () => qc.invalidateQueries({ queryKey: ["um-invites"] }) });
};

export const useCreateGroup = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (name: string) => createGroup(name), onSuccess: () => qc.invalidateQueries({ queryKey: ["um-groups"] }) });
};

export const useInviteToWorkspace = (workspaceId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ emailOrUserId, roleId }: { emailOrUserId: string; roleId: string }) =>
      inviteToWorkspace(workspaceId, emailOrUserId, roleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["um-ws-members", workspaceId] }),
  });
};

export const useCreateWorkspaceUser = (workspaceId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; display_name: string; password: string; role_id: string }) =>
      createWorkspaceUser(workspaceId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["um-ws-members", workspaceId] }),
  });
};

export const useUpdateMemberRole = (workspaceId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      updateMemberRole(workspaceId, userId, roleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["um-ws-members", workspaceId] }),
  });
};

export const useRemoveWorkspaceMember = (workspaceId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => removeWorkspaceMember(workspaceId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["um-ws-members", workspaceId] }),
  });
};

export const useAcceptInvite = (token: string) =>
  useMutation({
    mutationFn: (payload: { password: string; confirm_password: string; display_name: string }) =>
      acceptInvite(token, payload),
  });
