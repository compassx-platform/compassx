# Screen

Platform has two surfaces a person actually uses. Operators use the `compassx` command. People inside a workspace use the Platform shell.

The shell is the app id `platform` in `frontend/src/lib/appNavigation.ts`. It is the default app. A workspace URL is `/w/{slug}/platform/...`. Legacy paths `/platform` and the aliases `business` and `business_center` are the same app. The home page title is `Home`.

The app switcher shows Platform, Apps, and Portal to an account admin or a workspace developer. A member or a viewer sees Portal only.

The sidebar groups are:

- Home, Notebooks, Jobs, Dashboards
- Data: Data Catalog, SQL Editor, SQL Warehouses, Query History
- AI & Meaning: Agents, Agent Runtime, AI Gateway, Ontology, Connections
- Infra: Compute, Monitoring

Those pages belong to their own modules. This shell only chooses which routes are in the Platform app.

Account Settings has a section heading `Platform Services & Orchestration` and a row labeled `Apache Airflow Webserver`. The badges on that row are `RUNNING ({available}/1)`, `STARTING...`, and the stopped state. That screen writes account settings. The Airflow start and stop HTTP routes are the ones in [Service HTTP](services.md).

There is no separate page whose heading is Platform. The operator status is the CLI table, not a browser screen.
