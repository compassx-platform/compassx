/**
 * What a principal can actually do on an object, and why.
 *
 * Shown only after the user opens the Effective access disclosure. Denials stay
 * in the table: an empty allow-list would not say where the chain broke.
 */
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

import { useEffectivePermissions, usePrincipalOptions } from '../hooks/useGovernance';
import type { SecurableRef } from '../governanceTypes';

interface Props {
  securable: SecurableRef;
  /** Only a workspace admin may inspect a principal other than themselves. */
  canInspectOthers?: boolean;
}

export default function EffectivePermissions({
  securable,
  canInspectOthers = false,
}: Props) {
  const principals = usePrincipalOptions();
  const [principalId, setPrincipalId] = useState<string>('');

  const query = useEffectivePermissions(securable, principalId || undefined);
  const result = query.data;

  return (
    <div className="gov-effective">
      {canInspectOthers && (
        <label className="gov-effective-picker">
          <span className="uc-field-label">Check for</span>
          <span className="gov-select-wrap">
            <select
              value={principalId}
              onChange={(event) => setPrincipalId(event.target.value)}
            >
              <option value="">Me</option>
              {principals.options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </span>
        </label>
      )}

      {query.isLoading && <div className="uc-empty-inline">Resolving…</div>}

      {query.isError && (
        <div className="uc-empty-inline">
          Could not resolve effective access for this object.
        </div>
      )}

      {result && (
        <div className="uc-columns-table-wrap">
          <table className="uc-columns-table gov-effective-table">
            <thead>
              <tr>
                <th>Privilege</th>
                <th>Access</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.decisions).map(([privilege, reason]) => {
                const allowed = result.privileges.includes(privilege as never);
                return (
                  <tr key={privilege} className={allowed ? undefined : 'gov-row-denied'}>
                    <td className="gov-privilege-cell">{privilege}</td>
                    <td className="gov-access-cell">
                      <span className={allowed ? 'gov-access-allow' : 'gov-access-deny'}>
                        {allowed ? 'Allowed' : 'Denied'}
                      </span>
                      <span className="gov-reason-cell">{humanizeReason(reason)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/**
 * The resolver's reasons are machine tokens from `Decision` in
 * `backend/app/governance/resolver.py`, optionally followed by `: detail`.
 * Unknown tokens pass through tidied rather than being hidden, so a reason
 * added to the backend later still reads sensibly here.
 */
function humanizeReason(reason: string): string {
  const [token, ...rest] = reason.split(':');
  const detail = rest.join(':').trim();
  const known: Record<string, string> = {
    account_admin: 'Granted by account administrator role',
    workspace_admin: 'Granted by workspace administrator role',
    owner: 'Granted by ownership',
    direct_grant: 'Granted directly on this object',
    inherited_grant: 'Inherited from a parent',
    no_workspace_access: 'No access to this workspace',
    use_chain_broken: 'Blocked — missing USE on a parent container',
    agent_ceiling_exceeded: "Blocked — the agent's owner does not have this access",
    no_grant: 'No grant',
  };
  const label = known[token.trim()] ?? token.trim().replace(/_/g, ' ');
  return detail ? `${label} — ${detail}` : label;
}
