# Changelog

All notable changes to the CompassX Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-09-02

### 🐛 Bug Fixes
- **Notebook Kernel & Jupyter Proxy Governance**: Resolved `Not authenticated for a workspace` 401 error by introducing automatic fallback workspace resolution in `WorkspaceMiddleware` and `get_principal` for authenticated requests lacking explicit workspace slugs.
- **Frontend JupyterLab Services**: Enhanced `ServerConnection.makeSettings` custom fetch and headers to attach `X-Workspace-Slug`, `Authorization`, and `?workspace=` across all Jupyter REST and WebSocket channels.
- **Monitoring Collector Mocking**: Fixed Docker client mock initialization in unit test suite.

---

## [0.5.0] - 2026-09-02

### 🚀 Highlights

CompassX `0.5.0` introduces a unified Platform Monitoring & Observability subsystem with Prometheus metric exports, real-time node and pod telemetry dashboards, compute scaling and Kubernetes RBAC automation, an automated pre-install Helm database migration job template, and hardened AI chat session error handling and message persistence.

### ✨ Features & Enhancements

#### Platform Monitoring & Observability
- **Prometheus Metrics Exporter**: Implemented `/monitoring/metrics` with standard Prometheus metrics formatting for Kubernetes, Docker, and host processes.
- **Monitoring Manager & Collectors**: Added `MonitoringManager`, `KubernetesCollector`, `DockerCollector`, and `LocalProcessCollector` with automated fallback telemetry pipelines.
- **Interactive Monitoring Dashboard**: Added full-stack `MonitoringPage` displaying real-time cluster health, node utilization, API request latency breakdowns, and active pod statuses.
- **Collector Verification**: Added comprehensive unit test coverage for monitoring manager metrics aggregation and collectors.

#### Compute & Kubernetes Driver
- **Dynamic Compute Scaling**: Enhanced Kubernetes driver with dynamic replica scaling, zero-downtime rolling restart orchestration, and pod status reconciliation.
- **Runtime Spec Builders**: Standardized container image referencing across DuckDB, Spark, Ray, and Flink compute profiles.

#### Helm & Deployments
- **Automated Database Migration Hook**: Added Kubernetes Helm `pre-install`/`pre-upgrade` migration job (`migration-job.yaml`) with Alembic system and account database auto-upgrades.
- **Role & RBAC Hardening**: Granted `deployments/scale` and `pods/exec` RBAC permissions to backend and operator service accounts.
- **Single-Instance PVC Recreate Strategy**: Updated Airflow and persistent stateful services to use `Recreate` deployment strategy.

#### AI Agents & Interactive Chat
- **Error Handling & Retry Mechanics**: Hardened stream routes with structured error payloads and token validation recovery.
- **Message & Turn Persistence**: Enhanced chat session state synchronization and turn execution recovery.

### 🐛 Bug Fixes
- Fixed Airflow container environment variable ordering in Helm deployment templates.
- Fixed DuckDB compute runtime container image constant resolution in test suites and spec builders.
- Bumped platform and component versions to `0.5.0`.

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
