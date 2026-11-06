# Privileges

`GET /api/v1/governance/privileges` returns the vocabulary the grant dialog uses. It does not read the database.

The privilege names are `USE`, `BROWSE`, `SELECT`, `MODIFY`, `CREATE`, `EXECUTE`, `EDIT`, `USE_COMPUTE`, and `MANAGE`.

Catalog-path types are `catalog`, `schema`, `table`, `volume`, `notebook`, `dashboard`, `query`, and `tool`. They are addressed as a dotted name such as `main.sales.orders`. Workspace types are `job`, `agent`, `compute`, and `connection`. They are addressed by object id.

`MANAGE` implies every privilege that applies to that type. Ownership implies `MANAGE`.

Bundles expand to individual privileges when a grant is saved:

| Bundle | Privileges |
| --- | --- |
| `viewer` | `BROWSE`, `SELECT`, `USE` |
| `contributor` | those, plus `MODIFY`, `EXECUTE`, `EDIT` |
| `creator` | those, plus `CREATE` |
| `owner` | `MANAGE` |

An unknown name is `Unknown privilege or bundle: {name}. Expected one of {bundles} or {privileges}.` A privilege named by itself that does not apply to the type is `{privilege} is not applicable to {type}. Applicable privileges: {list}.` A bundle that contains privileges the type does not use drops those members. If nothing applicable remains, the grant is HTTP 400 `None of {names} are applicable to {type}.`

`Securable.parse` rejects a catalog-path object with a missing catalog, schema, or asset, and a workspace object with no id. The route returns that message as HTTP 400.
