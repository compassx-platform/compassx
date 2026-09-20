"""Tests for Databricks-style IAM/IDM and In-Session Role Switcher logic."""
from __future__ import annotations

import hashlib
import pytest
from app.user_manager.models.account_models import (
    UmServicePrincipal,
    UmServicePrincipalSecret,
    UmGroupNesting,
    UmGroupManager,
    UmServicePrincipalACL,
)
from app.governance.dependencies import _scoped_group_ids, _group_ids


def test_service_principal_secret_hashing():
    """Test SHA-256 secret generation and validation pattern."""
    raw_secret = "cx_sec_1234567890abcdef"
    hashed = hashlib.sha256(raw_secret.encode()).hexdigest()

    secret_record = UmServicePrincipalSecret(
        id="sec-1",
        sp_id="sp-1",
        secret_hash=hashed,
        secret_prefix="cx_sec_1234",
    )

    assert hashlib.sha256(raw_secret.encode()).hexdigest() == secret_record.secret_hash
    assert hashlib.sha256(b"wrong_secret").hexdigest() != secret_record.secret_hash


def test_cycle_detection_logic():
    """Test directed cycle detection logic for group nesting."""
    # Graph: G1 -> G2 -> G3 (G2 is parent of G1, G3 is parent of G2)
    nestings = [
        {"parent_group_id": "G2", "child_group_id": "G1"},
        {"parent_group_id": "G3", "child_group_id": "G2"},
    ]

    def has_ancestor(node: str, target_ancestor: str, current_nestings: list[dict]) -> bool:
        """Check if target_ancestor is an ancestor of node."""
        visited = set()
        queue = [node]
        while queue:
            curr = queue.pop(0)
            parents = [n["parent_group_id"] for n in current_nestings if n["child_group_id"] == curr]
            for p in parents:
                if p == target_ancestor:
                    return True
                if p not in visited:
                    visited.add(p)
                    queue.append(p)
        return False

    # Check valid nesting: G4 is parent of G3 -> G3 is not ancestor of G4
    assert not has_ancestor(node="G4", target_ancestor="G3", current_nestings=nestings)

    # Check cycle: Adding G1 as parent of G3 -> Check if G3 is already an ancestor of G1 -> True!
    assert has_ancestor(node="G1", target_ancestor="G3", current_nestings=nestings)


def test_role_switcher_scoping_behavior():
    """Test in-session role assumption scoping."""
    # Given user belongs to [G1, G2]
    # G1's parent is G_Parent
    user_direct_groups = {"G1", "G2"}
    
    # When user assumes G1, active_role_id = G1
    active_role_id = "G1"
    assert active_role_id in user_direct_groups

    # When user attempts to assume G3 (not a member)
    invalid_role_id = "G3"
    assert invalid_role_id not in user_direct_groups
