"""Legacy workspace helpers retained for import compatibility.

The agents feature no longer exposes or enforces workspace membership.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


def _require_member(*args, **kwargs):
    return None


def _require_role(*args, **kwargs):
    return None
