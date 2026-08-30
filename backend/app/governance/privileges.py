"""Governance vocabulary: securable types, privileges, and privilege bundles.

This module is pure definitions — no database access, no FastAPI. It is the
single source of truth for what can be secured and what may be done to it.

Model summary (see .compassx/security-review/governance-design.md):

  * Nine privileges, deliberately fewer than Unity Catalog's ~30.
  * Access to a nested securable requires USE on every ancestor container
    (the "USE chain"). This is what makes a catalog boundary a real gate
    rather than a naming convention.
  * BROWSE is separate from USE so a principal can discover that an object
    exists, and request access to it, without being able to read it.
  * Deny by default. There are no explicit DENY grants; revoke instead.
"""
from __future__ import annotations

import enum


class SecurableType(str, enum.Enum):
    """Every object type that can carry an owner and be granted on."""

    # Catalog-path securables — addressed by (catalog, schema, asset) and
    # subject to inheritance down the path.
    CATALOG = "catalog"
    SCHEMA = "schema"
    TABLE = "table"
    VOLUME = "volume"
    NOTEBOOK = "notebook"
    DASHBOARD = "dashboard"
    QUERY = "query"
    TOOL = "tool"

    # Workspace-scoped securables — no catalog path, one level of inheritance
    # from the workspace role only.
    JOB = "job"
    AGENT = "agent"
    COMPUTE = "compute"
    CONNECTION = "connection"


#: Securables that live under a catalog/schema path and inherit down it.
CATALOG_PATH_SECURABLES: frozenset[SecurableType] = frozenset({
    SecurableType.CATALOG,
    SecurableType.SCHEMA,
    SecurableType.TABLE,
    SecurableType.VOLUME,
    SecurableType.NOTEBOOK,
    SecurableType.DASHBOARD,
    SecurableType.QUERY,
    SecurableType.TOOL,
})

#: Securables scoped directly to a workspace, with no catalog path.
WORKSPACE_SECURABLES: frozenset[SecurableType] = frozenset({
    SecurableType.JOB,
    SecurableType.AGENT,
    SecurableType.COMPUTE,
    SecurableType.CONNECTION,
})

#: Container types that participate in the USE chain, ordered outermost first.
CONTAINER_SECURABLES: tuple[SecurableType, ...] = (
    SecurableType.CATALOG,
    SecurableType.SCHEMA,
)


class Privilege(str, enum.Enum):
    """The complete privilege set. Keep this list short."""

    USE = "USE"                  # traverse into a container; grants no sight of contents
    BROWSE = "BROWSE"            # see the object exists and read its metadata
    SELECT = "SELECT"            # read data / file contents
    MODIFY = "MODIFY"            # insert, update, delete data (not drop the object)
    CREATE = "CREATE"            # create children; creator owns the child
    EXECUTE = "EXECUTE"          # run it
    EDIT = "EDIT"                # change its definition
    USE_COMPUTE = "USE_COMPUTE"  # attach to a cluster/warehouse or use a connection
    MANAGE = "MANAGE"            # full control incl. granting and deleting; implied by ownership


#: Which privileges are meaningful on which securable type.
#: Used to validate grants at the API boundary so administrators cannot create
#: grants that could never be evaluated (e.g. SELECT on a job).
APPLICABLE_PRIVILEGES: dict[SecurableType, frozenset[Privilege]] = {
    SecurableType.CATALOG: frozenset({
        Privilege.USE, Privilege.BROWSE, Privilege.CREATE, Privilege.MANAGE,
        # Granted at catalog level to cascade to descendant tables/volumes.
        Privilege.SELECT, Privilege.MODIFY, Privilege.EXECUTE, Privilege.EDIT,
    }),
    SecurableType.SCHEMA: frozenset({
        Privilege.USE, Privilege.BROWSE, Privilege.CREATE, Privilege.MANAGE,
        Privilege.SELECT, Privilege.MODIFY, Privilege.EXECUTE, Privilege.EDIT,
    }),
    SecurableType.TABLE: frozenset({
        Privilege.BROWSE, Privilege.SELECT, Privilege.MODIFY, Privilege.MANAGE,
    }),
    SecurableType.VOLUME: frozenset({
        Privilege.BROWSE, Privilege.SELECT, Privilege.MODIFY, Privilege.MANAGE,
    }),
    SecurableType.NOTEBOOK: frozenset({
        Privilege.BROWSE, Privilege.EXECUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.DASHBOARD: frozenset({
        Privilege.BROWSE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.QUERY: frozenset({
        Privilege.BROWSE, Privilege.SELECT, Privilege.EXECUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.TOOL: frozenset({
        Privilege.BROWSE, Privilege.EXECUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.JOB: frozenset({
        Privilege.BROWSE, Privilege.EXECUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.AGENT: frozenset({
        Privilege.BROWSE, Privilege.EXECUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.COMPUTE: frozenset({
        Privilege.BROWSE, Privilege.USE_COMPUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
    SecurableType.CONNECTION: frozenset({
        Privilege.BROWSE, Privilege.USE_COMPUTE, Privilege.EDIT, Privilege.MANAGE,
    }),
}


#: Privileges that MANAGE implies. Ownership implies MANAGE, so an owner
#: implicitly holds everything applicable to their object.
def implied_by_manage(securable_type: SecurableType) -> frozenset[Privilege]:
    """MANAGE confers every privilege applicable to the securable."""
    return APPLICABLE_PRIVILEGES.get(securable_type, frozenset())


#: Named bundles shown in the UI. Administrators think in roles, not in
#: individual privileges; raw privileges stay available via the API.
PRIVILEGE_BUNDLES: dict[str, frozenset[Privilege]] = {
    "viewer": frozenset({Privilege.BROWSE, Privilege.SELECT, Privilege.USE}),
    "contributor": frozenset({
        Privilege.BROWSE, Privilege.SELECT, Privilege.USE,
        Privilege.MODIFY, Privilege.EXECUTE, Privilege.EDIT,
    }),
    "creator": frozenset({
        Privilege.BROWSE, Privilege.SELECT, Privilege.USE,
        Privilege.MODIFY, Privilege.EXECUTE, Privilege.EDIT,
        Privilege.CREATE,
    }),
    "owner": frozenset({Privilege.MANAGE}),
}


def expand_bundle(bundle_or_privilege: str) -> frozenset[Privilege]:
    """Resolve a bundle name or a raw privilege name to a privilege set.

    Accepts either so that grant APIs can take a single ``privilege`` field.
    Raises ValueError on an unknown name rather than silently granting nothing,
    which would fail open from the administrator's point of view.
    """
    key = bundle_or_privilege.strip()
    if key.lower() in PRIVILEGE_BUNDLES:
        return PRIVILEGE_BUNDLES[key.lower()]
    try:
        return frozenset({Privilege(key.upper())})
    except ValueError:
        raise ValueError(
            f"Unknown privilege or bundle: {bundle_or_privilege!r}. "
            f"Expected one of {sorted(PRIVILEGE_BUNDLES)} "
            f"or {sorted(p.value for p in Privilege)}."
        ) from None


def validate_privilege_for_securable(
    privilege: Privilege, securable_type: SecurableType
) -> None:
    """Reject grants that could never be evaluated.

    Called at the grant API boundary. Without this an administrator can create
    a SELECT-on-job grant, see it listed in the UI, and reasonably believe
    access was conferred when nothing will ever read it.
    """
    applicable = APPLICABLE_PRIVILEGES.get(securable_type, frozenset())
    if privilege not in applicable:
        raise ValueError(
            f"{privilege.value} is not applicable to {securable_type.value}. "
            f"Applicable privileges: {sorted(p.value for p in applicable)}."
        )
