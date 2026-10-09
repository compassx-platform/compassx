# Changelog

All notable changes to the CompassX Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.12.24] - 2026-10-09

### 🚀 Highlights

CompassX `0.12.24` introduces **Persistent Antigravity & AI Agent Authentication Across Sandbox Pod Restarts**, **Automated Shared Storage PVC Auto-Mounting (`compassx-shared-storage`)**, and **Bi-directional Daemonized Agent Credential Synchronization**.

### ✨ Features & Enhancements

#### Persistent Antigravity & AI Agent Authentication
- **Dual-Layer Token Persistence (`k8s_driver.py`, `app_dev_routes.py`, `kubernetes_driver.py`)**: Persists Antigravity OAuth tokens (`antigravity-oauth-token`, `oauth_creds.json`, `jetski_state.pbtxt`, `installation_id`, `config.json`, `mcp_config.json`) across container restarts by backing them up to both the persistent workspace repo volume (`/workspace/.gemini_auth`) and the cluster shared storage PVC (`/workspaces/.shared_auth/.gemini`).
- **Cluster Shared Storage PVC Auto-Mounting (`k8s_driver.py`)**: Automatically detects and mounts `compassx-shared-storage` PVC at `/workspaces` (with subPath `workspaces`) whenever present in the cluster namespace, enabling seamless cross-pod credential and asset sharing.
- **Continuous Auth Sync Daemon (`app_dev_routes.py`)**: Runs an asynchronous background sync loop in sandboxes every 5 seconds, capturing refreshed OAuth tokens and state changes in `/root/.gemini/` and syncing them instantly to persistent storage without disrupting running dev servers.
- **Terminal Session Pre-Seeding (`kubernetes_driver.py`, `docker_driver.py`)**: Automatically ensures `/root/.gemini` authentication files are restored and permissions set upon terminal attachment and exec command execution.

---

## [0.12.23] - 2026-10-09

### 🚀 Highlights

CompassX `0.12.23` introduces **Universal Clipboard Support with Seamless Non-Secure/HTTP Fallbacks**, **Native OSC 52 Terminal Clipboard Sequence Handling**, **Enhanced Multi-Key Selection & Copy-Paste Shortcuts**, and **Tmux Driver Clipboard Integration**.

### ✨ Features & Enhancements

#### Universal Terminal Clipboard Architecture
- **Universal Clipboard Fallback Engine (`terminalClipboardWriter.ts`)**: Implemented dual-mode clipboard write/read handlers with seamless fallback to offscreen `textarea` selection and `document.execCommand('copy')` when running on non-secure origins (HTTP or direct IP addresses) where `navigator.clipboard` is restricted.
- **Native OSC 52 Protocol Support (`TerminalSession.ts`)**: Added parser hooks for OSC 52 clipboard write escape sequences (`\x1b]52;...`), allowing terminal applications like `tmux`, `vim`, `emacs`, and CLI tools to copy text directly to the user's system clipboard.
- **Enhanced Select-to-Copy & Mouse Actions (`TerminalSession.ts`, `TerminalView.tsx`)**: Auto-copy on mouse highlight and container `mouseup` triggers across both xterm buffer selections and fallback DOM text selections.
- **Multi-Key Copy/Paste Keyboard Shortcuts (`TerminalSession.ts`)**: Added support for `Ctrl+C`, `Cmd+C`, `Ctrl+Shift+C`, and `Ctrl+Insert` (copying selected text without sending `SIGINT` \x03 to terminal processes), as well as `Shift+Insert` and `Ctrl+V` for clipboard pasting.
- **Context Menu Actions (`TerminalView.tsx`)**: Direct context menu copy and paste handlers utilizing universal clipboard helpers.

#### Tmux & Container Driver Integration
- **Driver Clipboard Settings (`docker_driver.py`, `kubernetes_driver.py`)**: Configured tmux session defaults with `set -s set-clipboard on`, `set -g allow-passthrough on`, mouse drag end copy bindings, and copy-mode `y` keybindings.
- **Pre-initialized Pod Tmux Configuration (`kubernetes_driver.py`)**: Pre-populates `/root/.tmux.conf` on Kubernetes terminal session launch to ensure consistent copy-paste behavior across all pod exec sessions.

---

## [0.12.22] - 2026-10-09

### 🚀 Highlights

CompassX `0.12.22` introduces **Automated Git Authentication & Auto-Start in Kubernetes Sandboxes**, **Robust Multi-Repo Base Detection with Remote Reconfiguration**, and **Cross-Container App Manifest Live Synchronization**.

### ✨ Features & Enhancements

#### Automated Kubernetes Sandbox Provisioning & Auto-Start
- **Authenticated Repo Init & Auto-Clone (`app_dev_routes.py`)**: Sandboxes automatically configure Git credentials (`x-access-token` for GitHub, `oauth2` for other providers), clone workspace repositories into `/workspace`, install multi-tier dependencies (`pip`, nested `npm`), and launch background process supervisors with built-in port 8080 reverse proxying.
- **Robust Base Repository Detection (`kubernetes_driver.py`)**: Detects valid Git repositories via `git rev-parse --verify HEAD` avoiding empty or stale initialized directories, and automatically updates remote origin URLs.

#### Live Manifest Synchronization
- **Live Container Manifest Sync (`app_dev_routes.py`, `omnigent_dev_service.py`)**: Updating `app.yaml` in the UI immediately broadcasts and writes the configuration into running sandbox pods (`/workspace/app.yaml`, `/workspaces/*/*/app.yaml`).
- **Extended Manifest Probing (`omnigent_dev_service.py`)**: Resolves app manifests across full container workspace hierarchies when not directly mounted on the host filesystem.

---

## [0.12.21] - 2026-10-09

### 🚀 Highlights

CompassX `0.12.21` introduces **Full-Stack Runtime Configuration & `app.yaml` Editor in App Settings**, **Streamlined Python Reverse Proxy Sandbox Execution**, and **Real-Time Gateway Port Synchronization**.

### ✨ Features & Enhancements

#### Visual `app.yaml` & Runtime Configuration in App Details
- **Multi-Service Visual Editor (`AppDetailPage.tsx`, `useApps.ts`)**: Added dedicated configuration panels for Frontend UI Service (startup command, internal port, working directory) and Backend API Service (startup command, internal port, working directory) within App Detail Settings.
- **Custom Dependency Installer (`AppDetailPage.tsx`)**: Configurable pre-startup installation command (`npm install`, `pip install -r requirements.txt`) executing prior to service launch.
- **Port 8080 Routing Topology Visualizer (`AppDetailPage.tsx`)**: Interactive routing visualizer highlighting traffic flow (`/*` to frontend UI, `/api/*` and `/ws/*` to backend API).

#### Streamlined Sandbox Reverse Proxy Launch
- **Pure-Python Reverse Proxy Daemon (`omnigent_dev_service.py`)**: Dev sandboxes launch a lightweight zero-dependency Python reverse proxy (`/tmp/reverse_proxy.py`) on port 8080 during container startup for reliable multi-service multiplexing across local and Kubernetes profiles.

---

## [0.12.20] - 2026-10-09

### 🚀 Highlights

CompassX `0.12.20` introduces **Full-Stack App Reverse Proxying & Caddyfile Generation**, **Seamless Port 8080 Gateway Routing**, **Enhanced Dev Terminal Resizing & Session Lifecycle**, and **Cross-Profile Dev Driver Testing**.

### ✨ Features & Enhancements

#### Full-Stack App Reverse Proxying & Port 8080 Gateway
- **Automated Caddy & Proxy Scripts (`app_manifest_service.py`)**: Added `generate_caddyfile` and `generate_proxy_script` fallback generator in `AppManifestService` to route frontend UI traffic (`/`) and backend API traffic (`/api`, `/ws`, `/docs`, `/openapi.json`) cleanly through unified port 8080.
- **Flexible Service Manifest Parsing (`app_manifest_service.py`)**: Enhanced manifest resolution to automatically parse multi-service configurations (`services.api`, `services.web`, `backend_port`, `frontend_port`, `gateway_port`, `backend_path`, `frontend_path`).
- **Dynamic Gateway Startup (`omnigent_dev_service.py`)**: Sandboxes automatically launch the unified reverse proxy gateway when full-stack multi-process applications are detected.

#### Terminal Session & UI Reliability
- **Interactive Terminal Lifecycle (`TerminalSession.ts`, `TerminalView.tsx`)**: Upgraded terminal resize debouncing, auto-fit geometry synchronization, reconnect resilience, and proper session teardown for the Output Drawer dev terminal.

---

## [0.12.19] - 2026-10-08

### 🚀 Highlights

CompassX `0.12.19` introduces **AI Agent Studio Workspace Refactoring**, **Isolated Interactive Shell & Dev Terminal Output Drawer**, **Multi-Branch Base Selection in Browser Toolbar**, and **Hardened Driver Session Management**.

### ✨ Features & Enhancements

#### AI Agent Studio & Workspace Architecture
- **Dedicated Left Studio Layout (`AppBuildPage.tsx`, `OmnigentChatPanel.tsx`)**: Refactored the left panel exclusively for AI Agent Studio chat, code editing, and split view workflows with streamlined tab navigation.
- **Dedicated Shell & Terminal Drawer (`OutputDrawer.tsx`)**: Replaced cramped side-panel terminal switches with a bottom collapsible output drawer supporting full interactive Dev Terminals, live runtime container logs, and diagnostic tracing.
- **Dynamic Branch & Base Target Switching (`BrowserToolbar.tsx`)**: Added support for base branch resolution (`git_branch` / `main`) and direct branch context display in the live preview toolbar.

#### Hardened Driver Session & Process Management
- **Tmux Session Isolation (`omnigent_dev_service.py`)**: Filtered out shell sessions (`cx_shell_`, `shell_`) from AI agent prompt forwarding and terminal buffer capture, preventing session collisions between user interactive terminals and background AI coding agents.
- **Timestamped Setup Diagnostics (`omnigent_dev_service.py`)**: Added phase logging with timestamps to `/tmp/workspace_setup.log` for deterministic visibility into workspace repository cloning, dependency installs, and service health probes.

---

## [0.12.18] - 2026-10-08

### 🚀 Highlights

CompassX `0.12.18` introduces **Unified Sandbox Pod Resolution**, **Dynamic Phase Lifecycle Tracking**, and **Platform-Wide Typing & Route Cleanups**.

### ✨ Features & Enhancements

#### Unified Sandbox Pod & Annotation Resolution
- **Multi-Selector Kubernetes Resolution (`kubernetes_driver.py`)**: `_get_dev_pod_name` resolves active pods across both unified sandbox label selectors (`compassx.sandbox-id`, `compassx.consumer-key`, `compassx.app_id`) and legacy deployment names, including annotation matching (`compassx.sandbox.id`, `compassx.sandbox.consumer_key`).
- **Dynamic Phase Tracking (`k8s_driver.py`, `docker_driver.py`)**: Tracks pod lifecycle transitions (`Running`, `Provisioning`, `Failed`) accurately during creation and discovery rather than assuming immediate running state.

#### Codebase & Type Cleanup
- **SQLAlchemy & Pydantic Cleanups**: Cleaned up schema imports and typing annotations across chat, catalog connections, dashboards, dataset, notebooks jupyter proxy, dev routes, omnigent dev service, and workspace account routes.

---

## [0.12.17] - 2026-10-08

### 🚀 Highlights

CompassX `0.12.17` introduces **Fuzzy & Normalized Sandbox Discovery**, **Accurate Kubernetes Endpoint Resolution**, and **Enhanced Live Preview Controls**.

### ✨ Features & Enhancements

#### Fuzzy & Normalized Sandbox Discovery
- **Cross-Identifier Reconciliation (`backend/app/sandbox/service.py`)**: Added `_normalize_key` matching across sandbox IDs, consumer keys (`app_<id>`), pod labels (`compassx.consumer-key`, `compassx.sandbox-id`), and app metadata to resolve existing instances accurately without duplicate provisioning.
- **Dynamic Kubernetes Driver Discovery (`backend/app/sandbox/drivers/k8s_driver.py`)**: Directly discovers and updates running dev sandboxes, pod names, and port endpoints across cluster namespaces.

#### Enhanced Live Preview Canvas & Embedded Controls
- **Top Navigation Bar (`LivePreviewCanvas.tsx`, `AppBuildPage.tsx`)**: Added integrated top-bar preview controls with address bar, refresh button, open-in-new-tab action, responsive viewport modes (Desktop, Tablet, Mobile), and in-flight health probing indicators.

---

## [0.12.16] - 2026-10-08

### 🚀 Highlights

CompassX `0.12.16` delivers **Compute Sandbox Environment Management**, **App Dev Sandbox Lifecycle Hardening**, and **Dedicated Compute Pool Node Routing**.

### ✨ Features & Enhancements

#### Unified Compute Sandboxes
- **Multi-Driver Sandbox Framework (`backend/app/sandbox/`)**: Added complete architecture for self-contained, isolated development sandboxes supporting Docker, Kubernetes, and Local execution drivers with automated port routing and lifecycle controls.
- **Compute Sandboxes UI (`ComputePage.tsx`, `ComputeSandboxesTable.jsx`, `CreateSandboxModal.jsx`)**: Integrated sandboxes tab into the Compute Management hub to inspect, launch, suspend, and configure compute sandboxes with customizable CPU/memory profiles and image specifications.

#### App Dev Sandbox Lifecycle & Live Preview
- **Targeted Sandbox Creation & Ensure Routes (`app_dev_routes.py`, `useApps.ts`)**: Added dedicated `ensure_dev_environment` and branch-scoped sandbox provisioning endpoints with optimistic state updates in `AppBuildPage.tsx`.
- **Live Preview Canvas Resilience (`LivePreviewCanvas.tsx`)**: Enhanced frame reloading and fallback error handling during sandbox branch switching.

#### Infrastructure & Node Pool Scheduling
- **Compute Pool Node Routing (`kubernetes_driver.py`)**: Dev sandboxes and compute workloads now explicitly schedule onto the dedicated autoscaling `computepool` (`aks-computepool-*`) nodes.
- **Standardized DB Port Default (`config.py`)**: Unified default PostgreSQL port to standard `5432`.

---

## [0.12.15] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.15` introduces **Automated Ingress & nip.io Host Allowance for Vite Dev Sandboxes** across Docker and Kubernetes runtime drivers.

### ✨ Features & Enhancements

#### Vite Dev Host Dynamic Patching
- **Recursive Configuration Discovery (`docker_driver.py`, `kubernetes_driver.py`)**: Recursively scans all workspace directories for `vite.config.*` (`.ts`, `.js`, `.mjs`, `.cjs`, `.mts`) and dynamically patches `allowedHosts: true`, preventing `Blocked request: Host is not allowed` errors on `nip.io` and custom ingress domains.
- **Auto-Provisioning Fallback (`kubernetes_driver.py`)**: Automatically creates a preconfigured `vite.config.js` with `allowedHosts: true` and HMR port mappings if a project contains Vite dependencies but lacks an explicit Vite config file.

---

## [0.12.14] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.14` introduces a **Production Fullstack Gateway** for unified static asset serving and backend API proxying in production containers.

### ✨ Features & Enhancements

#### Production Fullstack Gateway & API Routing
- **Integrated Python Gateway (`kubernetes_driver.py`)**: Built an embedded, lightweight `ThreadingHTTPServer` (`/tmp/cx_gateway.py`) inside production app containers to simultaneously serve built frontend assets (`dist/`, `build/`) on port 8080 and transparently proxy `/api/*`, `/healthcheck`, and backend endpoints to the co-located Python backend on port 8000.
- **Auto-Detection for Fullstack & Static Layouts (`kubernetes_driver.py`)**: Seamlessly handles fullstack setups (frontend static dist + Uvicorn/FastAPI backend), standalone backend frameworks (FastAPI, Streamlit, Flask, Bottle), and pure static single-page apps without requiring separate ingress rewrites or external reverse proxies.

---

## [0.12.13] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.13` introduces a **Zero-502 Dev Splash Supervisor**, **Direct Source Subdirectory (`git_subdir`) Binding**, and **Recursive Multi-Layer `node_modules` Symlinking**.

### ✨ Features & Enhancements

#### Zero-502 Splash Supervisor & Port 8080 Handover
- **Instant Live Splash Screen (`docker_driver.py`, `kubernetes_driver.py`)**: Dev-runner immediately boots a responsive splash page on port 8080 during sandbox start/reload, eliminating initial 502 Bad Gateway / connection refused errors while dependencies and dev servers initialize.
- **Clean Handover & Watchdog (`kubernetes_driver.py`)**: Dev-runner cleanly terminates the splash supervisor and frees port 8080 immediately before launching the active frontend/backend process; includes an 8-second watchdog to auto-serve built static outputs (`dist/`, `build/`) if the dynamic dev server fails to bind.

#### Source Subdirectory (`git_subdir`) Path Resolution
- **Subdirectory Binding (`kubernetes_driver.py`, `docker_driver.py`)**: Dev-runner and production container builders directly honor `git_subdir` / `APP_SUBDIR` across workspaces, allowing nested multi-package apps to launch and build cleanly without directory ambiguity.

#### Recursive Multi-Layer `node_modules` Symlinking
- **Deep Dependency Linking (`kubernetes_driver.py`)**: Recursively locates pre-installed `node_modules` across parent and sibling workspace paths up to 5 levels deep, significantly accelerating startup and avoiding redundant npm install operations.
- **AGY Security Trusted Bypass (`kubernetes_driver.py`)**: Automatically configures trusted workspace security overrides in dev environments to prevent blocking modal prompts during automated tool execution.

---

## [0.12.12] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.12` delivers **Production Auto-Reload Protection & Directory Targeting**, **Dev Pod Metadata Discovery**, and **Fuzzy App Matching in Sandbox Reaper**.

### ✨ Features & Enhancements

#### Production Auto-Reload Protection & Target Directory Scoping
- **Cloud/Pod Auto-Reload Disabling (`app.py`, `values.yaml`)**: Explicitly disables Uvicorn watchfiles auto-reload when running in Kubernetes or cloud production (`COMPASSX_BACKEND_RUNTIME=pod`, `COMPASSX_ENV=production`), preventing worker restart loops caused by high-frequency shared filesystem events.
- **Scoped Watch Directories (`app.py`)**: Restricts local dev auto-reload tracking explicitly to the `app/` directory while excluding `storage/`, `workspaces/`, `node_modules/`, `.git/`, and build directories.

#### Multi-Source Dev Pod App Metadata Discovery
- **Comprehensive Identifier Discovery (`kubernetes_driver.py`)**: Enhanced `list_running_dev_app_ids()` to inspect pod annotations (`compassx.io/app-id`), environment variables (`APP_ID`), and pod labels (`compassx/app-id`) across running dev deployments, ensuring accurate reconciliation even during partial updates.

#### Fuzzy App Matching & Reaper Resilience
- **Fuzzy Identifier Normalization (`sandbox_reaper_service.py`)**: Added hyphen/underscore normalization and alphanumeric fuzzy matching to prevent false-positive orphan detection and unintentional teardown of active dev workloads.
- **Reaper Bug Fix**: Resolved missing regex module import in idle reaper background sweep task.

---

## [0.12.11] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.11` introduces a **Single Active Dev Pod Guarantee**, **Cluster-Wide Idle Dev Pod Sweeping**, and **Optimistic React Sandbox Switching State**.

### ✨ Features & Enhancements

#### Single Active Dev Pod Guarantee & Lifecycle Hardening
- **Single Active Pod per App (`omnigent_dev_service.py`)**: `start_dev` and `switch_active_sandbox` verify existing pod presence before provisioning, reusing active pods and dispatching in-place dev-runner reload commands to avoid duplicate pods.
- **Synchronized Status Updates (`omnigent_dev_service.py`)**: Comprehensive database updates transition all active DevWorkspace rows to `stopped` or `suspended` when dev environments are stopped or reaped.

#### Cluster-Wide Idle Dev Pod Reaper
- **Direct Cluster Workload Discovery (`sandbox_reaper_service.py`, `kubernetes_driver.py`, `docker_driver.py`)**: Added `list_running_dev_app_ids()` across runtime drivers to detect all actively running dev deployments/containers in the cluster and reconcile them against activity timestamps and idle timeouts.
- **Orphaned Pod Sweeping (`sandbox_reaper_service.py`)**: Automatically detects and tears down orphaned or deleted app dev pods directly from Kubernetes/Docker.

#### Optimistic React Sandbox State Management
- **Instant Sandbox Selection (`AppBuildPage.tsx`)**: Added local selection state in React to immediately update active sandbox indicators, tabs, and file trees before backend queries resolve.
- **Auto-Selection of Newly Created Sandboxes (`AppBuildPage.tsx`)**: Automatically selects and activates new sandboxes upon branch creation.

---

## [0.12.10] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.10` brings **Leaf Sandbox Workspace Discovery**, **Isolated Fallback Placeholder Serving**, and **Expanded Backend/Frontend Framework Dispatching**.

### ✨ Features & Enhancements

#### Leaf Sandbox Directory Discovery & Root Resolution
- **Nested Monorepo Root Resolution (`docker_driver.py`, `kubernetes_driver.py`, `omnigent_dev_service.py`)**: Added recursive directory scan for project markers (`package.json`, `requirements.txt`, `app.py`, `main.py`, `vite.config.*`, `next.config.*`) up to 3 levels deep to locate and bind the active codebase within multi-layer monorepo structures.
- **Dedicated Fallback Isolation (`docker_driver.py`, `kubernetes_driver.py`)**: Provisioned sandbox initialization fallback HTML in `/tmp/cx_fallback/index.html` instead of the active workspace folder, preventing unintended workspace file pollution and git dirtying.

#### Multi-Framework Dispatching & Server Automation
- **Multi-Entry Backend Dispatcher (`docker_driver.py`, `kubernetes_driver.py`)**: Dispatches `app.py`, `main.py`, `server.py`, and `api.py` with automatic detection for FastAPI, Starlette, Flask, Bottle, and Streamlit.
- **Resilient Frontend Dev Scripting (`docker_driver.py`, `kubernetes_driver.py`)**: Prioritizes local `./node_modules/.bin/vite` and `./node_modules/.bin/next` executables before falling back to `npx`, and seamlessly hosts built static outputs (`dist/`, `build/`).

---

## [0.12.9] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.9` delivers **Dynamic Framework Detection in Dev Runner**, **Multi-Target Port Allocation**, **Deep Worktree Population Verification**, and **Branch Creation Cache Synchronization**.

### ✨ Features & Enhancements

#### Dynamic Dev-Runner Framework Detection & Port Allocation
- **Multi-Framework Runner Detection (`docker_driver.py`, `kubernetes_driver.py`)**: Added intelligent discovery and auto-launching for Next.js (`npx next dev -p 8080`), Vite dev server (`npx vite --port 8080`), Streamlit (`streamlit run app.py --server.port 8080`), custom npm scripts (`npm run dev`, `npm start`), and static web fallbacks (`npx serve`, `python -m http.server`).
- **Dynamic Port Assignment (`docker_driver.py`, `kubernetes_driver.py`)**: Dev-runner automatically assigns port 8000 for backend services when a frontend client is present, or port 8080 for standalone Python/Streamlit services.

#### Deep Worktree Population Verification
- **Non-Empty Tree Validation (`omnigent_dev_service.py`)**: Improved worktree verification to check for meaningful source code files beyond `.git` and placeholder `index.html` before flagging sandboxes as initialized.

#### Branch Creation React Cache Invalidation
- **Workspace Invalidation & Preview Reload (`AppBuildPage.tsx`)**: Invalidate React Query caches (`app-dev-files`, `app-dev-status`, `app-dev-workspaces`) and trigger live preview reload keys on branch and workspace creation.

---

## [0.12.8] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.8` introduces a **Unified Dev-Runner Process Supervisor**, **Instant Dev Sandbox Switching**, and **React Query Cache Synchronization for Live Preview**.

### ✨ Features & Enhancements

#### Unified Dev-Runner Process Supervisor
- **Robust In-Container Supervisor (`docker_driver.py`, `kubernetes_driver.py`)**: Introduced `/usr/local/bin/dev-runner.sh` script dynamically provisioned in dev containers and Kubernetes dev pods with `start`, `stop`, and `reload` lifecycle controls, clean PID tracking and signal dispatching, automated `requirements.txt` installation, and separate logging to `/tmp/backend.log` and `/tmp/frontend.log`.
- **Streamlined Dev Service Switching (`omnigent_dev_service.py`)**: Delegated sandbox switching directly to dev drivers, unifying runtime health checks across local and cloud environments.

#### Live Preview & Sandbox State React Invalidation
- **Live Preview Canvas Reload Key (`LivePreviewCanvas.tsx`)**: Added combined target URL and reload timestamp key to iframe rendering, ensuring instantaneous DOM rebuilds upon active workspace switches.
- **Cache Invalidation & Query Refetches (`AppBuildPage.tsx`)**: Automated invalidation and refetching of `app-dev-files`, `app-dev-status`, and `app-dev-workspaces` when switching active sandboxes.

---

## [0.12.7] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.7` delivers **Multi-Candidate Workspace Path Resolution**, **Verified Git Worktree Provisioning**, and **Resilient Shared Local Repo Cloning**.

### ✨ Features & Enhancements

#### Resilient Worktree & Sandbox Root Discovery
- **Multi-Candidate Workspace Path Resolution (`omnigent_dev_service.py`)**: Added candidate directory discovery fallbacks (`/workspaces/{app_id}/default`, `/workspaces/{app_id}/main`, `/workspaces/{app_id}`, `/workspaces/default`, `/app`) for live file tree rendering, file reading, and inline saving across dev containers and Kubernetes dev pods.
- **Verified Worktree Integrity (`omnigent_dev_service.py`)**: Enhanced worktree checks to verify both directory presence and non-empty file contents / valid `.git` references before initiating operations.
- **Shared Local Repo Cloning & Fallbacks (`docker_driver.py`, `kubernetes_driver.py`)**: Enhanced git worktree creation routines with fallback local cloning (`git clone --shared`) and direct git checkout for sandbox worktrees.

---

## [0.12.6] - 2026-10-07

### 🚀 Highlights

CompassX `0.12.6` delivers **Git Commit History Popover**, **Rich Omnigent Tool Streaming & Diffs**, **Contextual Folder Tree File Operations**, and **Enhanced Workspace Dev Drivers**.

### ✨ Features & Enhancements

#### Git Commit History & Sandbox Versioning
- **Interactive Git Commit History (`GitCommitHistoryPopover.tsx`, `AppBuildPage.tsx`, `useApps.ts`, `app_dev_routes.py`)**: Added dedicated popover component and API endpoint to inspect recent workspace git commits, commit authors, relative timestamps, and short hashes directly from the Build Studio header.

#### Omnigent Chat & Tool Streaming Enhancements
- **Rich Tool Call Execution & Structured Diffs (`OmnigentChatPanel.tsx`)**: Upgraded Omnigent Chat panel with grouped tool call badges, collapsible tool outputs, structured diff preview chips, thought blocks, and interactive user prompts.
- **Resilient Tool Input Fallbacks (`OmnigentChatPanel.tsx`)**: Robust parsing and formatting of heterogeneous tool argument schemas across all agent providers.

#### Workspace File Operations & Folder Tree Actions
- **Contextual File Management (`FolderTree.tsx`, `FilesPanel.tsx`, `FileExplorerSidepanel.tsx`, `omnigent_dev_service.py`)**: Added context actions for creating files/folders, inline renaming, deletion, real-time expansion tracking, and active file highlights.
- **Cross-Profile Dev Driver Extensions (`kubernetes_driver.py`, `omnigent_dev_service.py`, `test_cross_profile_dev_drivers.py`)**: Improved command execution and container file path binding across local Docker and Kubernetes dev pods.

---

## [0.12.5] - 2026-10-06

### 🚀 Highlights

CompassX `0.12.5` delivers **Modular Build Studio Canvases**, **Interactive Live Browser Preview & Toolbar**, **Dedicated Code Editor Canvas**, **Collapsible Output Drawer**, and **Refined File Explorer & Session Navigation**.

### ✨ Features & Enhancements

#### Modular Build Studio Architecture & Canvases
- **Modular Studio Layout (`AppBuildPage.tsx`)**: Completely redesigned App Build Studio with modular, resizable canvases for Live Preview, Code Editor, and Omnigent Chat.
- **Interactive Live Preview Canvas & Browser Toolbar (`LivePreviewCanvas.tsx`, `BrowserToolbar.tsx`)**: Embedded application preview canvas with responsive viewport modes (Desktop, Tablet, Mobile), URL navigation, refresh controls, and sandbox preview proxying.
- **Dedicated Code Editor Canvas (`CodeEditorCanvas.tsx`)**: High-performance multi-tab code editor with language syntax highlighting, unsaved change indicators, and quick save bindings.
- **Collapsible Bottom Output Drawer (`OutputDrawer.tsx`)**: Integrated bottom drawer housing dev terminal, build logs, and console outputs with collapsible height controls.

#### File Explorer & Session Navigation Refinements
- **Refined Files Panel & Folder Tree (`FileViewer.tsx`, `FilesPanel.tsx`, `FolderTree.tsx`)**: Clean modern file explorer with inline file creation, search filtering, smooth folder tree expanding/collapsing, and breadcrumb bar navigation.
- **Sleek Session History Popover (`SessionHistoryPopover.tsx`)**: Fast popup session switcher with search filtering, status indicators, and clean session lifecycle management.
- **Terminal View & Theme Polish (`TerminalView.tsx`, `DevTerminal.tsx`, `terminalThemePreferences.ts`)**: Streamlined terminal sizing, theme preference bindings, and seamless reconnects.

---

## [0.12.4] - 2026-10-06

### 🚀 Highlights

CompassX `0.12.4` delivers **Sandbox Remote Git Sync (`origin/main`)**, **Conflict-Aware Pre-Merge Auto-Stashing**, and **Flexible Base Branch Selection for Dev Sandboxes**.

### ✨ Features & Enhancements

#### Sandbox Remote Git Synchronization
- **Sync Active Sandbox with Remote Main (`SandboxSelector.tsx`, `useApps.ts`, `app_dev_routes.py`, `omnigent_dev_service.py`)**: Added dedicated sync endpoint and UI action to fetch and merge upstream remote changes (`origin/main` or configured base branch) into the active sandbox with behind-commit counting, conflict reporting, and automatic dependency re-evaluation.
- **Pre-Merge Auto-Stashing & Safe Merging (`omnigent_dev_service.py`)**: Automatically stashes uncommitted working tree changes before merging remote changes and restores them afterward to prevent work loss.

#### Dev Worktree & Branch Management
- **Base Branch Selection on Sandbox Creation (`NewSandboxModal.tsx`, `AppBuildPage.tsx`)**: Enabled selecting custom base branches (e.g. `main` or active branch) when launching new sandboxes, with automated remote repository pre-fetching.
- **Git Worktree Driver Extensions (`docker_driver.py`, `kubernetes_driver.py`)**: Enhanced worktree provisioning routines to support custom base branches during worktree branch initialization.

---

## [0.12.3] - 2026-10-06

### 🚀 Highlights

CompassX `0.12.3` delivers **Global Fast Shell Hotkey (`Ctrl+Shift+T`)**, **Precision Container Working Directory Resolution**, and **Polished Build Studio Session Navigation**.

### ✨ Features & Enhancements

#### Fast Shell Hotkeys & Terminal Shortcuts
- **Global Terminal Hotkey (`useNewShellHotkey.ts`, `AppBuildPage.tsx`)**: Added `Ctrl+Shift+T` / `Cmd+Shift+T` accelerator to spawn and focus new terminal shell sessions instantly inside the active workspace.
- **Terminal Focus & Keyboard Navigation (`TerminalSession.ts`)**: Streamlined keyboard event dispatching and auto-focus transitions.

#### Dev Driver & Container Shell Improvements
- **Container Working Directory Resolution (`docker_driver.py`, `kubernetes_driver.py`)**: Enhanced shell launch routines with precise directory binding and shell startup script seeding.
- **Studio Session Sidebar Polish (`SessionsSidebar.tsx`, `NewSessionModal.tsx`)**: Cleaner sessions layout, status indicators, and streamlined creation dialogs.

---

## [0.12.2] - 2026-10-05

### 🚀 Highlights

CompassX `0.12.2` delivers **Polished Build Studio UI & Session Modals**, **Streamlined Terminal Lifecycle Integration**, **Rich Multi-Agent Protocol Streaming**, and **File Explorer Sidepanel Refinements**.

### ✨ Features & Enhancements

#### Application Build Studio & Session Polish
- **Refined Sessions & Sandbox Management (`AppBuildPage.tsx`, `SessionsSidebar.tsx`, `SandboxSelector.tsx`, `NewSessionModal.tsx`, `NewSandboxModal.tsx`)**: Re-engineered modals with sleek backdrop blur, unified form layouts, interactive sandbox switching, and comprehensive error handling.
- **Terminal Lifecycle Streamlining (`DevTerminal.tsx`, `dev_terminal_service.py`)**: Simplified terminal mount/unmount logic, clean WebSocket lifecycle management, and seamless auto-reconnect on active sandbox transitions.

#### Omnigent Protocol & File Explorer Refinements
- **Rich Agent Message Streaming (`omnigent_dev_service.py`)**: Added support for granular tool call lifecycle events, multi-agent conversation contexts, and enhanced Docker container path resolution.
- **File Explorer Sidepanel Polish (`FileExplorerSidepanel.tsx`, `FileViewer.tsx`)**: Upgraded directory navigation with smooth transitions, breadcrumb updates, and quick path copy utilities.

---

## [0.12.1] - 2026-10-04

### 🚀 Highlights

CompassX `0.12.1` delivers **Resilient Kubernetes Dev Pod Discovery**, **Multi-Selector & Pod Prefix Binding**, and **Safe Python-Native Process Termination** for active workspace switching.

### ✨ Features & Enhancements

#### Kubernetes Driver Resilience
- **Multi-Selector & Prefix Pod Matching (`kubernetes_driver.py`)**: Added multiple fallback label selectors (`compassx/app-id`, `app.kubernetes.io/name`) and pod name prefix matching with creation timestamp ordering to reliably resolve running dev pod replicas during rollouts and restarts.
- **Python-Native Process Cleanup (`kubernetes_driver.py`)**: Implemented safe signal-based process termination for uvicorn, vite, and streamlit background servers when switching active workspace sandboxes without relying on host `pgrep`.
- **Gemini LLM Function Calling Test Fix (`test_llm_client.py`)**: Aligned Gemini test expectations with Google GenAI SDK `role="user"` conventions for function responses.

---

## [0.12.0] - 2026-10-04

### 🚀 Highlights

CompassX `0.12.0` is a **Major Milestone Release** delivering **Multi-Session Sandbox Architecture**, **Complete Dev Terminal & PTY Streaming Overhaul**, **Cross-Profile Dev Drivers with `app.yaml` Manifest Support**, **AI Gateway Streaming & Proxy Enhancements**, and **Interactive Build Studio File Explorer**.

### ✨ Features & Enhancements

#### Multi-Session Sandbox & Dev Sessions Architecture
- **Persistent Dev Sessions Lifecycle (`dev_session.py`, `dev_session_service.py`)**: Implemented persistent database models, active/archived state tracking, and multi-sandbox routing for application development sessions.
- **Session Switcher & Multi-Sandbox UI (`SessionSwitcher.tsx`, `SessionsSidebar.tsx`, `NewSessionModal.tsx`, `SandboxSelector.tsx`)**: Added interactive session management sidebar, quick session switcher, and sandbox creation modal in the App Build Studio.

#### Dev Terminal & PTY Streaming Overhaul
- **Interactive xterm.js Overhaul (`DevTerminal.tsx`, `TerminalSession.ts`, `dev_terminal_service.py`)**: Re-architected interactive terminal integration with direct PTY stream handling, reconnect resilience, automatic resize calculation, and touch scroll support.
- **Cross-Profile Dev Driver Support (`docker_driver.py`, `kubernetes_driver.py`, `base.py`)**: Added unified POSIX execution, container image resolution, and dynamic `app.yaml` manifest discovery across local, Docker, and Kubernetes profiles.

#### AI Gateway & Studio File Explorer
- **AI Gateway Streaming Proxy (`proxy_routes.py`, `gateway_service.py`, `openai_adapter.py`)**: Enhanced OpenAI proxy endpoints, tool calling synchronization with Omnigent agents, and completions streaming.
- **Build Studio File Explorer (`WorkspaceFileIcon.tsx`, `AppBuildPage.tsx`)**: Added in-studio directory tree navigation, code inspection, and file metadata visual cues.

---

## [0.11.11] - 2026-10-02

### 🚀 Highlights

CompassX `0.11.11` delivers a **Dedicated Full-Page Application Build Studio**, **Multi-Agent Coding Roster** (supporting Claude Code, Antigravity, Omnigent Polly, OpenCode, Codex UI, Gemini CLI, and DeepSeek Coder), and **Enhanced Studio Navigation & Quick Actions**.

### ✨ Features & Enhancements

#### Application Build Studio & Multi-Agent Roster
- **Dedicated Full-Page Build Studio (`AppBuildPage.tsx`, `App.tsx`)**: Introduced a full-page IDE and live preview workspace with draggable split panes, real-time iframe preview reload, and session management at `/apps/:applicationId/build`.
- **Expanded Agent Provider Catalog (`omnigent_dev_service.py`, `useOmnigentChat.ts`)**: Added a rich multi-agent roster supporting Claude Code, DeepMind Antigravity, Omnigent Polly, OpenCode, Codex UI, Gemini CLI, and DeepSeek Coder with provider branding, role tags, and interactive agent selection modal.
- **Studio Quick Actions & Navigation (`AppDetailPage.tsx`, `AppsHomePage.tsx`)**: Added quick "Open Build Studio" actions directly on the app card list, detail header, and tab bar.

---

## [0.11.10] - 2026-10-01

### 🚀 Highlights

CompassX `0.11.10` delivers **Morton Space-Filling Curve & Iceberg Z-Ordering Optimization**, **CompassX SQL DataFrame Clustering & Compact API**, and **Interactive AI Build Studio with Omnigent Chat**.

### ✨ Features & Enhancements

#### Iceberg Multi-Dimensional Z-Ordering & Compaction
- **Morton Curve Clustering (`zorder.py`, `iceberg_manager.py`)**: Implemented bit-interleaved Morton space-filling curves for multi-column clustering across DuckDB and Iceberg tables.
- **CompassX SQL Client Enhancements (`client.py`)**: Added `optimize_table` API and `z_order_by` argument to `write_table` and `pd.DataFrame.write_table`.

#### Application Build Studio
- **AI Build Studio Integration (`AppDetailPage.tsx`, `useOmnigentChat.ts`)**: Added dedicated AI Studio tab for interactive side-by-side app development and real-time Omnigent chat streaming.

---

## [0.11.9] - 2026-10-01

### 🚀 Highlights

CompassX `0.11.9` delivers **Workload Identity Header Resolution & M2M Service Principal Auth**, **Volume Directory Lifecycle & Keep Marker Management**, and **Polished Volume Explorer Modal UI**.

### ✨ Features & Enhancements

#### Workload Identity & M2M Authentication
- **Workload Identity Header Resolution (`middleware.py`, `dependencies.py`)**: Added automatic resolution for `x-workload-identity`, `compassx-workload-identity`, and case-insensitive headers to resolve App Service Principals directly into active workspace contexts.
- **Workspace ID & Header Fallbacks**: Supported `x-workspace-id` and `workspace-id` headers in addition to standard path slugs.

#### Volume Directory Lifecycle & Explorer Polish
- **Volume Manager Directory Operations (`volume_manager.py`)**: Added `.keep` marker file lifecycle management for empty storage directories, deduplication against raw object storage listings, and directory cleanups.
- **Enhanced Modal UI (`VolumeExplorer.tsx`)**: Upgraded modal dialogs for directory creation and item renaming with backdrop blur, keyboard shortcuts, and strict path validation.

---

## [0.11.8] - 2026-10-01

### 🚀 Highlights

CompassX `0.11.8` delivers **Modular Volume File Explorer Component**, **Refined Data Catalog Volume Management**, and **Interactive Directory Traversal & Filtering**.

### ✨ Features & Enhancements

#### Unified Volume File Explorer & Data Catalog UI
- **Modular Volume Explorer (`VolumeExplorer.tsx`)**: Extracted volume details, directory navigation, file table views, and upload handling into an encapsulated component.
- **Enhanced Search & Breadcrumb Traversal**: Improved directory level filtering, favorite toggling, and granular volume permissions management within the Unified Catalog view.

---

## [0.11.7] - 2026-09-30

### 🚀 Highlights

CompassX `0.11.7` delivers **Workload Identity Resolution & Environment Injections**, **App-Scoped Kubernetes Runtime Isolation**, and **Deterministic Sandbox Identity Binding**.

### ✨ Features & Enhancements

#### Kubernetes App & Sandbox Workload Identity Binding
- **Dynamic Workload Identity Resolution (`kubernetes_driver.py`)**: Automatic resolution and deterministic mapping of application identities (`COMPASSX_WORKLOAD_IDENTITY`) for both deployed container workloads and interactive developer sandboxes.
- **Enhanced Runtime Context Injections**: Injected `WORKSPACE_ID`, `COMPASSX_WORKLOAD_IDENTITY`, `APP_ID`, `APP_NAME`, and `APP_SLUG` into development container environments alongside host configuration files.

---

## [0.11.6] - 2026-09-25

### 🚀 Highlights

CompassX `0.11.6` delivers **Workspace-Wide MCP Configuration & Tool Propagation**, **Multi-Root OpenCode & Antigravity Native Config Injection**, and **Automated IDE Settings Synchronization**.

### ✨ Features & Enhancements

#### Model Context Protocol (MCP) Recursive Workspace Propagation & Settings
- **Recursive Workspace Syncing (`omnigent_sync.py`)**: Enhanced script generation to recursively scan and propagate `.mcp.json` and `mcp.json` across all workspace trees (`/workspaces/*`, `/workspaces/*/*`, and local workdirs).
- **IDE Settings Injection**: Automated creation and synchronization of `.gemini/settings.json` within every workspace directory alongside global configs (`/root/.config/opencode`, `/root/.opencode`).
- **Omnigent Native Path Discovery**: Automatic dynamic injection into `/root/.omnigent/antigravity-native/*/agy-home/.gemini/config/mcp_config.json` for seamless containerized agent workflows.

---

## [0.11.5] - 2026-09-25

### 🚀 Highlights

CompassX `0.11.5` delivers **Model Context Protocol (MCP) Server-Sent Events (SSE) Streaming Transport**, **Built-in Dashboard & Notebook MCP Connectors**, and **Omnigent IDE Real-Time Tool Synchronization & Driver Injections**.

### ✨ Features & Enhancements

#### Model Context Protocol (MCP) SSE Transport & Streaming
- **SSE Transport Server (`sse_server.py`)**: Built-in Server-Sent Events endpoint (`/api/v1/ai-gateway/mcp/sse/{server_name}`) allowing standard MCP clients to stream tools, execute prompts, and exchange bidirectional messages over HTTP SSE.
- **Built-in Dashboard Manager MCP (`dashboard_manager_mcp.py`)**: Native MCP server providing query execution, dashboard visualization, and metric aggregation tools to autonomous agents.
- **Built-in Notebook Manager MCP (`notebook_manager_mcp.py`)**: Native MCP server allowing agents to inspect notebooks, execute cell runs, propose edits, and analyze outputs.
- **Multi-Schema Catalog & SQL Expansion**: Added `list_schemas` and `get_table_schema` to `catalog_search_mcp.py` and enhanced query validation in `sql_warehouse_mcp.py`.

#### Omnigent Agent IDE Tool Sync & Container Runtime Injections
- **Real-Time MCP Tool Synchronization (`omnigent_sync.py`)**: Automated sync bridge between central MCP server registry and Omnigent Agent IDE sandboxes.
- **Driver Environment Injection**: Injected live MCP endpoints, authentication headers, and database connection pools into Docker and Kubernetes development containers (`docker_driver.py`, `kubernetes_driver.py`, `omnigent_dev_service.py`).

---

## [0.11.4] - 2026-09-24

### 🚀 Highlights

CompassX `0.11.4` delivers **Real-Time Agent Notebook Operations Streaming & Execution Engine**, **Live Multi-Agent Handoff & Plan Timeline Integration**, and **Granular Agent Cache Synchronization**.

### ✨ Features & Enhancements

#### Real-Time Agent Notebook Streaming & Execution
- **Dynamic Notebook Action Streaming (`AgentSidePanel.tsx`)**: Live handling and rendering of notebook operations (`edit_cell`, `propose_cell_edit`, `apply_notebook_edit`, `add_multiple_cells`, `run_cell`, `approve_cell_edit`, `reject_cell_edit`) directly into the active Notebook Studio session.
- **Batch Cell Insertion & Diffs**: Seamless batch creation of multiple code and markdown cells with cell explanation banners and inline diff previews.
- **Live Output Stream Rendering**: Real-time streaming capture of stdout, stderr, execution result objects, and execution counters dispatched from the agent runtime.

#### Multi-Agent Handoff & Plan Timeline Streaming
- **Handoff Tracking**: Live visual indicators when tasks are transferred between specialized agents with explicit reason metadata.
- **Interactive Plan Stepping**: Streaming timeline updates for `create_plan`, `mark_step`, and `approve_plan` tool execution.

#### Cache & Session State Synchronization
- **Optimistic Cache Invalidation**: Automatic real-time refresh of agent changes, context memory, and execution plans upon tool completion.

---

## [0.11.3] - 2026-09-24

### 🚀 Highlights

CompassX `0.11.3` delivers **AI Gateway with Multi-Provider LLM Orchestration & MCP Integration**, **Universal Context-Aware Agent Copilot & Side Panel**, **Enterprise Portal Customization Engine**, and **Decommissioning of Legacy Nova Sidebars**.

### ✨ Features & Enhancements

#### AI Gateway & Model Context Protocol (MCP) Integration
- **Centralized AI Gateway (`backend/app/ai_gateway/`)**: Unified LLM provider routing (OpenAI, Anthropic Claude, Google Gemini, Ollama) with automated retry, token accounting, inference logging, and fallback pipelines.
- **Model Context Protocol (MCP) Server & Client Tools**: Integrated MCP manager and built-in connectors (`catalog_search_mcp.py`, `sql_warehouse_mcp.py`) allowing autonomous agents to execute catalog inspections and live database analytics safely.

#### Universal Agent Copilot & Side Panel
- **Universal Copilot Side Panel (`AppShell.tsx`)**: Global, responsive AI Copilot drawer accessible from anywhere in the platform with persistent chat sessions, prompt suggestions, and customization settings.
- **Context-Aware Screen Intelligence (`useCurrentPageContext.ts`)**: Automatic extraction and injection of active page routes, query context, dataset details, and notebook metadata into agent prompts.
- **Agent Customizations & Skills Management (`AgentCustomizationsView.tsx`)**: Granular control over system instructions, custom prompt skills, model parameter tuning, and MCP tool permissions.

#### Enterprise Portal Customization & Landing Configuration
- **Portal Management API (`portal_routes.py`, `portal_config.py`)**: Centralized workspace portal branding, announcements, quick link curation, and customizable layout widgets.

#### Architectural Cleanup
- **Legacy Module Retirement**: Safely removed outdated Nova sidebar components (`AppNovaSidebar`, `NovaSidePanel`, `nova.css`, `useNovaAttachments`, `novaStore`) in favor of the unified Agent Copilot architecture.

---

## [0.11.2] - 2026-09-22

### 🚀 Highlights

CompassX `0.11.2` delivers **Real-Time Compute Resource Metrics & Telemetry**, **Interactive Notebook Metrics Panel in Notebook Studio**, **Prometheus & cAdvisor Telemetry Integration**, and **Enhanced AKS Node Pool Autoscaler Management**.

### ✨ Features & Enhancements

#### Real-Time Compute Resource Metrics & Telemetry
- **Telemetry Collection Service (`resource_service.py`)**: Real-time metric gathering for compute runtimes and Jupyter kernels via Prometheus and cAdvisor.
- **Dedicated Metrics API (`GET /api/v1/compute/resources/{resource_id}/metrics`)**: Returns CPU utilization %, Memory usage (MB/GB/%), Disk I/O, Network I/O, and historical sparkline series with automated fallback.
- **Configurable Metrics Backend**: Direct integration with cluster-internal Prometheus (`compassx-prometheus`) with fallback system telemetry.

#### Interactive Notebook Metrics Panel
- **Notebook Studio Metrics Drawer (`ComputeMetricsPanel.tsx`)**: Real-time telemetry monitoring drawer inside the Notebook Studio right sidebar.
- **Visual Utilization Gauges & Sparklines**: Instant visual feedback on active CPU load, memory breakdown, and resource pressure indicators during heavy computations.

#### AKS Node Pool Autoscaling & Compute Profile Refinements
- **Autoscaler Synchronization**: Refined node pool autoscaling configuration handling and status reporting in Account Settings.
- **Catalog Explorer Navigation**: Improved stability and tree node selection in Catalog Explorer.

---

## [0.11.1] - 2026-09-21

### 🚀 Highlights

CompassX `0.11.1` delivers **Dedicated AKS Compute Node Pool Provisioning & Deprovisioning Lifecycle Management**, **Graceful Workload Migration & Reschedule Switchover**, and **Interactive Compute Pool UI Controls in Account Settings**.

### ✨ Features & Enhancements

#### AKS Compute Node Pool Lifecycle Management
- **Explicit Provisioning & Deprovisioning Endpoints (`account_routes.py`)**: Added `POST /api/account/settings/compute/provision` and `POST /api/account/settings/compute/deprovision` to manage dedicated AKS compute node pools on-demand.
- **Graceful Workload Drain & Migration**: Deprovisioning automatically drains and moves running compute and notebook pods to the fallback shared user pool before initiating Azure node pool deletion.
- **Live Status & Autoscaler Tracking (`node_pool_manager.py`)**: Comprehensive state reporting including provisioned status, current/ready nodes, scale-to-zero detection, and autoscaler bounds.

#### Manual & Rolling Compute Workload Switchover
- **Workload Rescheduling (`switchover_compute_workloads`)**: Added `POST /api/account/settings/compute/switchover` to patch and roll compute runtime pods onto the target node pool seamlessly.

#### Account Settings UI Enhancements
- **Compute Pool Action Card (`AccountSettingsPage.tsx`)**: Real-time visual status badge for AKS compute node pool state (Not Provisioned / Provisioned / Provisioning).
- **Direct AKS Action Buttons**: One-click actions to Provision, Update Autoscaler, Deprovision, and Reschedule & Sync Compute Pods.

---

## [0.11.0] - 2026-09-21

### 🚀 Highlights

CompassX `0.11.0` delivers **Interactive Notebook Studio 2.0 with Integrated Web Terminal**, **Compute Resource Lifecycle Reconciliation & Auto-Recovery**, **Workspace-Level Service Principals & Member Management Overhaul**, and **Node Pool Hardware Tiering & Azure VM Catalog Expansion**.

### ✨ Features & Enhancements

#### Interactive Notebook Studio 2.0 & Web Terminal
- **Integrated Web Terminal**: Embedded `xterm.js` web terminal with dynamic pod selector and WebSocket streaming directly inside the notebook interface.
- **Sidebar Drawers & Navigation**: Quick-access collapsible drawers for compute resources, kernel runtime selection, files, and cluster status.
- **Kernel State Narrowing & Resiliency**: Hardened kernel attachment and execution lifecycle against unassigned resources and transient pod disconnections.

#### Compute Resource Lifecycle Reconciliation & Auto-Recovery
- **Automated Pod-to-DB Sync**: Background reconciliation service syncing live Kubernetes pod state with PostgreSQL resource records.
- **Auto-Recovery Loop**: Detects desynchronized or failed compute workloads and triggers automatic state correction and pod reinstatement.

#### Workspace-Level Service Principals & Member Management
- **Workspace SP Assignments (`0008_ws_service_principals.py`)**: Direct assignment of Service Principals to workspaces with granular access roles (Admin, Editor, Viewer).
- **Workspace Members Directory**: Redesigned workspace membership drawer supporting human users and machine identities in a unified view.

#### Node Pool Hardware Tiering & VM Catalog
- **Tier Matching**: Intelligent node pool selection routing interactive and heavy workloads to target hardware tiers (`userpoolv2`, `systempoolv2`).
- **VM Catalog Extension**: Expanded Azure VM series catalog with cost, CPU, memory, and acceleration specifications.

---

## [0.10.0] - 2026-09-20

### 🚀 Highlights

CompassX `0.10.0` delivers **Databricks-Inspired Enterprise Identity & Access Management (IAM)**, featuring **First-Class Service Principals with OAuth2 Client Credentials**, **Nested Group Hierarchies & Parent/Child Memberships**, **Unified Account Identity Hub**, and **Dynamic Role & Workspace Context Switching with Assumed Role Banner**.

### ✨ Features & Enhancements

#### First-Class Service Principals (Machine Identities)
- **Automated Workload Identities**: Added dedicated service principal entities for scripts, CI/CD runners, and background tasks.
- **OAuth2 Client Credentials**: Support for client ID generation, secure client secret generation, lifecycle management, and rotation.
- **Access Control**: Service principals can be assigned account and workspace roles and added to groups identically to human users.

#### Nested Groups & Parent-Child Hierarchies
- **Group Hierarchy Support**: Groups can now contain other groups as members, enabling hierarchical organizational permission modeling.
- **Recursive Membership Resolution**: Automated computation of direct and inherited group memberships across governance policies.
- **Group Details Drawer (`GroupDetailsPanel.tsx`)**: Interactive side drawer to inspect group composition, add parent groups, and manage child members.

#### Unified Account Identity Hub
- **Centralized Identity Directory (`IdentityHubTab.tsx`)**: Single-pane dashboard aggregating Users, Service Principals, and Nested Groups with real-time statistics, global search, and filtering.

#### Dynamic Role Switcher & Assumed Context Banner
- **Session Role Switcher (`RoleSwitcherDropdown.tsx`)**: Allows multi-role users to switch active persona (e.g. Account Admin, Workspace Admin, Member, Read-Only) dynamically.
- **Assumed Context Banner (`AssumedContextBanner.tsx`)**: Persistent top notification banner indicating active assumed role/workspace with instant one-click return.

#### Database Migrations & Governance Enforcement
- **Alembic Migration (`0003_sp_and_nested_groups.py`)**: Provisioned tables for `service_principals`, `service_principal_secrets`, and `group_parents`.
- **Governance Guard Updates (`dependencies.py`)**: Unified principal resolution supporting session role overrides, service principal tokens, and user JWTs.

---

## [0.9.5] - 2026-09-20

### 🚀 Highlights

CompassX `0.9.5` delivers a **React Hooks Ordering & State Derivation Fix** in App Detail Page for resilient rendering during loading and error transitions.

### ✨ Features & Enhancements

#### React Hooks Ordering & Loading State Resiliency
- **Safe Hook Call Order (`AppDetailPage.tsx`)**: Reordered loading and error early returns to execute after top-level derived states and hooks, eliminating React Hooks rule violations and ensuring seamless state transitions during app loading and teardown.

---

## [0.9.4] - 2026-09-20

### 🚀 Highlights

CompassX `0.9.4` delivers **Unified Inactivity Auto-Shutdown & Scale-to-Zero across Apps, Dev Sandboxes, and Compute Runtimes**, **Live App Startup Console with Real-Time Cluster Events and Elapsed Timers**, **Lifecycle & Activity Management REST API**, and **Shared Storage PVC Architecture**.

### ✨ Features & Enhancements

#### Unified Inactivity Auto-Shutdown & Lifecycle Management
- **Universal Scale-to-Zero**: Extended the background reaper service (`sandbox_reaper_service.py`) to monitor inactivity and automatically suspend compute across **Dev Sandboxes**, **Deployed User Apps**, and **Compute Runtimes (DuckDB / Jupyter)**.
- **REST Endpoints (`lifecycle_routes.py`)**: Added dedicated lifecycle querying, configuration, and activity touch endpoints (`/api/v1/apps/{app_id}/lifecycle`, `/api/v1/compute/resources/{resource_id}/lifecycle`).
- **Activity Touch Interceptors**: User interactions, terminal sessions, and API queries automatically refresh the idle timer to prevent active work disruption.

#### Live App Startup Progress Console & Timeline
- **Multi-Step Startup Timeline**: Interactive progress bar tracking pod provisioning phases (Init → Scheduling → Pulling Image → Container Startup → Live Health).
- **Cluster Event Streaming**: Real-time event log viewer displaying Kubernetes scheduling and container lifecycle events.
- **Elapsed Time Stopwatch**: Live duration counter tracking provisioning and startup latency.

#### Compute Runtime Inactivity Controls
- **Compute Inactivity Panel**: Added Inactivity Auto-Shutdown settings card on the Compute Resource detail page with configurable timeout thresholds (15 min – 8 hrs).

#### Shared Storage PVC & Helm Infrastructure
- **Shared Storage Architecture**: Added `shared-storage-pvc.yaml` supporting shared ReadWriteMany / ReadWriteOnce volumes across Airflow, Prometheus, and Omnigent workloads.

---

## [0.9.3] - 2026-09-18

### 🚀 Highlights

CompassX `0.9.3` delivers **Account Settings API Authentication & Authorization Fixes** and **Dual REST Route Mounting Compatibility** (`/api/account` & `/api/v1/account`).

### ✨ Features & Enhancements

#### Account Settings API Authentication & Client Fix
- **Authenticated Axios Client**: Switched `accountSettingsApi.ts` to use `authApi` with bearer token interceptor to ensure all account settings queries and mutations are properly authenticated.
- **Dual Route Mounting**: Mounted `workspace_account_routes` at both `/api/account` and `/api/v1/account` in FastAPI backend for seamless routing compatibility across all client configurations.

---

## [0.9.2] - 2026-09-18

### 🚀 Highlights

CompassX `0.9.2` delivers **Dedicated App Workload Node Pool Provisioning & Dynamic Switchover**, **Account Settings Console & Management API**, **On-Demand Airflow Webserver Lifecycle Management**, and **Cluster Resource Scheduling Isolation**.

### ✨ Features & Enhancements

#### Dedicated App Node Pool Management (`NodePoolManager`)
- **AKS Node Pool Provisioning**: Automated management of dedicated AKS node pools (`apppool`) with support for curated Azure VM size tiers (Burstable, Compute-Optimized, Memory-Optimized).
- **Dynamic Workload Switchover**: One-click rolling migration of all running app deployments and dev sandboxes between the shared pool (`userpoolv2`) and the dedicated app pool (`apppool`).
- **Cluster Discovery & Status**: Live inspection of cluster node pools, node readiness, active VM sizes, and app workload distribution.

#### Account Settings Console & API
- **New Account Settings UI**: Added Account Settings page accessible via the profile menu and Account Console tabs for Account Admins.
- **REST Endpoints**: Added `GET/PATCH /api/v1/account/settings`, `GET /api/v1/account/settings/nodepool/status`, and `POST /api/v1/account/settings/nodepool/switchover`.

#### On-Demand Airflow Webserver Lifecycle Management
- **Scale-to-Zero Webserver**: Ability to start and stop the Airflow Webserver on-demand from Account Settings to conserve cluster compute while keeping the scheduler and worker active.
- **Helm Configuration**: Updated chart defaults for on-demand webserver support.

#### Workload Placement & Node Isolation
- **Driver Node Targeting**: App runner and dev sandbox deployment builders route workloads to dedicated node pools dynamically based on active account configuration.

---

## [0.9.1] - 2026-09-16

### 🚀 Highlights

CompassX `0.9.1` delivers **Dev Sandbox Lifecycle Management UI**, **Suspend & Resume API Endpoints**, **Configurable Auto-Suspend & Stale Workspace Reaping**, and a **Persistent Deployment Status Fix**.

### ✨ Features & Enhancements

#### Dev Sandbox Lifecycle Management UI
- **Lifecycle Settings Panel**: New "Dev Sandbox Lifecycle & Auto-Suspend (Reaper)" section in App Settings with configurable Auto-Suspend idle timeout (15 min – 8 hrs) and Auto-Reap stale workspace threshold (7–90 days).
- **Active Work Protection**: UI clearly communicates that live Omnigent AI sessions, terminal connections, and recent file changes automatically prevent suspension.
- **Config Persistence**: Sandbox lifecycle settings are stored in `app.config.dev_sandbox` and synced on every App Settings save.

#### Suspend & Resume API Endpoints
- **`POST /api/v1/apps/{app_id}/dev/suspend`**: Immediately scales the dev sandbox to 0 replicas (scale-to-zero).
- **`POST /api/v1/apps/{app_id}/dev/resume`**: Restores the sandbox from scale-to-zero back to active (1 replica), enabling rapid 1-2s resume.

#### Sandbox Reaper Service Enhancements
- **Per-App Policy Override**: Reaper now respects per-app `dev_sandbox.auto_suspend_enabled`, `idle_timeout_minutes`, `auto_reap_enabled`, and `stale_reap_days` config overrides, falling back to global defaults.

#### Persistent Deployment Status Fix
- **`flag_modified` on Config**: Fixed SQLAlchemy not detecting JSON mutations in deployment status, ensuring `in_progress` deployments correctly resolve to `success` or `failed`.

---

## [0.9.0] - 2026-09-15

### 🚀 Highlights

CompassX `0.9.0` delivers **Omnigent-Inspired Managed Dev Sandboxes** with **Decoupled Persistent Volume Storage**, **Activity-Driven Scale-to-Zero Idle Suspension**, **Reactive 1-2s Resume**, and an automated **Background Sandbox Reaper Service**.

### ✨ Features & Enhancements

#### Managed Dev Sandbox Lifecycle & Storage Decoupling
- **State Preservation on Suspend**: Dev sandboxes mount the shared Kubernetes Persistent Volume (`compassx-dev-workspaces`) at `/workspaces`. When an app dev session is suspended or idle, compute scales to `replicas: 0` freeing CPU and memory while keeping all workspace files, git changes, and npm/pip modules intact.
- **Fast Reactive Resume**: Resuming suspended workspaces (`suspend_dev` → `resume_dev`) restores compute to `replicas: 1` in ~1-2 seconds with the persistent storage automatically re-attached.
- **Status Reporting**: `get_dev_status` now distinguishes `"suspended"` from `"running"` and `"stopped"`, enabling clear UI indicators for scale-to-zero sandboxes.

#### Activity-Driven Tracking & Background Sandbox Reaper
- **Workspace Activity Tracking**: Added `touch_workspace_activity` integrated into file operations, git synchronization, and live terminal PTY streams.
- **Automated Sandbox Reaper**: Background reaper service runs continuous sweeps:
  - Scales active sandboxes idle for > 30 minutes to zero compute replicas to optimize cluster resources.
  - Sweeps inactive workspaces older than 30 days for disk reclamation while keeping audit trails and metadata intact.

---

## [0.8.6] - 2026-09-15

### 🚀 Highlights

CompassX `0.8.6` delivers **Real-Time Deployment Log Streaming**, **Configurable App Resource Limits & Replicas**, **Auto-Save Env Vars on Deploy**, and **Smarter Deployment Status Polling**.

### ✨ Features & Enhancements

#### Real-Time Deployment Log Streaming
- **Progressive Log Updates**: The `capture_build_logs` pipeline now streams live log lines from Kubernetes pods back to the database in real-time via `on_progress` callbacks, so the UI shows continuous build progress instead of waiting for the final result.
- **Pod Phase Notifications**: Phase transitions (Pending → Running → Succeeded) are injected as timestamped log events enabling visibility into scheduling delays.
- **Error Detection**: Build failures (npm errors, fatal Git errors, build pipeline errors) are now detected across multiple patterns and immediately mark the deployment as `failed`.

#### Configurable App Resource Limits & Replicas
- **Per-App Resources**: Deployment specs now honor `resources.cpu`, `resources.memory`, and `resources.replicas` from the app config, replacing hard-coded limits, enabling proper resource control per app.

#### Auto-Save Env Vars on Deploy
- **Atomic Config Flush**: When deploying a dirty config (unsaved env vars, CPU/memory/replicas changes), the UI now automatically persists those settings via PATCH before triggering a build.
- **SQLAlchemy flag_modified**: Added `flag_modified(app, "config")` to `app_routes.py` to ensure JSON config mutations are reliably committed.

#### Smarter Deployment Status Polling
- **Faster Polling on Active Builds**: Frontend refetch interval reduced to 1000ms for `in_progress`, `building`, `starting`, and `queued` statuses.
- **Auto-Scroll with Log Filter**: Deployment terminal auto-scroll now triggered on both deployment data and filtered log changes.
- **Env Var Object Format Support**: `env_vars` in `object` format from the backend are automatically parsed and normalized into the UI list format.

---

## [0.8.5] - 2026-09-15

### 🚀 Highlights

CompassX `0.8.5` delivers **Live Git Branch Detection & Synchronization**, **Dev Sandbox Auto-Recovery for Git Push Operations**, **Optimized Hot-Reload & File Watcher Performance**, and **Refined Omnigent Dev Studio Routing**.

### ✨ Features & Enhancements

#### Live Git Branch Synchronization & Dynamic Resolution
- **In-Pod Branch Inspection**: Implemented `get_live_branch` across `KubernetesDevDriver` and `DockerDevDriver` to query active branches inside workspace containers via Git exec.
- **Dynamic Branch Sync**: Workspaces reflect user branch changes made in the terminal during development and commit to the active branch automatically.

#### Dev Sandbox Auto-Recovery for Push
- **Auto-Start on Push**: Committing or pushing changes to a stopped or idle dev sandbox automatically spins up the sandbox pod and executes the Git pipeline smoothly.

#### File Watcher & Resource Optimization
- **Throttled Polling & Exclusions**: Configured debounced file watching (`interval: 2000ms`) with explicit exclusions for `node_modules`, `.git`, `dist`, and `.cache` across Vite, Uvicorn, Chokidar, and Watchpack in dev containers, significantly reducing CPU and memory overhead.

#### Omnigent Dev Studio Ingress Fix
- **Direct Dev Studio Navigation**: Sanitized Omnigent public URL resolution to eliminate invalid session sub-paths when opening Dev Studio.

---

## [0.8.4] - 2026-09-15

### 🚀 Highlights

CompassX `0.8.4` delivers **Dev Sandbox Pod Affinity & Colocation**, **Enhanced In-Container Git Push with Multi-Platform Auth**, and dedicated **App Repository Credential Management UI**.

### ✨ Features & Enhancements

#### Dev Sandbox Pod Affinity & Low-Latency Colocation
- **Pod Affinity Scheduling**: Added Kubernetes pod affinity in `kubernetes_driver.py` ensuring dev sandbox pods are colocated with the Omnigent server instance for minimal network latency during interactive terminal sessions and file synchronization.

#### In-Container Git Push & Multi-Platform Authentication
- **Resilient Push Pipeline**: Enhanced `KubernetesDevDriver.exec_git_in_workspace` with headless prompt suppression (`GIT_TERMINAL_PROMPT=0`), deterministic success markers, and detailed stderr diagnostic reporting.
- **Multi-Provider Auth Injection**: Dynamic credential resolution supporting GitHub (`x-access-token`), GitLab, and Azure DevOps (`oauth2`) PAT injection in `omnigent_dev_service.py`.
- **Automatic Dev Branch Association**: Automatically associates custom dev workspaces with isolated `dev/<workspace-name>` branches.

#### App Settings & Repository Credentials UI
- **Git Credential Management**: Added interactive credential selection (None/Public, Personal Access Token, Linked Platform Account) with nickname management and show/hide token toggles in `AppDetailPage.tsx` and `AppDevelopmentTab.tsx`.

---

## [0.8.3] - 2026-09-14

### 🚀 Highlights

CompassX `0.8.3` introduces the **Interactive Dev Sandbox Terminal** with live WebSocket PTY streaming and command execution, **Decoupled Per-Workspace Git Push** targeting dedicated development branches, and expanded container driver runtime capabilities.

### ✨ Features & Enhancements

#### Interactive Dev Sandbox Terminal
- **Full-Featured Dev Terminal**: Embedded terminal emulator (`DevTerminal.tsx`) with ANSI styling, execution history buffer, auto-scroll, and interactive shell execution directly in the App Development tab.
- **WebSocket Terminal Streaming**: Real-time terminal bridge (`DevTerminalService` & `/api/v1/apps/{app_id}/dev/terminal/ws`) streaming standard input/output directly to active Kubernetes pods and Docker containers.
- **Remote Command Execution**: Added `/api/v1/apps/{app_id}/dev/terminal/exec` for dispatching shell commands within sandboxed workspaces.

#### Per-Workspace Git Publishing & Branching
- **Dedicated Dev Branches**: Workspaces automatically commit and push to dedicated development branches (`dev/<workspace-name>`) without polluting the main branch.
- **Decoupled Workflow**: Committing changes preserves the active sandbox session without triggering premature production deployments.
- **Authenticated Driver Git Push**: Secure Git credential injection and in-container remote push execution in both Kubernetes and Docker drivers.

#### Driver & Runtime Enhancements
- **Driver PTY & Exec Protocol**: Added `open_terminal_ws_client` and `exec_git_in_workspace` across `KubernetesDriver` and `DockerDriver`.
- **WebSocket Ingress Routing**: Ensured proper upgrade headers and timeouts for dev sandbox terminal connections.

---

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
