# CompassX Platform

CompassX is an enterprise AI-native data & analytics platform.

This guide provides step-by-step instructions to set up and run the platform locally using the **`local-dev`** profile.

---

## Architecture Overview (`local-dev` profile)

In **`local-dev`** mode:
- **Backend (FastAPI)**: Runs natively on your host machine with hot-reload enabled.
- **Frontend (React + Vite)**: Runs natively on your host machine (`http://localhost:5173`).
- **Infrastructure Services (Docker)**: PostgreSQL (pgvector), Redis, MinIO (S3-compatible object storage), Apache Airflow, Jupyter Enterprise Gateway, and Prometheus run in Docker Compose.

```
+------------------------------------------------------------------+
|                          HOST MACHINE                            |
|                                                                  |
|   Frontend (Vite: 5173)  <--->  Backend (FastAPI: 8000)          |
|                                         |                        |
+-----------------------------------------|------------------------+
                                          |
               +--------------------------v--------------------------+
               |                 DOCKER COMPOSE                      |
               |                                                     |
               |   - PostgreSQL (5433)   - Redis (6379)              |
               |   - MinIO (9000/9001)   - Airflow (8080)            |
               |   - Enterprise Gateway (8888)                       |
               |   - Prometheus (9090)                               |
               +-----------------------------------------------------+
```

---

## Prerequisites

Before starting, ensure you have the following installed and running:

1. **Docker Desktop** (or Docker Engine on Linux)
   - Ensure Docker is running.
   - *macOS note:* Ensure "Allow the default Docker socket to be used" is enabled in Docker Desktop Settings > Advanced.
2. **Python 3.11+**
3. **Node.js 18+ & npm**
4. **Git**

---

## Quick Start Guide

### 1. Clone the Repository & Configure Environment

```bash
git clone <repo-url> compassx
cd compassx
```

Copy the example environment file:

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

---

### 2. Setup on macOS / Linux

#### A. Setup Backend Virtual Environment
```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/python -m pip install -r requirements.txt
cd ..
```

*(Optional: If you prefer keeping the virtualenv outside the repository)*:
```bash
python3 -m venv ~/venvs/compassx-backend
export BACKEND_VENV_PATH=~/venvs/compassx-backend
"$BACKEND_VENV_PATH/bin/python" -m pip install --upgrade pip setuptools wheel
"$BACKEND_VENV_PATH/bin/python" -m pip install -r requirements.txt
```

#### B. Setup Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

#### C. Start the Platform
From the repository root:
```bash
./compassx up
```

> **macOS Note:** On first launch, macOS may prompt for permission: *"[Terminal/IDE] wants access to control Terminal.app"*. Click **Allow** to let CompassX spawn separate service windows.

---

### 3. Setup on Windows

#### A. Setup Backend Virtual Environment (PowerShell)
> **Tip:** Windows paths can exceed standard character limits with certain packages. Setting up the virtualenv in a short path like `C:\venvs\compassx-backend` is recommended.

**Recommended (External venv):**
```powershell
cd backend
py -3.11 -m venv C:\venvs\compassx-backend
$env:BACKEND_VENV_PATH = "C:\venvs\compassx-backend"
[System.Environment]::SetEnvironmentVariable('BACKEND_VENV_PATH', 'C:\venvs\compassx-backend', 'User')
& "$env:BACKEND_VENV_PATH\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& "$env:BACKEND_VENV_PATH\Scripts\python.exe" -m pip install -r requirements.txt
cd ..
```

**Alternative (Repo-local venv):**
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..
```

#### B. Setup Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

#### C. Start the Platform
From the repository root:
```powershell
.\compassx.cmd up
```

---

## Service Endpoints & Credentials

Once startup completes (`Platform ready`), services are available at:

| Service | URL | Credentials / Notes |
| :--- | :--- | :--- |
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | Main user interface |
| **Backend API Docs** | [http://localhost:8000/api/swagger/docs](http://localhost:8000/api/swagger/docs) | Interactive Swagger UI |
| **Backend Health** | [http://localhost:8000/healthcheck](http://localhost:8000/healthcheck) | API healthcheck endpoint |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | User: `minioadmin` \| Pass: `minioadmin` |
| **Airflow UI** | [http://localhost:8080](http://localhost:8080) | User: `admin` \| Pass: `admin` |
| **Enterprise Gateway** | [http://localhost:8888](http://localhost:8888) | Jupyter kernel gateway |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | Metrics & cluster monitoring |
| **PostgreSQL** | `localhost:5433` | User: `postgres` \| Pass: `postgres` |

---

## Platform Management CLI (`compassx`)

Manage platform services without manual Docker or process commands:

```bash
# Start all platform services (default profile: local-dev)
./compassx up                     # Windows: .\compassx.cmd up

# Check live status of all services
./compassx status                 # Windows: .\compassx.cmd status

# Run root-cause diagnostic health checks
./compassx health                 # Windows: .\compassx.cmd health

# View logs for a specific service
./compassx logs backend           # Windows: .\compassx.cmd logs backend
./compassx logs frontend          # Windows: .\compassx.cmd logs frontend
./compassx logs postgres          # Windows: .\compassx.cmd logs postgres

# Restart services
./compassx restart                # Windows: .\compassx.cmd restart
./compassx restart backend        # Restart only the backend

# Stop all services cleanly
./compassx down                   # Windows: .\compassx.cmd down
```

---

## Deployment Options & Releases

All platform deployment configurations are located in the [`deployments/`](./deployments/) folder:

1. **Local Development (`local-dev`)**: Run frontend & backend natively with containerized dependencies via `./compassx up`.
2. **Full Docker Compose Stack**: Standalone container deployment located in [`deployments/docker-compose/`](./deployments/docker-compose/).
   ```bash
   docker compose -f deployments/docker-compose/docker-compose.yml up -d
   ```
3. **Kubernetes Cloud Release (Helm Chart)**: Production-grade Helm chart for AWS EKS, Azure AKS, Google GKE located in [`deployments/helm/compassx/`](./deployments/helm/compassx/).
   ```bash
   helm install compassx ./deployments/helm/compassx --namespace compassx
   ```

---

## Troubleshooting

### 1. Docker Daemon is Not Running
- **Error:** `Docker daemon is not running. Start Docker Desktop...`
- **Solution:** Open Docker Desktop and wait until the engine starts before running `./compassx up`.

### 2. macOS: Terminal Automation Permission Denied
- **Error:** `Failed to open Terminal.app for 'backend'...`
- **Solution:** Open **System Settings > Privacy & Security > Automation**, find your terminal/IDE (e.g. VS Code, Terminal, iTerm), and toggle **Terminal** on.

### 3. Port Already in Use
- **Error:** `A required port is already in use by another process.`
- **Solution:** Ensure other database servers or conflicting processes aren't holding ports `5433`, `8000`, `5173`, `6379`, `9000`, `9001`, or `8080`. Run `./compassx down` to terminate previous sessions.

### 4. Backend Python Not Found
- **Error:** `Could not find a backend Python interpreter.`
- **Solution:** Ensure you created a virtualenv at `backend/.venv` or set the `BACKEND_VENV_PATH` environment variable to your virtualenv path.

