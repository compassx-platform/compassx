/**
 * Grant privileges on one securable.
 *
 * Two ways to choose, because administrators think in roles but occasionally
 * need a single privilege: a bundle picker ("Viewer", "Contributor") that
 * expands to a privilege set, and the raw checkboxes underneath. The privilege
 * list comes from `GET /governance/privileges` filtered to what is applicable
 * to this securable type, so the dialog cannot offer a grant the backend would
 * reject as unevaluatable (SELECT on a job, say).
 */
import { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';

import { useToast } from '@/lib/toast';

import {
  useApplicablePrivileges,
  useCreateGrant,
  usePrincipalOptions,
  usePrivilegeVocabulary,
} from '../hooks/useGovernance';
import type { PrincipalOption, Privilege, SecurableRef } from '../governanceTypes';
import PrincipalPicker from './PrincipalPicker';

interface Props {
  securable: SecurableRef;
  /** Principals already holding a grant here — marked in the picker. */
  existingIds?: ReadonlySet<string>;
  onClose: () => void;
}

/** What each privilege means on this object, in the terms a grantee would use. */
const PRIVILEGE_HELP: Record<Privilege, string> = {
  USE: 'Traverse into this container. Required to reach anything inside it, but grants no sight of the contents on its own.',
  BROWSE: 'See that the object exists and read its metadata.',
  SELECT: 'Read the data or file contents.',
  MODIFY: 'Insert, update, and delete data. Does not allow dropping the object.',
  CREATE: 'Create children inside it. The creator owns what they create.',
  EXECUTE: 'Run it.',
  EDIT: 'Change its definition.',
  USE_COMPUTE: 'Attach to it and run work through it.',
  MANAGE: 'Full control, including granting access to others and deleting it.',
};

export default function GrantDialog({ securable, existingIds, onClose }: Props) {
  const toast = useToast();
  const vocabulary = usePrivilegeVocabulary();
  const applicable = useApplicablePrivileges(securable.securable_type);
  const principals = usePrincipalOptions();
  const createGrant = useCreateGrant(securable);

  const [principal, setPrincipal] = useState<PrincipalOption | null>(null);
  const [selected, setSelected] = useState<Set<Privilege>>(new Set());
  const [expiresAt, setExpiresAt] = useState('');

  /**
   * Bundles narrowed to this securable. "Viewer" includes SELECT, which means
   * nothing on a job, so each bundle is intersected with what applies here and
   * one that empties out is not offered at all.
   */
  const bundles = useMemo(() => {
    const all = vocabulary.data?.bundles ?? {};
    const applicableSet = new Set(applicable);
    return Object.entries(all)
      .map(([name, privileges]) => ({
        name,
        privileges: privileges.filter((privilege) => applicableSet.has(privilege)),
      }))
      .filter((bundle) => bundle.privileges.length > 0);
  }, [vocabulary.data, applicable]);

  // A bundle is "active" when its privileges are exactly what is selected, so
  // clicking it twice does not appear to do nothing.
  const activeBundle = useMemo(() => {
    for (const bundle of bundles) {
      if (
        bundle.privileges.length === selected.size &&
        bundle.privileges.every((privilege) => selected.has(privilege))
      ) {
        return bundle.name;
      }
    }
    return null;
  }, [bundles, selected]);

  // Close on Escape, like every other modal in the app.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const togglePrivilege = (privilege: Privilege) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(privilege)) next.delete(privilege);
      else next.add(privilege);
      return next;
    });
  };

  const applyBundle = (privileges: Privilege[]) => {
    setSelected(new Set(privileges));
  };

  const canSubmit = Boolean(principal) && selected.size > 0 && !createGrant.isPending;

  const handleSubmit = () => {
    if (!principal || selected.size === 0) return;
    createGrant.mutate(
      {
        ...securable,
        principal_id: principal.id,
        principal_type: principal.type,
        privileges: Array.from(selected),
        // A date input yields a local calendar day; send it as an instant so
        // the backend does not have to guess a timezone.
        expires_at: expiresAt ? new Date(`${expiresAt}T23:59:59`).toISOString() : null,
      },
      {
        onSuccess: (granted) => {
          if (granted.length === 0) {
            toast.info(`${principal.label} already had those privileges.`);
          } else {
            toast.success(`Granted ${granted.length} privilege${granted.length === 1 ? '' : 's'} to ${principal.label}.`);
          }
          onClose();
        },
        onError: (error) => toast.error(errorMessage(error, 'Could not grant access.')),
      },
    );
  };

  return (
    <div className="uc-modal-overlay" onClick={onClose}>
      <div
        className="uc-modal gov-grant-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gov-grant-title"
      >
        <div className="uc-modal-header">
          <h3 id="gov-grant-title" style={{ margin: 0 }}>Grant access</h3>
          <button type="button" className="uc-icon-btn" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="uc-modal-body">
          <p className="gov-modal-subtitle">
            On <code>{securable.name}</code> ({securable.securable_type})
          </p>

          <div className="uc-field">
            <label className="uc-field-label">Grant to</label>
            <PrincipalPicker
              options={principals.options}
              value={principal}
              onChange={setPrincipal}
              isLoading={principals.isLoading}
              existingIds={existingIds}
            />
          </div>

          {bundles.length > 0 && (
            <div className="uc-field">
              <label className="uc-field-label">Preset</label>
              <div className="gov-bundle-row">
                {bundles.map((bundle) => (
                  <button
                    key={bundle.name}
                    type="button"
                    className={`gov-bundle-chip${activeBundle === bundle.name ? ' is-active' : ''}`}
                    onClick={() => applyBundle(bundle.privileges)}
                    title={bundle.privileges.join(', ')}
                  >
                    {bundle.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="uc-field">
            <label className="uc-field-label">Privileges</label>
            {vocabulary.isLoading && <div className="uc-empty-inline">Loading privileges…</div>}
            {vocabulary.isError && (
              <div className="uc-empty-inline">Could not load the privilege list.</div>
            )}
            <div className="gov-privilege-grid">
              {applicable.map((privilege) => (
                <label key={privilege} className="gov-privilege-option">
                  <input
                    type="checkbox"
                    checked={selected.has(privilege)}
                    onChange={() => togglePrivilege(privilege)}
                  />
                  <span className="gov-privilege-text">
                    <span className="gov-privilege-name">{privilege}</span>
                    <span className="gov-privilege-help">{PRIVILEGE_HELP[privilege]}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="uc-field">
            <label className="uc-field-label" htmlFor="gov-grant-expiry">
              Expires (optional)
            </label>
            <input
              id="gov-grant-expiry"
              type="date"
              className="uc-sidebar-owner-input"
              value={expiresAt}
              onChange={(event) => setExpiresAt(event.target.value)}
            />
            <p className="gov-field-help">
              Leave empty for a grant that does not expire.
            </p>
          </div>
        </div>

        <div className="uc-modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {createGrant.isPending ? 'Granting…' : 'Grant'}
          </button>
        </div>
      </div>
    </div>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}
