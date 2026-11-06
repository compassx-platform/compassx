# Screen

The legacy data catalog has no page of its own. The screen titled for data catalog work is the Catalog module at `/data-catalog`. That page calls `/catalog/...`. It does not call `/api/v1/data-catalog`.

A person checks this module through the HTTP routes: save a connection, test a host, list databases, preview a table, and run SQL. The password they typed does not come back in the connection JSON.
