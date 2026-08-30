/**
 * The Permissions tab for one securable: owner, grants, and effective access.
 *
 * Access to the grant list itself requires MANAGE, so the panel does not simply
 * fire the request and render whatever error comes back. It asks the effective
 * endpoint first — which any caller who can see the object may read — and uses
 * the answer to decide whether to load grants at all. A user who cannot manage
 * the object sees their own effective access and is told who to ask, rather
 * than an error they can do nothing about.
 */
import { useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';

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

/** One row per principal, with their privileges gathered together. */
interface GrantGroup {
  principalId: string;
  principalType: string;
  privileges: string[];
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
  const [pendingRevoke, setPendingRevoke] = useState<GrantGroup | null>(null);

  const groups = useMemo(() => groupGrants(grants.data ?? []), [grants.data]);
  const grantedIds = useMemo(
    () => new Set(groups.map((group) => group.principalId)),
    [groups],
  );

  const labelFor = (principalId: string) =>
    principals.options.find((option) => option.id === principalId)?.label ?? principalId;

  const handleRevoke = () => {
    if (!pendingRevoke) return;
    revoke.mutate(
      {
        ...securable,
        principal_id: pendingRevoke.principalId,
        privileges: pendingRevoke.privileges,
      },
      {
        onSuccess: () => {
          toast.success(`Revoked access for ${labelFor(pendingRevoke.principalId)}.`);
          setPendingRevoke(null);
        },
        onError: (error) => {
          toast.error(errorMessage(error, 'Could not revoke access.'));
          setPendingRevoke(null);
        },
      },
    );
  };

  return (
    <div className="gov-panel">
      <div className="uc-detail-card">
        <OwnerBadge securable={securable} canManage={canManage} />
      </div>

      {canManage && (
        <div className="uc-detail-card">
          <div className="gov-section-header">
            <div>
              <div className="uc-detail-title">Grants on this {securableType}</div>
              <p className="gov-field-help">
                Direct grants only. Access inherited from a parent {parentHint(securableType)}
                is not listed here — use Effective access below to see the whole picture.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsGranting(true)}
            >
              <Plus size={14} aria-hidden="true" /> Grant access
            </button>
          </div>

          {grants.isLoading && <div className="uc-empty-inline">Loading grants…</div>}

          {!grants.isLoading && groups.length === 0 && (
            <div className="uc-empty-state">
              <p>No direct grants on this {securableType}.</p>
              <p className="gov-field-help">
                Anyone with access reaches it through ownership, a parent, or an
                administrator role.
              </p>
            </div>
          )}

          {groups.length > 0 && (
            <div className="uc-table-responsive">
              <table className="uc-columns-table">
                <thead>
                  <tr>
                    <th>Principal</th>
                    <th>Privileges</th>
                    <th>Expires</th>
                    <th style={{ width: '48px' }}>
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => (
                    <tr key={group.principalId}>
                      <td>
                        <span className="gov-principal-name">{labelFor(group.principalId)}</span>
                        <span className="gov-principal-detail">{group.principalType}</span>
                      </td>
                      <td>
                        <span className="uc-tags-list">
                          {group.privileges.map((privilege) => (
                            <span key={privilege} className="uc-chip">{privilege}</span>
                          ))}
                        </span>
                      </td>
                      <td>
                        {group.expiresAt
                          ? new Date(group.expiresAt).toLocaleDateString()
                          : <span className="gov-owner-none">Never</span>}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="uc-icon-btn"
                          aria-label={`Revoke all access for ${labelFor(group.principalId)}`}
                          onClick={() => setPendingRevoke(group)}
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
        </div>
      )}

      <div className="uc-detail-card">
        <EffectivePermissions securable={securable} canInspectOthers={isWorkspaceAdmin} />
      </div>

      {!canManage && !effective.isLoading && (
        <p className="gov-field-help">
          Managing access to this {securableType} requires the MANAGE privilege.
          Ask its owner to grant it.
        </p>
      )}

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
          message={`Remove ${pendingRevoke.privileges.join(', ')} from ${labelFor(pendingRevoke.principalId)} on ${name}? They may still reach it through a parent or an administrator role.`}
          confirmLabel="Revoke"
          isLoading={revoke.isPending}
          onConfirm={handleRevoke}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </div>
  );
}

/** Collapse the per-privilege rows the API returns into one row per principal. */
function groupGrants(grants: Grant[]): GrantGroup[] {
  const byPrincipal = new Map<string, GrantGroup>();
  for (const grant of grants) {
    if (!grant.privilege) continue;
    const existing = byPrincipal.get(grant.principal_id);
    if (existing) {
      existing.privileges.push(grant.privilege);
      // Show the soonest expiry, since that is when access starts to change.
      if (grant.expires_at && (!existing.expiresAt || grant.expires_at < existing.expiresAt)) {
        existing.expiresAt = grant.expires_at;
      }
    } else {
      byPrincipal.set(grant.principal_id, {
        principalId: grant.principal_id,
        principalType: grant.principal_type,
        privileges: [grant.privilege],
        expiresAt: grant.expires_at,
      });
    }
  }
  for (const group of byPrincipal.values()) group.privileges.sort();
  return Array.from(byPrincipal.values());
}

function parentHint(securableType: SecurableType): string {
  return securableType === 'catalog' ? 'workspace role ' : 'catalog or schema ';
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}
