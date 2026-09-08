/**
 * Types mirroring the governance API (`backend/app/governance/routes.py`).
 *
 * The privilege vocabulary is deliberately *not* hardcoded here beyond the
 * union type: `GET /governance/privileges` serves the authoritative list, and
 * the grant dialog builds itself from that response so the UI cannot offer a
 * privilege the resolver would refuse to honour.
 */

export type SecurableType =
  | 'catalog'
  | 'schema'
  | 'table'
  | 'volume'
  | 'notebook'
  | 'dashboard'
  | 'query'
  | 'tool'
  | 'job'
  | 'agent'
  | 'compute'
  | 'connection';

export type Privilege =
  | 'USE'
  | 'BROWSE'
  | 'SELECT'
  | 'MODIFY'
  | 'CREATE'
  | 'EXECUTE'
  | 'EDIT'
  | 'USE_COMPUTE'
  | 'MANAGE';

export type PrincipalType = 'user' | 'group' | 'service';

/**
 * How the API addresses a governed object: a dotted path
 * (`main.sales.orders`) for catalog-path securables, the object id for jobs,
 * agents, compute, and connections.
 */
export interface SecurableRef {
  securable_type: SecurableType;
  name: string;
}

export interface PrivilegeVocabulary {
  privileges: Privilege[];
  /** Named bundles — administrators think in roles, not individual privileges. */
  bundles: Record<string, Privilege[]>;
  /** Which privileges are meaningful on which securable type. */
  applicable: Record<SecurableType, Privilege[]>;
}

export interface Grant {
  id: string;
  principal_id: string;
  principal_type: string;
  securable_type: string;
  securable_name: string;
  privilege: string | null;
  granted_by: string | null;
  granted_at: string;
  expires_at: string | null;
}

export interface GrantInput extends SecurableRef {
  principal_id: string;
  principal_type: PrincipalType;
  /** Privilege names and/or bundle names, mixed freely. */
  privileges: string[];
  expires_at?: string | null;
}

export interface RevokeInput extends SecurableRef {
  principal_id: string;
  privileges: string[];
}

export interface Owner {
  securable_type: string;
  securable_name: string;
  owner_principal_id: string;
  owner_principal_type: string;
  assigned_at: string;
}

export interface OwnerInput extends SecurableRef {
  owner_principal_id: string;
  owner_principal_type: 'user' | 'group';
}

/** What a principal can actually do on an object, and why. */
export interface EffectivePermissions {
  principal_id: string;
  securable_type: string;
  securable_name: string;
  is_owner: boolean;
  /** Privileges held here, after the USE chain. */
  privileges: Privilege[];
  /** Per-privilege resolution reason, including for denials. */
  decisions: Record<string, string>;
}

/**
 * A grantee candidate. Assembled in the frontend from workspace members and
 * account groups, because the governance API takes a principal id and does not
 * itself resolve names.
 */
export interface PrincipalOption {
  id: string;
  type: PrincipalType;
  label: string;
  /** Secondary line in the picker — email for users, member count for groups. */
  detail?: string;
}
