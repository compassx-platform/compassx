/**
 * Governance module — owner, grants, and effective-permission UI.
 *
 * Drop `<PermissionsPanel securableType="table" name="main.sales.orders" />`
 * into any detail page; everything else here supports it.
 */
export { default as PermissionsPanel } from './components/PermissionsPanel';
export { default as OwnerBadge } from './components/OwnerBadge';
export { default as OwnerName } from './components/OwnerName';
export { default as GrantDialog } from './components/GrantDialog';
export { default as EffectivePermissions } from './components/EffectivePermissions';
export { default as PrincipalPicker } from './components/PrincipalPicker';

export * from './governanceTypes';
export * from './hooks/useGovernance';
