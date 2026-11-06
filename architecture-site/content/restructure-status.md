# Restructure status

Keep this page. Do not remove it.

Catalog, Ontology, Monitoring, Ingestion, Jobs, Dashboards, SQL warehouse, Storage, Notebooks, Compute, Sandbox, Apps, Portal, AI Gateway, Agents, Nova, Agent runtime, Identity, Workspace, Governance, Platform, Legacy data catalog, and Shared libraries are restructured. Their documents are written from the code.

Update this page in the same change that restructures a module. Set that row to **In progress** while the split is open, and **Done** when the public behavior is unchanged and the module page is updated.

## Restructuring guideline

The current code is the source of truth. The folder sketch for Catalog is a guide. Change the folders when the module needs a different shape.

There is no module document to restructure from. For each module, follow this order:

1. Read the existing code for that module.
2. Understand the functionality.
3. Split that functionality into logical, readable pages. Write each page in depth from the code. Cover the logical flow and what the module does. Register every new page in `content/nav.json` under that module. If the module exposes a tool, add `content/<module>/tools.md` and register it. A tool is an agent tool the module registers, a tool record the module stores, or a tool HTTP route the module owns. Write what the tool does, how a person or an agent calls it, and what they should see. Do not add that page when the module exposes no tool.
4. Write the test cases for that module in `content/<module>/test-cases.md`, and register the page in `content/nav.json`. Write them in plain English. They are real uses a person or an agent runs in the product, end to end, to see that the functionality works. They are not code tests. Cover what the module does. For each case, say what you do and what you should see. For example: create a notebook, read data from the catalog, change it, and store it. If the module exposes a tool, include a case that runs that tool.
5. Restructure the code. The rules below still apply.
6. Update that module's documents, including its test cases, if the restructure changed a file, a flow, or a boundary. Run the cases and confirm the same outcomes.

Rules that apply while the code is restructured:

1. Restructure one module at a time. Do not change what a user can do. HTTP paths, JSON bodies, database writes, log text, and UI behavior stay as they are.
2. Split at real seams. Routes handle HTTP. One application file owns one action. A repository owns SQLAlchemy. A port owns a collaborator such as search, storage, or logging.
3. Business logic and logging both follow SOLID. The application type decides the outcome. The logger writes the same message and level the code writes today.
4. Keep the existing import path as a facade. `service.py` and `routes.py` keep their public names and forward to the new types. Callers do not change.
5. Do not introduce a second domain model. SQLAlchemy models stay the persistence model.
6. Do not merge the legacy data catalog into Catalog. Do not move Identity, Workspace, Governance, or Platform out of the process.
7. A module is done only when `content/<module>/index.md` matches the new files, and any topic page under that module touched by the change is updated from the code.
8. A topic page stays **Not traced** until the sequence is read from the code. Put that page in the module it belongs to. Do not create a separate runtime or decisions section.
9. Document every tool the module exposes, on that module's Tools page. Catalog is the example. A module that exposes no tool does not get an empty Tools page.

Order of work: Catalog, then Ontology, Monitoring, Ingestion, Jobs, Dashboards, SQL warehouse, Storage, Notebooks, Compute, Sandbox, Apps, Portal, AI Gateway, then Agents with Nova and Agent runtime. The shared kernel waits until product modules call it through a port.

## Reference file structure

Catalog is the reference. Other modules use the same interior and rename the resource packages to match their own actions. `connections/`, tools, and ORM models stay where callers already import them. A file that moves under `infrastructure/` keeps a one-line shim at the old import path.

The resource package for schemas is `schema/`, because `schemas.py` must keep its name.

```text
backend/app/catalog/
├── routes.py                      # same router and handler names
├── service.py                     # same function names; each forwards to one application type
├── composition.py                 # wires the log, search index, and Postgres reader
├── models.py                      # existing ORM models
├── schemas.py                     # existing public request and response models
│
├── shared/
│   ├── log.py                     # CatalogLog port
│   ├── search_index.py            # SearchIndex port
│   └── postgres_reader.py         # PostgresReader port
│
├── tables/
│   ├── repository.py              # shared table lookups and column replacement
│   └── application/
│       ├── create_table.py        # class CreateTable
│       ├── get_table.py
│       ├── list_tables.py
│       ├── delete_table.py
│       ├── refresh_columns.py
│       └── create_table_from_file.py
│
├── catalogs/application/...
├── schema/application/...         # schema/, not schemas/, so schemas.py keeps its name
├── volumes/application/...
├── notebooks/application/...
├── dashboards/application/...
├── queries/application/...
├── lineage/application/...
├── sample_data/application/...
├── browse/application/...
├── sync/application/...
├── iceberg/application/...
│
├── infrastructure/                # iceberg, volumes, search, embeddings, storage, z-order
└── connections/                   # already split; left in place
```

HTTP stays in `routes.py`. There is no per-resource `routes.py`. A repository file holds the lookups that more than one action uses. An action's own queries stay inside that action, copied from the previous service function. `composition.py` constructs the log, the search index, and the Postgres reader and passes them into each application type. Adapters under `infrastructure/` keep a shim at the old import path, and their logger name stays the old module name.

## Module split

The split below is the future service map. This restructure draws the seams inside the current process. It does not deploy separate processes, and it does not split the account database or the system database. The account database and the system database stay shared until a module's own documents describe that split.

A module can move to its own service later when three things are true. Callers use a port instead of importing its functions. It owns its tables. It does not import another product module's ORM models.

### Shared kernel

These stay in-process libraries. Other modules call them. Pulling one out first would turn every request into a network call.

| Module | What stays together |
| --- | --- |
| Identity | Accounts, sign-in, invites, members |
| Workspace | Tenants, membership, storage configuration |
| Governance | Privileges, securables, and the guard |
| Platform | `compassx` plus the Docker and Kubernetes drivers |

Identity and Workspace share the account database. Extract them together, or leave both in the kernel.

### Product modules

Each row is one future service. Code listed on the module page stays inside that boundary. Cross-calls become a port. The current function stays the adapter.

| Future service | Current home |
| --- | --- |
| Catalog | `backend/app/catalog` and `frontend/src/modules/data` |
| Legacy data catalog | `backend/app/data`, `backend/app/dataset` |
| Storage | `backend/app/storage` |
| SQL warehouse | `backend/app/sql_warehouse` |
| Ingestion | `backend/app/ingestion` |
| Jobs | `backend/app/jobs` |
| Notebooks | `backend/app/notebooks` |
| Dashboards | `backend/app/dashboards` |
| Ontology | `backend/app/ontology` |
| Monitoring | `backend/app/monitoring` |
| Compute | `backend/app/compute` |
| Sandbox | `backend/app/sandbox` |
| Apps | App routes, Omnigent, and `frontend/src/modules/apps` |
| Portal | Portal routes and `frontend/src/modules/portal` |
| AI Gateway | `backend/app/ai_gateway` |
| Agents | `backend/app/agents`, with Nova and Agent runtime until their tools are ports |

Shared libraries are not services. Their files join the module named in the shared-libraries document when that document is written. The old import path remains a shim.

Ontology and Monitoring have the fewest inbound imports, so they are the easiest later extractions. Catalog, Notebooks, Agents, and Nova import each other directly, so their ports come first.

## Module status

| Module | Code status | Document status |
| --- | --- | --- |
| Identity | Done | [Written](identity/index.md) |
| Workspace | Done | [Written](workspace/index.md) |
| Governance | Done | [Written](governance/index.md) |
| Platform | Done | [Written](platform/index.md) |
| Catalog | Done | [Written](catalog/index.md) |
| Legacy data catalog | Done | [Written](legacy-data-catalog/index.md) |
| Storage | Done | [Written](storage/index.md) |
| SQL warehouse | Done | [Written](sql-warehouse/index.md) |
| Ingestion | Done | [Written](ingestion/index.md) |
| Jobs | Done | [Written](jobs/index.md) |
| Notebooks | Done | [Written](notebooks/index.md) |
| Dashboards | Done | [Written](dashboards/index.md) |
| Ontology | Done | [Written](ontology/index.md) |
| Monitoring | Done | [Written](monitoring/index.md) |
| Compute | Done | [Written](compute/index.md) |
| Sandbox | Done | [Written](sandbox/index.md) |
| Apps | Done | [Written](apps/index.md) |
| Portal | Done | [Written](portal/index.md) |
| AI Gateway | Done | [Written](ai-gateway/index.md) |
| Agents | Done | [Written](agents/index.md) |
| Nova | Done | [Written](nova/index.md) |
| Agent runtime | Done | [Written](agent-runtime/index.md) |
| Shared libraries | Done | [Written](shared-libraries/index.md) |

## Document status

Catalog, Ontology, Monitoring, Ingestion, Jobs, Dashboards, SQL warehouse, Storage, Notebooks, Compute, Sandbox, Apps, Portal, AI Gateway, Agents, Nova, Agent runtime, Identity, Workspace, Governance, Platform, Legacy data catalog, and Shared libraries have overviews, topics, and test cases written from the code. Set a row to **Written** in the same change that adds or changes the pages, and register them in `content/nav.json`.

| Document | Status |
| --- | --- |
| Overview | [Overview](index.md) |
| Restructure status | This page. Keep it |
| For agents and developers | [For agents and developers](for-agents.md) |
| Identity | [Written](identity/index.md) |
| Workspace | [Written](workspace/index.md) |
| Governance | [Written](governance/index.md) |
| Platform | [Written](platform/index.md) |
| Catalog | [Written](catalog/index.md) |
| Legacy data catalog | [Written](legacy-data-catalog/index.md) |
| Storage | [Written](storage/index.md) |
| SQL warehouse | [Written](sql-warehouse/index.md) |
| Ingestion | [Written](ingestion/index.md) |
| Jobs | [Written](jobs/index.md) |
| Notebooks | [Written](notebooks/index.md) |
| Dashboards | [Written](dashboards/index.md) |
| Ontology | [Written](ontology/index.md) |
| Monitoring | [Written](monitoring/index.md) |
| Compute | [Written](compute/index.md) |
| Sandbox | [Written](sandbox/index.md) |
| Apps | [Written](apps/index.md) |
| Portal | [Written](portal/index.md) |
| AI Gateway | [Written](ai-gateway/index.md) |
| Agents | [Written](agents/index.md) |
| Nova | [Written](nova/index.md) |
| Agent runtime | [Written](agent-runtime/index.md) |
| Shared libraries | [Written](shared-libraries/index.md) |
