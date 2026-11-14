/**
 * The Permissions tab for one securable.
 *
 * Access to the grant list itself requires MANAGE, so the panel asks the
 * effective endpoint first — which any caller who can see the object may read —
 * and only then loads grants. A user who cannot manage the object sees the
 * owner and a single sentence, and can open effective access, rather than an
 * error they can do nothing about.
 */
import { useMemo, useState } from 'react';
import { ChevronRight, Trash2 } from 'lucide-react';

import ConfirmDialog from '@/components/common/ConfirmDialog';
import { useToast } from '@/lib/toast';

import {
  useEffectivePermissions,
  useGrants,
  usePrincipalOptions,
  useRevokeGrant,
} from '../hooks/useGovernance';
import type { Grant, SecurableRef, SecurableType } from '../governanceTypes';
import EffectivePermissions from './EffectivePermissions';
import GrantDialog from './GrantDialog';
import OwnerBadge from './OwnerBadge';
import '../governance.css';

interface Props {
  securableType: SecurableType;
  /** Dotted path for catalog-path securables; the object id otherwise. */
  name: string;
  /** Workspace admins may inspect another principal's effective access. */
  isWorkspaceAdmin?: boolean;
}

/** One table row: a single privilege on a single principal. */
interface GrantRow {
  id: string;
  principalId: string;
  principalType: string;
  privilege: string;
  /** Quieter when the grant was made on a parent, not on this object. */
  inherited: boolean;
  sourceLabel: string;
  expiresAt: string | null;
}

export default function PermissionsPanel({
  securableType,
  name,
  isWorkspaceAdmin = false,
}: Props) {
  const toast = useToast();
  const securable = useMemo<SecurableRef>(
    () => ({ securable_type: securableType, name }),
    [securableType, name],
  );

  const principals = usePrincipalOptions();
  const effective = useEffectivePermissions(securable);
  const canManage = effective.data?.privileges.includes('MANAGE') ?? false;

  // Only load grants once MANAGE is known to be held: the endpoint refuses
  // anyone else, and a failed request here would render as a broken tab.
  const grants = useGrants(securable, canManage);
  const revoke = useRevokeGrant(securable);

  const [isGranting, setIsGranting] = useState(false);
  const [pendingRevoke, setPendingRevoke] = useState<GrantRow | null>(null);

  const rows = useMemo(() => {
    const byId = new Map(principals.options.map((option) => [option.id, option.label]));
    const labelFor = (principalId: string) => byId.get(principalId) ?? principalId;
    const list = toGrantRows(grants.data ?? [], securable);
    return list.sort((a, b) => {
      const byName = labelFor(a.principalId).localeCompare(labelFor(b.principalId));
      if (byName !== 0) return byName;
      return a.privilege.localeCompare(b.privilege);
    });
  }, [grants.data, principals.options, securable]);

  const labelFor = (principalId: string) =>
    principals.options.find((option) => option.id === principalId)?.label ?? principalId;

  const grantedIds = useMemo(
    () => new Set(rows.map((row) => row.principalId)),
    [rows],
  );

  const handleRevoke = () => {
    if (!pendingRevoke) return;
    const target = pendingRevoke;
    revoke.mutate(
      {
        ...securable,
        principal_id: target.principalId,
        privileges: [target.privilege],
      },
      {
        onSuccess: () => {
          toast.success(`Revoked access for ${labelFor(target.principalId)}.`);
          setPendingRevoke(null);
        },
        onError: (error) => {
          toast.error(errorMessage(error, 'Could not revoke access.'));
          setPendingRevoke(null);
        },
      },
    );
  };

  const loading = effective.isLoading || (canManage && grants.isLoading);

  return (
    <div className="gov-panel">
      <div className="gov-header">
        <div className="gov-header-main">
          <span className="gov-object-name">{name}</span>
          <OwnerBadge securable={securable} canManage={canManage} />
        </div>
        {canManage && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setIsGranting(true)}
          >
            Grant
          </button>
        )}
      </div>

      {loading && <p className="gov-quiet">Loading grants…</p>}

      {canManage && !grants.isLoading && grants.isError && (
        <p className="gov-quiet">Could not load grants.</p>
      )}

      {canManage && !grants.isLoading && !grants.isError && rows.length === 0 && (
        <p className="gov-quiet">No grants on this {securableType}.</p>
      )}

      {canManage && rows.length > 0 && (
        <div className="uc-columns-table-wrap">
          <table className="uc-columns-table">
            <thead>
              <tr>
                <th>Principal</th>
                <th>Privilege</th>
                <th>Granted</th>
                <th style={{ width: '48px' }}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className={row.inherited ? 'gov-row-inherited' : undefined}>
                  <td>
                    <span className="gov-principal-name">{labelFor(row.principalId)}</span>
                    <span className="gov-principal-meta">{row.principalType}</span>
                  </td>
                  <td className="gov-privilege-cell">{row.privilege}</td>
                  <td>
                    <span className="gov-source">{row.sourceLabel}</span>
                    {row.expiresAt && (
                      <span className="gov-source-meta">
                        Expires {new Date(row.expiresAt).toLocaleDateString()}
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="uc-icon-btn"
                      aria-label={`Revoke ${row.privilege} for ${labelFor(row.principalId)}`}
                      onClick={() => setPendingRevoke(row)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!canManage && !effective.isLoading && (
        <p className="gov-quiet">
          Managing access to this {securableType} requires the MANAGE privilege.
          Ask its owner to grant it.
        </p>
      )}

      <details className="gov-disclosure">
        <summary>
          <ChevronRight size={14} className="gov-disclosure-chevron" aria-hidden="true" />
          Effective access
        </summary>
        <EffectivePermissions securable={securable} canInspectOthers={isWorkspaceAdmin} />
      </details>

      {isGranting && (
        <GrantDialog
          securable={securable}
          existingIds={grantedIds}
          onClose={() => setIsGranting(false)}
        />
      )}

      {pendingRevoke && (
        <ConfirmDialog
          title="Revoke access"
          message={`Remove ${pendingRevoke.privilege} from ${labelFor(pendingRevoke.principalId)} on ${name}? They may still reach it through a parent or an administrator role.`}
          confirmLabel="Revoke"
          isLoading={revoke.isPending}
          onConfirm={handleRevoke}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </div>
  );
}

/**
 * The grants endpoint returns grants on the requested object. A row whose
 * securable is a different object (a parent path) is inherited and rendered
 * quieter. Workspace securables are addressed as `type:id` in the response
 * and as the bare id in this panel; those are the same object.
 */
function toGrantRows(grants: Grant[], securable: SecurableRef): GrantRow[] {
  const rows: GrantRow[] = [];
  for (const grant of grants) {
    const privilege = grant.privilege;
    if (!privilege) continue;
    const onThisObject =
      grant.securable_name === securable.name
      || grant.securable_name === `${securable.securable_type}:${securable.name}`;
    rows.push({
      id: grant.id,
      principalId: grant.principal_id,
      principalType: grant.principal_type,
      privilege,
      inherited: !onThisObject,
      sourceLabel: onThisObject ? 'This object' : `Inherited from ${grant.securable_name}`,
      expiresAt: grant.expires_at,
    });
  }
  return rows;
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}
