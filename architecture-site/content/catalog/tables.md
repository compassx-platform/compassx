# Tables

A table is a `UnifiedCatalogTable` under a schema, with `UnifiedCatalogColumn` rows. The HTTP handlers `add_table`, `read_tables`, `read_table`, `refresh_table_columns`, and `remove_table` call `CreateTable`, `ListTables`, `GetTable`, `RefreshColumns`, and `DeleteTable`.

## Register a table

`CreateTable` requires the catalog and the schema. It raises `ValueError` with `Table '{name}' already exists in schema '{schema}'` when the name is taken. Otherwise it inserts the row with `table_type` from the request, owner and `created_by` set to the actor, and commits. It then enqueues a search document of type `table` with no column summary. The route turns a `ValueError` into HTTP 400 and claims ownership of `catalog.schema.table` for the caller after a successful create.

## Register a table from a file

`POST .../tables-from-file` reads the upload and the columns JSON, then `CreateTableFromFile` stores the bytes and registers an Iceberg table. The search document's content summary is the column names and types. A bad columns JSON is HTTP 400 from the route, before the application type runs.

## Read and refresh

`GetTable` and `ListTables` return `CatalogTableRead`, including columns. `RefreshColumns` introspects the live source: foreign tables through the Postgres reader, Iceberg tables through the metadata file. `introspect_columns` and `_replace_columns` live in `tables/repository.py`. Replacing columns deletes the previous column rows and inserts the new ones.

## Delete

`DeleteTable` removes only Iceberg tables. Any other type raises `Only Iceberg tables can be deleted from the catalog`. The catalog row and its lineage edges are deleted. The search asset row is deleted when that delete succeeds. Parquet and Iceberg metadata files in storage are left in place.

## Sample and lineage

`GetSampleData` reads up to the requested limit (default 100) from the table's source and returns columns plus rows. `RegisterLineage` stores an edge from a source table to a target table. `GetLineage` returns the graph for one table, walking the edges stored on `UnifiedCatalogLineage`.

## Create from a notebook kernel

`POST /api/v1/catalog/table/create`, `/table/write`, and `/table/optimize` stay in `routes.py`. Their JSON errors are the contract the notebook kernel reads (`status`, `error_type`, `message`), so the handlers still build that JSON. They use `_parse_table_ref`, the Iceberg manager, Z-order, and `resolve_catalog_storage`.

Create parses `catalog.schema.table`, checks governance before any schema is auto-created, writes a Parquet file, creates the Iceberg metadata, inserts the catalog row and columns, and enqueues search. Write checks the incoming columns against the registered ones and appends or overwrites according to the request. Optimize rewrites the Parquet files with Z-order and commits a new Iceberg snapshot. A failed search enqueue on create logs `Failed to enqueue embedding for table %s: %s` at warning and still returns the created table.
