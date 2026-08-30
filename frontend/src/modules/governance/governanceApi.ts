/**
 * Governance API client — grants, ownership, and effective-permission inspection.
 *
 * All calls use the shared axios instance from `@/lib/api`, so the workspace is
 * taken from the `X-Workspace-Slug` header the interceptor attaches rather than
 * from a parameter the caller chooses.
 */
import api from '@/lib/api';
import type {
  EffectivePermissions,
  Grant,
  GrantInput,
  Owner,
  OwnerInput,
  PrivilegeVocabulary,
  RevokeInput,
  SecurableRef,
} from './governanceTypes';

const BASE = '/governance';

// ── Vocabulary ───────────────────────────────────────────────────────────────

/**
 * The privilege vocabulary. Served by the backend rather than duplicated here
 * so the two cannot drift into offering privileges the resolver will not honour.
 */
export async function fetchPrivilegeVocabulary(): Promise<PrivilegeVocabulary> {
  const res = await api.get(`${BASE}/privileges`);
  return res.data;
}

// ── Grants ───────────────────────────────────────────────────────────────────

/** Grants made directly on one object. Requires MANAGE on it. */
export async function fetchGrants(ref: SecurableRef): Promise<Grant[]> {
  const res = await api.get(`${BASE}/grants`, {
    params: { securable_type: ref.securable_type, name: ref.name },
  });
  return res.data;
}

/** Everything one principal holds — the access review for a user or group. */
export async function fetchPrincipalGrants(principalId: string): Promise<Grant[]> {
  const res = await api.get(`${BASE}/principals/${encodeURIComponent(principalId)}/grants`);
  return res.data;
}

/** Grant privileges. Idempotent — re-granting returns an empty list. */
export async function createGrant(body: GrantInput): Promise<Grant[]> {
  const res = await api.post(`${BASE}/grants`, body);
  return res.data;
}

/**
 * Revoke privileges. POST rather than DELETE because the target is a
 * (principal, securable, privileges) triple that does not fit a path.
 */
export async function revokeGrant(body: RevokeInput): Promise<{ revoked: number }> {
  const res = await api.post(`${BASE}/grants/revoke`, body);
  return res.data;
}

// ── Ownership ────────────────────────────────────────────────────────────────

/**
 * Who owns an object. Readable by anyone who can see it: the owner is who you
 * ask for access, so hiding it would leave a denied user with nowhere to go.
 */
export async function fetchOwner(ref: SecurableRef): Promise<Owner | null> {
  const res = await api.get(`${BASE}/owner`, {
    params: { securable_type: ref.securable_type, name: ref.name },
  });
  return res.data ?? null;
}

/** Transfer ownership. Requires MANAGE, which an owner holds implicitly. */
export async function transferOwner(body: OwnerInput): Promise<Owner> {
  const res = await api.put(`${BASE}/owner`, body);
  return res.data;
}

// ── Effective permissions ────────────────────────────────────────────────────

/**
 * What a principal can actually do here, and why — the debugging endpoint.
 * Omit `principalId` for the caller; inspecting another requires workspace admin.
 */
export async function fetchEffectivePermissions(
  ref: SecurableRef,
  principalId?: string,
): Promise<EffectivePermissions> {
  const res = await api.get(`${BASE}/effective`, {
    params: {
      securable_type: ref.securable_type,
      name: ref.name,
      ...(principalId ? { principal_id: principalId } : {}),
    },
  });
  return res.data;
}
