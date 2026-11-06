from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def test_connection(body: ConnectionTestRequest):
    result = test_connection_raw(
        host=body.host,
        port=body.port,
        username=body.username,
        password=body.password,
        database=body.database,
    )
    return ConnectionTestResponse(**result)
