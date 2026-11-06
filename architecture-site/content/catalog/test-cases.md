# Test cases

A person or an agent runs these in the product, end to end. They are not code tests. Pass means the outcome below is what you see.

## Create a catalog, a schema, and a table

Create a catalog. Add a schema. Create a table in that schema. Open the table.

You should see the table under the schema, with its columns. Search for the table by name and open it from the result.

## Refuse a duplicate

Create a second table with the same name in that schema.

You should see the create refused because the table already exists. The first table is unchanged.

## Register a table from a file

Put a data file in a volume. Create a table from that file. Open the table and its sample.

You should see columns and sample rows that match the file.

## Read a table from a notebook, change it, and store it

Create a notebook in that schema. Open it, attach compute, and run a cell that reads the table. In a later cell, change the rows and write them back through the catalog. Close the notebook and open it again. Open the table sample.

You should see the rows in the cell, the same cells when you reopen the notebook, and the changed rows on the table. The full notebook walkthrough is also the Notebooks test case, once that page exists.

## Work with files in a volume

Create a volume. Upload a file, rename it, download it, and delete it.

You should see the uploaded name, then the new name, a download of that file, and an empty list after delete.

## Follow lineage

Record lineage from a source table to a table produced from it. Open lineage for either table.

You should see both tables and the link between them.

## Save a notebook, a dashboard, and a query

Under one schema, create a notebook, a dashboard, and a query. Move the notebook to another schema. Save a second version of the query, then restore the first version. Delete the query.

You should see the notebook in the new schema, the query text back to the first version, and the query gone after delete. The dashboard stays in the original schema.

## Sync a Postgres catalog

Create a catalog of type postgres pointed at a database you can reach. Run sync. Open the schemas and tables.

You should see the remote schemas and base tables, with their columns, and those tables findable by search.

## Show the catalog only in one workspace

Bind the catalog to one workspace. Open the catalog from that workspace, then from a workspace that is not bound and for which the catalog is not marked for all workspaces.

You should see the catalog in the bound workspace only.

## Promote a tool and open it

In a notebook, define a function with `@cx.tool`, giving it a name, a description, and one argument. Run `cx.tools.promote` for that function into a catalog and schema. Open that schema in the data catalog and choose Tools. Open the tool.

You should see the promotion succeed in the notebook, the tool under Tools, and its full name, parameter, source, and version 1. Promote the same function again after changing the source. Version History should show version 2, and Source Code should show the new function. Ask Nova, or an agent that has this tool enabled, to call it. You should see the function run and its result come back in the chat.

## Ask the catalog agent tool to find a table

With a table already in a catalog this workspace can see, ask an agent that has the `catalog` tool to list catalogs, then to search for that table by name.

You should see the catalog in the list, and the table's `catalog.schema.table` name in the search result. A catalog bound only to another workspace should be absent from the list.

## Delete an Iceberg table

Delete an Iceberg table you created for this check. Try the same delete on a foreign table.

You should see the Iceberg table leave the schema. The foreign table stays, and the delete is refused because only Iceberg tables are removed. The Iceberg files in storage are still there.
