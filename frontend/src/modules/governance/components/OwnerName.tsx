/**
 * The owner of a securable, resolved to a display name.
 *
 * A read-only counterpart to `OwnerBadge`, for the metadata rows that detail
 * pages already have. It exists so those rows can show the real owner instead
 * of a locally-invented one; the transfer affordance stays in the Permissions
 * tab where the confirmation and warning live.
 */
import { useMemo } from 'react';

import { useOwner, usePrincipalLabels } from '../hooks/useGovernance';
import type { SecurableRef, SecurableType } from '../governanceTypes';

interface Props {
  securableType: SecurableType;
  name: string;
  /** Shown while loading and when the object has no owner recorded. */
  fallback?: string;
}

export default function OwnerName({ securableType, name, fallback = '—' }: Props) {
  const securable = useMemo<SecurableRef>(
    () => ({ securable_type: securableType, name }),
    [securableType, name],
  );
  const ownerQuery = useOwner(securable);
  const labelFor = usePrincipalLabels();

  if (ownerQuery.isLoading) return <>{fallback}</>;
  const ownerId = ownerQuery.data?.owner_principal_id;
  if (!ownerId) return <>{fallback}</>;
  return <>{labelFor(ownerId)}</>;
}
