# Volumes

A volume is a `UnifiedCatalogVolume` under a schema. Files inside it are bytes on the catalog's storage backend, tracked by `UnifiedCatalogVolumeFile` when a file is recorded.

## Create and list

`CreateVolume` checks the catalog and schema, refuses a duplicate volume name, inserts the row, commits, and enqueues a search document of type `volume`. A failed enqueue logs `Failed to enqueue embedding for volume %s: %s` and leaves the volume row. `ListVolumes` filters by catalog and schema when those names are passed.

The route `add_volume` requires `CREATE` on the schema and claims ownership of the volume securable after the row exists.

## Files

File routes take a volume id. `_volume_securable` in `routes.py` joins the volume to its schema and catalog and builds the securable `catalog.schema.volume`. An unknown id is HTTP 404, so an id cannot skip the path used for grants.

`VolumeManager` in `infrastructure/volume_manager.py` uploads, lists, downloads, renames, and deletes. Its log lines are unchanged (`Uploaded %s to volume %s (%d bytes)`, and the matching lines for directories, deletes, and renames). The route handlers authorize with the guard, then call the manager. `record_volume_file` checks the caller's token, then records a file that was written outside this request.

## Resolve credentials

`POST /api/v1/catalog/volumes/resolve` mints storage credentials for a volume path. The route refuses a missing workspace id, validates the bearer token, resolves the storage context for the schema, and logs success or `Volume resolve: credential mint failed: %s`. Those log lines stay on `app.catalog.routes`.
