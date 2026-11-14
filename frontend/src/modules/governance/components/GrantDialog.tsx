/**
 * Grant privileges on one securable.
 *
 * A small form: who receives the grant, then one picker that offers a bundle
 * or a single privilege. Bundles expand to the privileges that apply on this
 * securable type. The privilege list comes from `GET /governance/privileges`,
 * so the dialog cannot offer a grant the backend would reject.
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

  const onPick = (value: string) => {
    if (!value) return;
    if (value.startsWith('bundle:')) {
      const bundle = bundles.find((item) => item.name === value.slice('bundle:'.length));
      if (bundle) applyBundle(bundle.privileges);
      return;
    }
    togglePrivilege(value as Privilege);
  };

  const canSubmit = Boolean(principal) && selected.size > 0 && !createGrant.isPending;
  const selectedList = useMemo(() => Array.from(selected).sort(), [selected]);

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
          <div>
            <h3 id="gov-grant-title">Grant</h3>
            <p>{securable.name}</p>
          </div>
          <button type="button" className="uc-icon-btn" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="uc-modal-body">
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

          <div className="uc-field">
            <label className="uc-field-label" htmlFor="gov-grant-privilege">
              Privilege
            </label>
            {vocabulary.isError && (
              <div className="uc-empty-inline">Could not load the privilege list.</div>
            )}
            <select
              id="gov-grant-privilege"
              className="gov-privilege-select"
              value=""
              disabled={vocabulary.isLoading || vocabulary.isError}
              onChange={(event) => {
                onPick(event.target.value);
                event.target.value = '';
              }}
            >
              <option value="">
                {vocabulary.isLoading ? 'Loading privileges…' : 'Choose a privilege or bundle'}
              </option>
              {bundles.length > 0 && (
                <optgroup label="Bundles">
                  {bundles.map((bundle) => (
                    <option key={bundle.name} value={`bundle:${bundle.name}`}>
                      {bundleLabel(bundle.name)}
                    </option>
                  ))}
                </optgroup>
              )}
              {applicable.length > 0 && (
                <optgroup label="Privileges">
                  {applicable.map((privilege) => (
                    <option key={privilege} value={privilege}>
                      {privilege}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            {selectedList.length > 0 && (
              <div className="gov-selected-row">
                {selectedList.map((privilege) => (
                  <button
                    key={privilege}
                    type="button"
                    className="gov-bundle-chip is-active"
                    onClick={() => togglePrivilege(privilege)}
                  >
                    {privilege}
                    <X size={12} aria-hidden="true" />
                    <span className="sr-only">Remove {privilege}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="uc-field">
            <label className="uc-field-label" htmlFor="gov-grant-expiry">
              Expires
            </label>
            <input
              id="gov-grant-expiry"
              type="date"
              className="uc-sidebar-owner-input"
              value={expiresAt}
              onChange={(event) => setExpiresAt(event.target.value)}
            />
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

function bundleLabel(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}
