/**
 * React Query hooks over the governance API.
 *
 * Grant and revoke both invalidate the grant list *and* the effective-permission
 * view for the same securable: a grant that does not immediately show up in
 * "what can this person do" is indistinguishable, to an administrator, from one
 * that silently failed.
 */
import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useGroups, useWorkspaceMembers } from '@/lib/userManagerApi';

import {
  createGrant,
  fetchEffectivePermissions,
  fetchGrants,
  fetchOwner,
  fetchPrincipalGrants,
  fetchPrivilegeVocabulary,
  revokeGrant,
  transferOwner,
} from '../governanceApi';
import type {
  GrantInput,
  OwnerInput,
  PrincipalOption,
  Privilege,
  RevokeInput,
  SecurableRef,
} from '../governanceTypes';

// ── Query keys ───────────────────────────────────────────────────────────────

export const governanceKeys = {
  privileges: ['governance', 'privileges'] as const,
  grants: (ref: SecurableRef) =>
    ['governance', 'grants', ref.securable_type, ref.name] as const,
  principalGrants: (principalId: string) =>
    ['governance', 'principal-grants', principalId] as const,
  owner: (ref: SecurableRef) =>
    ['governance', 'owner', ref.securable_type, ref.name] as const,
  effective: (ref: SecurableRef, principalId?: string) =>
    ['governance', 'effective', ref.securable_type, ref.name, principalId ?? 'me'] as const,
};

// ── Vocabulary ───────────────────────────────────────────────────────────────

/** The privilege vocabulary. Rarely changes, so it is cached for the session. */
export function usePrivilegeVocabulary() {
  return useQuery({
    queryKey: governanceKeys.privileges,
    queryFn: fetchPrivilegeVocabulary,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/** The privileges that may be granted on one securable type, in a stable order. */
export function useApplicablePrivileges(securableType: SecurableRef['securable_type']) {
  const { data } = usePrivilegeVocabulary();
  return useMemo<Privilege[]>(
    () => data?.applicable?.[securableType] ?? [],
    [data, securableType],
  );
}

// ── Grants ───────────────────────────────────────────────────────────────────

/**
 * Grants made directly on one object.
 *
 * Requires MANAGE, so this 403s or 404s for most callers. Pass `enabled: false`
 * — via the `enabled` argument — when the caller is known not to hold it, rather
 * than letting the panel fire a request that is expected to fail.
 */
export function useGrants(ref: SecurableRef, enabled = true) {
  return useQuery({
    queryKey: governanceKeys.grants(ref),
    queryFn: () => fetchGrants(ref),
    enabled: enabled && Boolean(ref.name),
    retry: false,
  });
}

export function usePrincipalGrants(principalId: string, enabled = true) {
  return useQuery({
    queryKey: governanceKeys.principalGrants(principalId),
    queryFn: () => fetchPrincipalGrants(principalId),
    enabled: enabled && Boolean(principalId),
    retry: false,
  });
}

export function useCreateGrant(ref: SecurableRef) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GrantInput) => createGrant(body),
    onSuccess: () => invalidateFor(qc, ref),
  });
}

export function useRevokeGrant(ref: SecurableRef) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RevokeInput) => revokeGrant(body),
    onSuccess: () => invalidateFor(qc, ref),
  });
}

// ── Ownership ────────────────────────────────────────────────────────────────

export function useOwner(ref: SecurableRef, enabled = true) {
  return useQuery({
    queryKey: governanceKeys.owner(ref),
    queryFn: () => fetchOwner(ref),
    enabled: enabled && Boolean(ref.name),
    retry: false,
  });
}

export function useTransferOwner(ref: SecurableRef) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OwnerInput) => transferOwner(body),
    onSuccess: () => invalidateFor(qc, ref),
  });
}

// ── Effective permissions ────────────────────────────────────────────────────

export function useEffectivePermissions(
  ref: SecurableRef,
  principalId?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: governanceKeys.effective(ref, principalId),
    queryFn: () => fetchEffectivePermissions(ref, principalId),
    enabled: enabled && Boolean(ref.name),
    retry: false,
  });
}

/**
 * What the current user may do on one securable, for gating the UI.
 *
 * Returns `has(privilege)`, which is false until the answer arrives. Hiding an
 * action the user turns out to have is a smaller harm than offering one that
 * fails on click, and the backend is the real check either way — this only
 * decides what is worth showing.
 */
export function useMyPrivileges(
  securableType: SecurableRef['securable_type'],
  name: string,
) {
  const ref = useMemo<SecurableRef>(
    () => ({ securable_type: securableType, name }),
    [securableType, name],
  );
  const query = useEffectivePermissions(ref, undefined, Boolean(name));
  const privileges = query.data?.privileges;

  const has = useMemo(() => {
    const held = new Set<string>(privileges ?? []);
    return (privilege: Privilege) => held.has(privilege);
  }, [privileges]);

  return { has, isLoading: query.isLoading, isOwner: query.data?.is_owner ?? false };
}

// ── Principals ───────────────────────────────────────────────────────────────

/**
 * Grantee candidates for the picker: workspace members and account groups.
 *
 * The governance API takes a principal id and does not resolve names, so the
 * mapping from id to something a human recognises is assembled here. Groups are
 * account-scoped and only load for an admin, so a failure there is not fatal —
 * the picker simply offers users only.
 */
export function usePrincipalOptions() {
  const workspace = useWorkspaceContext();
  const members = useWorkspaceMembers(workspace.id);
  const groups = useGroups();

  const options = useMemo<PrincipalOption[]>(() => {
    const result: PrincipalOption[] = [];

    for (const member of members.data ?? []) {
      const id = member.user_id ?? member.group_id;
      if (!id) continue;
      const isGroup = member.principal_type === 'group';
      result.push({
        id,
        type: isGroup ? 'group' : 'user',
        label: member.display_name || member.email || id,
        detail: isGroup ? 'Workspace group' : member.email ?? undefined,
      });
    }

    // Account groups that are not already workspace members can still be
    // granted on: a grant is what gives them their access in the first place.
    const seen = new Set(result.map((option) => option.id));
    for (const group of groups.data ?? []) {
      if (seen.has(group.id)) continue;
      result.push({
        id: group.id,
        type: 'group',
        label: group.name,
        detail: `${group.member_count} member${group.member_count === 1 ? '' : 's'}`,
      });
    }

    return result.sort((a, b) => a.label.localeCompare(b.label));
  }, [members.data, groups.data]);

  return {
    options,
    isLoading: members.isLoading,
    // Groups failing to load degrades the picker rather than breaking it.
    error: members.error,
  };
}

/** Resolve a principal id to a display name, falling back to the raw id. */
export function usePrincipalLabels(): (principalId: string) => string {
  const { options } = usePrincipalOptions();
  return useMemo(() => {
    const byId = new Map(options.map((option) => [option.id, option.label]));
    return (principalId: string) => byId.get(principalId) ?? principalId;
  }, [options]);
}

// ── Internals ────────────────────────────────────────────────────────────────

function invalidateFor(
  qc: ReturnType<typeof useQueryClient>,
  ref: SecurableRef,
): void {
  qc.invalidateQueries({ queryKey: governanceKeys.grants(ref) });
  qc.invalidateQueries({ queryKey: governanceKeys.owner(ref) });
  // Every principal's effective view on this object, not just the caller's.
  qc.invalidateQueries({
    queryKey: ['governance', 'effective', ref.securable_type, ref.name],
  });
  qc.invalidateQueries({ queryKey: ['governance', 'principal-grants'] });
}
