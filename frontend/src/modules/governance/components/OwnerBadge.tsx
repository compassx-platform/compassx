/**
 * Who owns an object, and — for a caller who may — a way to hand it over.
 *
 * The owner is deliberately readable by anyone who can see the object: they are
 * who you ask for access, so hiding them would leave a denied user with nowhere
 * to go. Transfer is offered only when `canManage`, and is confirmed, because
 * the transferring administrator may be handing away their own last route back
 * to the object.
 */
import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';

import { useToast } from '@/lib/toast';

import { useOwner, usePrincipalOptions, useTransferOwner } from '../hooks/useGovernance';
import type { PrincipalOption, SecurableRef } from '../governanceTypes';
import PrincipalPicker from './PrincipalPicker';

interface Props {
  securable: SecurableRef;
  canManage?: boolean;
}

export default function OwnerBadge({ securable, canManage = false }: Props) {
  const toast = useToast();
  const ownerQuery = useOwner(securable);
  const principals = usePrincipalOptions();
  const transfer = useTransferOwner(securable);

  const [isTransferring, setIsTransferring] = useState(false);
  const [nextOwner, setNextOwner] = useState<PrincipalOption | null>(null);

  const owner = ownerQuery.data;
  const ownerLabel = owner
    ? principals.options.find((option) => option.id === owner.owner_principal_id)?.label
      ?? owner.owner_principal_id
    : null;

  const handleTransfer = () => {
    if (!nextOwner) return;
    transfer.mutate(
      {
        ...securable,
        owner_principal_id: nextOwner.id,
        // A service principal cannot own an object; only users and groups can.
        owner_principal_type: nextOwner.type === 'group' ? 'group' : 'user',
      },
      {
        onSuccess: () => {
          toast.success(`${securable.name} is now owned by ${nextOwner.label}.`);
          setIsTransferring(false);
          setNextOwner(null);
        },
        onError: (error) => toast.error(errorMessage(error, 'Could not transfer ownership.')),
      },
    );
  };

  return (
    <div className="gov-owner-block">
      <div className="gov-owner-row">
        <span className="gov-owner-icon" aria-hidden="true">
          <ShieldCheck size={14} />
        </span>
        <span className="uc-field-label" style={{ margin: 0 }}>Owner</span>
        <span className="gov-owner-name">
          {ownerQuery.isLoading && 'Loading…'}
          {!ownerQuery.isLoading && ownerLabel}
          {!ownerQuery.isLoading && !owner && (
            <span className="gov-owner-none">No owner assigned</span>
          )}
        </span>
        {canManage && !isTransferring && (
          <button
            type="button"
            className="gov-link-btn"
            onClick={() => setIsTransferring(true)}
          >
            Transfer
          </button>
        )}
      </div>

      {owner && (
        <p className="gov-field-help">
          The owner holds full control and is who a denied user asks for access.
        </p>
      )}

      {isTransferring && (
        <div className="gov-transfer-panel">
          <div className="uc-field">
            <label className="uc-field-label">New owner</label>
            <PrincipalPicker
              options={principals.options}
              value={nextOwner}
              onChange={setNextOwner}
              isLoading={principals.isLoading}
            />
          </div>
          <p className="gov-field-help gov-warning">
            Ownership carries full control. If you are not otherwise an administrator
            here, you may not be able to take it back.
          </p>
          <div className="gov-inline-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setIsTransferring(false);
                setNextOwner(null);
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleTransfer}
              disabled={!nextOwner || transfer.isPending}
            >
              {transfer.isPending ? 'Transferring…' : 'Transfer ownership'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}
