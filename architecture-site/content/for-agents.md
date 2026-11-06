# For agents and developers

Catalog, Ontology, Monitoring, Ingestion, Jobs, Dashboards, SQL warehouse, Storage, Notebooks, Compute, Sandbox, Apps, Portal, AI Gateway, Agents, Nova, Agent runtime, Identity, Workspace, Governance, Platform, Legacy data catalog, and Shared libraries are written. Write a new page from the code, then update the matching Markdown in the same change. Do not describe a behavior the code does not implement.

## Where a page lives

A module is a folder under `architecture-site/content/<module>/`.

- `index.md` is the overview. It states the role, the current code paths, what the module owns, and what it calls.
- Another file in that folder is one topic, such as `notebooks/authenticate-kernel.md`. Add it when the subject is large enough to read on its own.
- `test-cases.md` is the plain-English end-to-end cases for that module. A person or an agent runs them in the product. They are not code tests.
- `tools.md` is required when the module exposes a tool: an agent tool it registers, a tool record it stores, or a tool HTTP route it owns. Document how the tool is called and what the caller sees, and add a test case that runs it. Skip the page when the module exposes no tool.
- Register every page in `content/nav.json` under that module's section.

Do not add a site-wide Runtime section or a site-wide Decisions section. Provisioning, authentication, setup, and technical choices are topics of the module that owns them.

## When a module is restructured

Follow the guideline on [Restructure status](restructure-status.md). Keep that page. Read the existing code, understand the functionality, write the logical pages in depth, write the plain-English test cases, restructure the code, then update those pages if the split changed them.

While doing that:

1. Keep the public HTTP routes, JSON bodies, database writes, log text, log level, and public Python import paths working.
2. One application file owns one action. A facade at the old `routes.py` or `service.py` path forwards to it.
3. Keep the logger name that the code used before the move.
4. Update `content/<module>/index.md` so the packages, owners, and calls match the code.
5. Add or update a topic page in the same folder when a user path or a technical choice needs its own page.
6. Add the new page to `content/nav.json` under that module.

Leave Identity, Workspace, Governance, and Platform in this process. Leave the legacy data catalog separate from Catalog. SQLAlchemy models stay the persistence model.

## What a topic page contains

State who starts the action, which modules handle each step, and where auth and data move. Name the decision and what a later change must preserve. Leave the page marked **Not traced** until those steps are read from the code.

`content/notebooks/index.md` is served at `/notebooks`. A topic file such as `content/notebooks/authenticate-kernel.md` is served at `/notebooks/authenticate-kernel`.
