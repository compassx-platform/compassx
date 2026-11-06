# Legacy data catalog

The legacy data catalog stores saved PostgreSQL connections and reads databases, schemas, tables, and query results through those connections. It is not the Catalog module. Catalog owns catalogs, schemas, tables, volumes, notebooks, dashboards, queries, and tools. This module owns `/api/v1/data-catalog`.

`main.py` includes `app.data.routes.data_catalog_routes.router`. The prefix is `/api/v1/data-catalog` and the tag is `Data Catalog`. This module does not register an agent tool. There is no Tools page.

The route session is `get_db`, which is the system database session. `CatalogConnection` is declared on `AccountBase`. The password column is Fernet ciphertext. A response never includes the password.

`app.routes.data_catalog_routes`, `app.services.data_catalog_service`, `app.schemas.data_catalog`, and `app.models.data_catalog` stay as the old import paths. The service shim makes `app.services.data_catalog_service` the same module as `app.data.services.data_catalog_service`.

## What stays public

`app.data.routes.data_catalog_routes` still defines `router` and the handler names `get_connections`, `read_connection`, `add_connection`, `edit_connection`, `remove_connection`, `test_connection`, `get_databases`, `get_schemas`, `get_tables`, `preview_table`, and `run_sql`. Each handler forwards to one application file.

`list_connections`, `get_connection`, `create_connection`, `update_connection`, `delete_connection`, `test_connection_raw`, `list_databases`, `list_schemas`, `list_tables`, `get_table_preview`, and `execute_sql` stay importable from `app.data.services.data_catalog_service` and from `app.services.data_catalog_service`. Each one forwards to one application file. `encrypt_password`, `decrypt_password`, `_make_conn`, `_conn_from_record`, `_serialize_value`, and `_serialize_row` stay in the service module. The logger stays `app.data.services.data_catalog_service`.

## Files

- `app/data/routes/data_catalog_routes.py` — HTTP facade
- `app/data/http/catalog/application/` — one file per route
- `app/data/services/data_catalog_service.py` — service facade and connection helpers
- `app/data/services/application/` — one file per service action
- `app/data/models/data_catalog.py` — `catalog_connections`
- `app/data/models/dataset.py` — `datasets`
- `app/data/schemas/data_catalog.py` — request and response models
- `app/data/dataset/dsl_models.py` — `DatasetQuery`
- `app/routes/data_catalog_routes.py`, `app/services/data_catalog_service.py`, `app/schemas/data_catalog.py`, `app/models/data_catalog.py`, `app/models/dataset.py`, `app/dataset/` — old import paths

## Pages

- [Connections](connections.md)
- [Browse](browse.md)
- [SQL](sql.md)
- [Datasets](datasets.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
