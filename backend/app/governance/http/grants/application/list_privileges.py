from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_privileges() -> dict:
    """The privilege vocabulary, for building a grant dialog.

    Served from the backend rather than duplicated in the frontend so the two
    cannot drift into offering privileges the resolver will not honour.
    """
    return {
        "privileges": [p.value for p in Privilege],
        "bundles": {
            name: sorted(p.value for p in privileges)
            for name, privileges in PRIVILEGE_BUNDLES.items()
        },
        "applicable": {
            securable.value: sorted(p.value for p in privileges)
            for securable, privileges in APPLICABLE_PRIVILEGES.items()
        },
    }
