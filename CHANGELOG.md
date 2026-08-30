# Changelog

All notable changes to the CompassX Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.0] - 2026-08-30

### 🚀 Highlights

CompassX `0.4.0` introduces end-to-end Governance and Access Control components, interactive notebook code diff reviews, enhanced dashboard filters and customized table configuration engines, persistent agent session plans with turn inspection, and a comprehensive platform documentation suite.

### ✨ Features & Enhancements

#### Governance & Access Control
- **Unified Securable Permissions**: Added full-stack securable permission management for databases, schemas, tables, storage volumes, and compute resources.
- **Ownership Management**: Introduced `OwnerName` and `OwnerBadge` components for securable ownership inspection.
- **Principal Picker & Grant Dialogs**: Implemented `PrincipalPicker` and `PermissionsPanel` for granular privilege grants, revocations, and effective access resolution.
- **Governance Client & Hooks**: Added frontend governance API client and React Query hooks (`useGovernance`).

#### AI Agents & Interactive Chat
- **Session Plans Persistence**: Integrated `useSessionPlans` to fetch, persist, and render execution plans for agent chat sessions.
- **Turn & Diff Review Docks**: Enhanced `AgentChatPage` with unified turn edit badges, file modification markers, and change rejection/reversion handling.
- **Context Watermark Badges**: Added `ContextUsageBadge` to display token utilization, high-watermark context window limits, and turn compaction metrics.
- **Tool Catalog Refactoring**: Cleaned up deprecated tools and tightened model dispatch pathways.

#### Notebooks & Code Actions
- **Inline Cell Diffs**: Added granular per-cell accept/reject diff buttons in `CodeCell` and editor line diff indicators in CodeMirror.
- **Bulk Diff Review**: Introduced bulk acceptance and rejection actions in `NotebookToolbar` and Zustand `notebookStore`.
- **Side Effect Safeguards**: Added database side effect confirmation dialogs for mutating SQL/Python operations.

#### Dashboards & Visualizations
- **Filter Configuration Engine**: Introduced `FilterConfigSection` supporting single-value, multi-value, and date-range filter widgets with placement controls.
- **Dynamic Dataset Filtering**: Added utility functions (`filterUtils`) to dynamically filter chart dataset rows based on active dashboard filter states.
- **Table Visualizer Enhancements**: Created `TableConfigSection` with column selection, sorting, custom title row styling (`TableTitleRowColorPicker`), and header style popovers.
- **Metric Counter Transformations**: Added `aggregateValues` data transform support for numeric calculations and delta comparisons.

#### Infrastructure & Platform Engine
- **Database Connection Pooling**: Increased SQLAlchemy engine pool sizing and timeout parameters for high concurrency.
- **Schema Migrations**: Cleaned up Alembic migrations and dropped deprecated LLM memory-provider flags.
- **Documentation Suite**: Added complete MkDocs documentation covering Platform Architecture, Compute Clusters, Data Catalogs, Governance, Jobs, and Notebooks.

### 🐛 Bug Fixes
- Fixed React ref typing and Lucide icon title attributes across agent chat components.
- Fixed change capture revert record status propagation on change rejection.
- Fixed workspace context isolation in agent tool execution and resource creation endpoints.
- Fixed FastAPI app version metadata to accurately report `0.4.0`.

---

## [0.3.0] - 2026-08-25

### Features & Fixes
- Updated Airflow notebook runner container configurations and volume mounts.
- Improved database connection pool defaults for PostgreSQL backend.
- Synchronized Helm chart templates and Kubernetes deployment manifests.

---

## [0.2.0] - 2026-08-18

### Features & Fixes
- Added multi-cloud deployment values for AWS, Azure, and GCP.
- Implemented Docker Compose multi-container stack with pgvector and MinIO.
- Added session streaming endpoints and agent artifact handling.

---

## [0.1.0] - 2026-08-10

### Initial Release
- Core FastAPI backend with unified data catalog, SQL warehouse, and Jupyter execution gateway.
- React + Vite frontend workspace shell with Notebooks, Dashboards, and Agent Chat interfaces.
