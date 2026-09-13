# Changelog

All notable changes to the CompassX Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.2] - 2026-09-13

### 🚀 Highlights

CompassX `0.8.2` delivers the dedicated **Interactive App Development Studio Tab**, **Named Multi-Workspace Management**, customizable workspace creation with Git branch linking, real-time live dev logs terminal, and resilient Kubernetes dev sandbox routing.

### ✨ Features & Enhancements

#### Interactive App Development Studio
- **Dedicated Development Tab**: Modular `AppDevelopmentTab` component integrating live sandbox controls, step-by-step launch progress, interactive preview frame, and embedded terminal logs.
- **Custom Named Workspaces**: Support for creating and managing explicitly named dev workspaces (`POST /api/v1/apps/{app_id}/dev/workspaces`) with branch association and directory isolation.
- **Direct Workspace Launch & Switcher**: Seamlessly launch or switch active dev sessions across different workspace folders directly from the workspace cards.
- **Dev Git Commit & Push**: Built-in modal for reviewing and committing workspace changes directly to the remote repository.

#### Dev Sandbox & Driver Enhancements
- **Dynamic Session Resumption**: Extended `start_dev_session` to automatically resolve or initialize named workspaces with RFC-compliant folder paths and database records.
- **Real-Time Dev Logs Console**: Streaming log viewer with auto-scroll, log search filter, and instant refresh for dev sandbox processes.
- **Kubernetes Ingress & Routing**: Dual-mode Ingress path and subdomain handling for dev container hosts with WebSocket and hot-module replacement (HMR) support.

---

## [0.8.1] - 2026-09-11

### 🚀 Highlights

CompassX `0.8.1` introduces **App Background Tasks & Long-Running Job Execution**, a dedicated **Workspace Settings UI & Management Suite**, enhanced **Real-Time Resource Monitoring & Metrics Collection**, and expanded **Kubernetes Driver & Sandbox Lifecycle Handling**.

### ✨ Features & Enhancements

#### App Background Tasks & Job Lifecycle
- **App Tasks Architecture**: Added database persistence and lifecycle tracking for asynchronous background tasks and job executions per application (`AppTask` model and Alembic migration `0007_app_tasks.py`).
- **Task Management API**: REST endpoints for initiating, monitoring, and canceling long-running application background tasks (`/api/v1/apps/{app_id}/tasks`).
- **Frontend App Task Studio**: Built-in task monitoring console in `AppDetailPage` with task execution states, duration timers, status badges, and logs inspection.

#### Workspace Settings & Administration
- **Workspace Settings Page**: Dedicated configuration view (`WorkspaceSettingsPage`) for managing workspace details, general preferences, quotas, and metadata.
- **Backend Workspace Management**: Added workspace configuration and update endpoints in `workspace_routes.py`.

#### Real-Time Platform Monitoring & Collectors
- **Enhanced Resource Metrics**: Platform collectors (`collectors.py`) and manager (`manager.py`) updates for tracking live CPU, memory, and container workload utilization.
- **Monitoring Console Updates**: Dynamic metric charts and status cards in `MonitoringPage.tsx`.

#### Kubernetes Driver & Local-Dev Enhancements
- **Dynamic Status & Lifecycle**: Enhanced container status resolution and sandboxed runner management in `kubernetes_driver.py` and `app_runner.py`.
- **Local Development Profile**: Extended `docker-compose.local-dev.yml` override mappings and profile registry support for streamlined local development.

---

## [0.8.0] - 2026-09-10

### 🚀 Highlights

CompassX `0.8.0` delivers major platform expansions including **End-to-End Dev Workspace Management in Omnigent**, native **MLflow Tool Integration & Platform Connections**, baked MLflow notebook kernel runtimes, and critical Gemini LLM function-calling compatibility.

### ✨ Features & Enhancements

#### Omnigent Dev Workspace Management
- **Multi-Workspace Lifecycle**: Full support for creating, listing, and deleting isolated development workspaces per application with dedicated database persistence (`DevWorkspace` model and Alembic migration `0006_dev_workspaces.py`).
- **Kubernetes & Docker Dev Drivers**: Enhanced dev sandbox container management with unique workspace IDs, dynamic session handling, and robust resource allocation.
- **Frontend App Dev Studio**: Integrated workspace lifecycle controls directly into `AppDetailPage` with intuitive workspace cards, loading indicators, and delete confirmation dialogs.

#### MLflow Integration & MLOps Tooling
- **Platform Tool & Connection Provider**: Added `MlflowTool` for experiment tracking, run logging, metric/parameter queries, and model registry management via direct asynchronous REST API dispatch.
- **Catalog Connections**: Added MLflow tracking connection provider in the Catalog Connections registry.
- **Frontend Agent Tool Catalog**: Registered `mlflow` in the agent tool registry for agent capability assignment.
- **Notebook Runtime Support**: Baked `mlflow` into the DuckDB kernel image (`Dockerfile.compute-duckdb`) for zero-setup experiment tracking directly in interactive notebooks.
- **Docker Compose Stack**: Integrated MLflow tracking server container backed by PostgreSQL and MinIO object storage.

### 🧹 Bug Fixes & Improvements

#### LLM Client
- **Gemini Tool Call Formatting**: Corrected tool result message role from `tool` to `user`, resolving 400 INVALID_ARGUMENT errors in Gemini agent function execution loops.

#### Multi-Architecture Local Development
- **ARM64 / Apple Silicon Support**: Configured local build fallbacks for auxiliary services (`enterprise-gateway`, `airflow-notebook-runner`) in `local-dev` profile to eliminate platform architecture incompatibilities.

---

## [0.7.2] - 2026-09-08

### 🚀 Highlights

CompassX `0.7.2` introduces the full-stack **App Deployments & Live Build Logs Terminal**, dynamic **Kubernetes Dev Sandbox & Omnigent Integration** with hot-reloading and workspace sync, plus automated TLS and WebSocket-enabled Ingress routing for deployed user applications.

### ✨ Features & Enhancements

#### Apps Runtime & Omnigent Dev Sandbox
- **Kubernetes Dev Sandbox**: Added dynamic dev sandbox pod provisioning integrating Omnigent Server with hot-reloading, Git workspace synchronization, and internal cluster IP routing.
- **Dynamic Ingress & WebSocket Support**: Automated host routing, TLS certificate assignment, and WebSocket annotations for responsive real-time dev server sessions.
- **Deployments & Build Logs Console**: Full-stack build history sidebar and real-time streaming terminal with log level filtering, auto-scroll, copy, and log export utilities.

---

## [0.7.1] - 2026-09-07

### 🚀 Highlights

CompassX `0.7.1` delivers critical runtime engine improvements for Kubernetes application provisioning, automatic RFC 1123 resource label sanitization, dynamic Streamlit/Node execution containers, and enhanced Helm RBAC roles.

### 🧹 Bug Fixes & Platform Enhancements

#### Kubernetes App Runtime Driver
- **RFC 1123 Label & Name Sanitization**: Automatically sanitize all application IDs and selector labels to strictly comply with Kubernetes DNS subdomain formatting.
- **Dynamic Container Execution Pipeline**: Implemented resilient entrypoint preparation and runtime fallback handling for Streamlit and Node container workloads.
- **Subresource & Ingress RBAC**: Expanded Helm Role permissions to support `networking.k8s.io` Ingresses and status subresources (`deployments/status`, `services/status`, `ingresses/status`).
- **Container Tooling**: Bundled `git`, `curl`, and `ca-certificates` into backend production images.
- **K8s Client Networking Access**: Added missing `.networking()` accessor method to platform Kubernetes API client wrapper.

---

## [0.7.0] - 2026-09-07

### 🚀 Highlights

CompassX `0.7.0` introduces the full-stack **Interactive Knowledge Graph & Ontology Visualization Engine**, the next-generation **Apps Development Platform** with Omnigent Dev Studio integration and multi-mode application deployment, plus catalog tool query fallbacks and architectural cleanups.

### ✨ Features & Enhancements

#### Knowledge Graph & Ontology Studio
- **Interactive Graph Visualization**: Implemented dynamic 2D/3D dome graph rendering for complex knowledge graphs, entities, and relationships.
- **Ontology Configuration Panel**: Added dynamic kinds and relationship management, node creation modals, side drawer inspection, and responsive canvas toolbars.
- **Theme Support**: Integrated instant light/dark mode theme switching across the ontology studio canvas.

#### Apps Development Platform
- **Multi-Mode Application Deployment**: Added native support for deploying Vite Single Page Applications, Next.js, Streamlit, and custom Docker container apps.
- **Omnigent Dev Studio Integration**: Seamless development environment embedding for rapid application authoring and live hot-reloading.
- **Apps Home & Lifecycle Dashboard**: Created `AppsHomePage` component for searching, deploying, monitoring, and managing application instances.

#### Data Catalog & Compute
- **Catalog Tool Enhancements**: Added `list_tables` operation and automatic empty query fallback handling in `CatalogTool`.
- **Runtime Images**: Bumped compute runtime images (`compute-duckdb`, `airflow-notebook-runner`) to `v0.7.0`.

### 🧹 Cleanup & Bug Fixes
- Removed stale asset manager modules and dead entity interfaces across backend, frontend, and deployment manifests.
- Bumped platform and component versions to `0.7.0`.

---

## [0.6.1] - 2026-09-04

### 🚀 Highlights
- Apps ecosystem management and initial multi-mode application runner preview.

---

## [0.6.0] - 2026-09-03

### 🚀 Highlights
- Major module cleanup and unified workspace navigation.

---

## [0.5.2] - 2026-09-02

### 🐛 Bug Fixes
- **Frontend JupyterLab Services Request Parsing**: Fixed `input.toString()` evaluating to `[object Request]` when `@jupyterlab/services` passed `Request` objects to custom `fetch` wrapper by extracting `input.url` and cloning headers properly.

---

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
