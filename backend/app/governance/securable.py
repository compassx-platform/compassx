"""Securable addressing — how a governed object is identified in a grant.

A Securable is the (type, path) pair that grants are made against. Two shapes:

  * Catalog-path securables use (catalog, schema, asset), matching the columns
    already present on ``um_object_grants``. Grants inherit down the path.
  * Workspace-scoped securables (jobs, agents, compute, connections) have no
    catalog path and are addressed by their id.

Keeping addressing in one immutable type means callers cannot construct a
half-specified securable — e.g. a table with no schema — which would otherwise
produce a grant that silently matches more than intended.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.governance.privileges import (
    CATALOG_PATH_SECURABLES,
    WORKSPACE_SECURABLES,
    SecurableType,
)

#: Placeholder written to ``um_object_grants.catalog_name`` for workspace-scoped
#: securables. The column is NOT NULL and shared with catalog-path grants; a
#: sentinel that cannot collide with a real catalog name keeps the two families
#: separable in SQL without a schema change.
WORKSPACE_SENTINEL = "__workspace__"


@dataclass(frozen=True, slots=True)
class Securable:
    """An addressable, governable object."""

    type: SecurableType
    catalog: str | None = None
    schema: str | None = None
    asset: str | None = None

    def __post_init__(self) -> None:
        if self.type in CATALOG_PATH_SECURABLES:
            self._validate_catalog_path()
        elif self.type in WORKSPACE_SECURABLES:
            if not self.asset:
                raise ValueError(f"{self.type.value} securable requires an asset id")
        else:  # pragma: no cover - guards against an unhandled enum member
            raise ValueError(f"Unhandled securable type: {self.type}")

    def _validate_catalog_path(self) -> None:
        if not self.catalog:
            raise ValueError(f"{self.type.value} securable requires a catalog name")

        needs_schema = self.type is not SecurableType.CATALOG
        if needs_schema and not self.schema:
            raise ValueError(f"{self.type.value} securable requires a schema name")

        needs_asset = self.type not in (SecurableType.CATALOG, SecurableType.SCHEMA)
        if needs_asset and not self.asset:
            raise ValueError(f"{self.type.value} securable requires an asset name")

        # Reject over-specification: a catalog with a schema name would be
        # ambiguous when matched as a grant prefix.
        if self.type is SecurableType.CATALOG and (self.schema or self.asset):
            raise ValueError("catalog securable must not carry a schema or asset name")
        if self.type is SecurableType.SCHEMA and self.asset:
            raise ValueError("schema securable must not carry an asset name")

    # ------------------------------------------------------------------
    # Constructors — clearer at call sites than positional arguments
    # ------------------------------------------------------------------

    @classmethod
    def catalog_(cls, catalog: str) -> "Securable":
        return cls(SecurableType.CATALOG, catalog=catalog)

    @classmethod
    def schema_(cls, catalog: str, schema: str) -> "Securable":
        return cls(SecurableType.SCHEMA, catalog=catalog, schema=schema)

    @classmethod
    def table(cls, catalog: str, schema: str, name: str) -> "Securable":
        return cls(SecurableType.TABLE, catalog=catalog, schema=schema, asset=name)

    @classmethod
    def volume(cls, catalog: str, schema: str, name: str) -> "Securable":
        return cls(SecurableType.VOLUME, catalog=catalog, schema=schema, asset=name)

    @classmethod
    def notebook(cls, catalog: str, schema: str, name: str) -> "Securable":
        return cls(SecurableType.NOTEBOOK, catalog=catalog, schema=schema, asset=name)

    @classmethod
    def dashboard(cls, catalog: str, schema: str, name: str) -> "Securable":
        return cls(SecurableType.DASHBOARD, catalog=catalog, schema=schema, asset=name)

    @classmethod
    def query(cls, catalog: str, schema: str, name: str) -> "Securable":
        return cls(SecurableType.QUERY, catalog=catalog, schema=schema, asset=name)

    @classmethod
    def tool(cls, catalog: str, schema: str, name: str) -> "Securable":
        return cls(SecurableType.TOOL, catalog=catalog, schema=schema, asset=name)

    @classmethod
    def job(cls, job_id: str) -> "Securable":
        return cls(SecurableType.JOB, asset=job_id)

    @classmethod
    def agent(cls, agent_id: str) -> "Securable":
        return cls(SecurableType.AGENT, asset=agent_id)

    @classmethod
    def compute(cls, compute_id: str) -> "Securable":
        return cls(SecurableType.COMPUTE, asset=compute_id)

    @classmethod
    def connection(cls, connection_id: str) -> "Securable":
        return cls(SecurableType.CONNECTION, asset=connection_id)

    @classmethod
    def parse(cls, securable_type: str | SecurableType, name: str) -> "Securable":
        """Build a Securable from the (type, name) pair the API accepts.

        ``name`` is the dotted path for catalog-path securables and the object
        id for workspace-scoped ones. Validation happens in ``__post_init__``,
        so a wrong number of path segments is rejected here rather than
        producing a grant that matches more than the caller intended.
        """
        kind = (
            securable_type
            if isinstance(securable_type, SecurableType)
            else SecurableType(str(securable_type).lower())
        )
        if kind in WORKSPACE_SECURABLES:
            return cls(kind, asset=name)

        parts = name.split(".")
        if len(parts) > 3:
            raise ValueError(
                f"{name!r} has {len(parts)} path segments; expected at most 3 "
                f"(catalog.schema.asset)."
            )
        parts += [None] * (3 - len(parts))  # type: ignore[list-item]
        return cls(kind, catalog=parts[0], schema=parts[1], asset=parts[2])

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def is_catalog_path(self) -> bool:
        return self.type in CATALOG_PATH_SECURABLES

    @property
    def storage_catalog(self) -> str:
        """Value written to ``um_object_grants.catalog_name`` (NOT NULL)."""
        return self.catalog if self.is_catalog_path else WORKSPACE_SENTINEL

    def ancestors(self) -> list["Securable"]:
        """Containers whose USE privilege is a prerequisite, outermost first.

        Workspace-scoped securables have no ancestors; their gate is the
        workspace role check, applied separately.
        """
        if not self.is_catalog_path:
            return []

        chain: list[Securable] = []
        if self.type is not SecurableType.CATALOG:
            chain.append(Securable.catalog_(self.catalog))  # type: ignore[arg-type]
        if self.type not in (SecurableType.CATALOG, SecurableType.SCHEMA):
            chain.append(Securable.schema_(self.catalog, self.schema))  # type: ignore[arg-type]
        return chain

    def covers(self, other: "Securable") -> bool:
        """True if a grant on ``self`` should also apply to ``other``.

        Inheritance flows down the catalog path: a grant on a catalog covers
        its schemas and their assets. Workspace-scoped securables never cover
        anything but themselves — an EXECUTE grant on one job must not leak to
        another.
        """
        if not self.is_catalog_path:
            return self == other
        if not other.is_catalog_path:
            return False
        if self.catalog != other.catalog:
            return False
        if self.type is SecurableType.CATALOG:
            return True
        if self.schema != other.schema:
            return False
        if self.type is SecurableType.SCHEMA:
            return True
        # Asset-level grant: must match the same asset, and the same kind of
        # asset. Two different object types may share a name within a schema.
        return self.type is other.type and self.asset == other.asset

    @property
    def full_name(self) -> str:
        """Human-readable identifier used in errors, audit records, and the UI."""
        if not self.is_catalog_path:
            return f"{self.type.value}:{self.asset}"
        parts = [p for p in (self.catalog, self.schema, self.asset) if p]
        return ".".join(parts)

    def __str__(self) -> str:
        return f"{self.type.value} {self.full_name}"
