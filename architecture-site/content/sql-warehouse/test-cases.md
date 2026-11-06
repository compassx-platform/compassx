# Test cases

Run these in a workspace where you can open SQL Editor. Use a second user in the same workspace when a case says so.

## Create the first warehouse

Open **SQL Warehouses**. You should see the heading **SQL Warehouses**. Choose **Create warehouse**, name it `sales`, leave the engine on DuckDB, and choose **Create**.

The new row should appear and its status should be running. It should be the default, because it is the first warehouse in the workspace. The list count should say `1 warehouse`.

## A second engine

Create another warehouse named `events` with engine ClickHouse.

It should not be the default. Set it as the default. `sales` should lose the default mark and `events` should gain it. Stop `events`. Its status should be stopped. Start it. Its status should be running again.

## Run a statement

Open **SQL Editor**. You should see the sidebar title **SQL Editor** and a tab whose text is `SELECT 1 AS id, 'CompassX SQL Warehouse' AS name;`. Run it.

You should see one row with those two columns. Open **Query History**. The statement should be there with status succeeded, and the row should name the warehouse that ran it.

## A stopped warehouse still runs

Stop the default warehouse. Run `SELECT 42 AS answer` from the editor.

The statement should return one row. The warehouse status should be running again.

## Validate and explain

Validate an empty statement. You should see that it is not valid, with the error `Empty SQL`.

Validate `SELECT 1`. You should see that it is valid and the statement count is 1.

Explain `SELECT 1` against the running warehouse. You should get a plan. Explain against a warehouse id from another workspace. You should get 404 `Warehouse not found`.

## Drafts stay with the person

In the editor, create a tab and leave the name blank. It should be named `Query 1`. Create another named `Monthly Report`.

Sign in as the other user in the same workspace and open **SQL Editor**. You should not see `Monthly Report`. Their first blank tab should also be named `Query 1`.

Rename `Monthly Report` to a blank name and save. The name should stay `Monthly Report`. Delete that tab. It should leave the editor, and the other user's tabs should be unchanged.

## History is personal

Run a statement as the first user. Open **Query History** as the second user.

The first user's statement should not be in the second user's list. Asking for the first user's result id as the second user should be 403 `Forbidden`.

## Catalog browser

In the editor, open a catalog that belongs to the workspace. You should see its schemas, then its tables. A catalog from another workspace should not be in the list.

## Concurrent limit

Set the warehouse policy `max_concurrent_queries` to 1 and start a statement that is still running. Start a second statement on the same warehouse.

The second statement should fail with `Warehouse '{name}' has reached its concurrent query limit of 1.`

## Delete

Delete `events`. It should leave **SQL Warehouses**, and a later query should not be able to select it.
