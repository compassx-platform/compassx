# Platform Architecture

The internal guide for CompassX. Developers and agents read these same Markdown files. This site only displays them.

The current code is the source of truth. A page describes what the code does today. When a module is restructured, its page is updated in the same change.

Catalog, Ontology, Monitoring, Ingestion, Jobs, Dashboards, SQL warehouse, Storage, Notebooks, Compute, Sandbox, Apps, Portal, AI Gateway, Agents, Nova, Agent runtime, Identity, Workspace, Governance, Platform, Legacy data catalog, and Shared libraries are written. The restructuring guideline and the module status stay on the [restructure status](restructure-status.md) page.

## How the pages are organized

Each module is one section in the sidebar. The first page is the overview. Further pages are topics inside that module, so an agent can open one subject without reading the rest. Each module also has test cases: plain-English uses a person or an agent runs in the product, such as creating a notebook, reading a catalog table, changing the data, and storing it again.

Write those pages from the code before restructuring the module. Until then the sidebar section stays empty. The modules named above have their pages written.

Product how-to guides stay in the MkDocs site under `docs/`. This site does not replace them.

