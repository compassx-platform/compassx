# Docker Compose Deployment

CompassX deployment manifests and configurations are located in `deployments/docker-compose/`.

You can manage Docker Compose directly with Docker or through the unified `compassx` platform CLI.

---

## Running with the `compassx` CLI (Recommended)

```bash
# Start infrastructure in local-dev mode (native backend + frontend, Docker infra)
./compassx up                     # Windows: .\compassx.cmd up

# Start entire full stack in Docker containers
./compassx up --profile docker    # Windows: .\compassx.cmd up --profile docker

# Check platform status and diagnostics
./compassx status
./compassx health

# Stop stack
./compassx down
```

---

## Running with Docker Compose Directly

From the repository root:

```bash
# Start the full containerized stack
docker compose -f deployments/docker-compose/docker-compose.yml up -d

# Or navigate to the folder
cd deployments/docker-compose
docker compose up -d
```

---

## Available Profiles

| Profile | CLI Command | Included Services |
| :--- | :--- | :--- |
| **`local-dev`** | `./compassx up --profile local-dev` | Host-native Frontend & Backend + Docker PostgreSQL, Redis, MinIO, Airflow, Enterprise Gateway, Prometheus. |
| **`docker`** | `./compassx up --profile docker` | All infrastructure + Backend and Frontend containers. |

---

## Service Ports Reference

| Service | Internal Port | Host Port | Protocol | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend UI** | `80` | `5173` | HTTP | Web UI |
| **Backend API** | `8000` | `8000` | HTTP | FastAPI REST API & WebSockets |
| **PostgreSQL** | `5432` | `5433` | TCP | Relational DB + pgvector |
| **Redis** | `6379` | `6379` | TCP | In-memory cache & broker |
| **MinIO API** | `9000` | `9000` | HTTP | S3 Storage API |
| **MinIO Console** | `9001` | `9001` | HTTP | Storage web interface |
| **Airflow Web** | `8080` | `8080` | HTTP | Airflow UI |
| **Enterprise Gateway** | `8888` | `8888` | HTTP | Jupyter kernel manager |
| **Prometheus** | `9090` | `9090` | HTTP | Metrics aggregator |

---

## Common Operations

### Checking Container Health & Logs

```bash
# View running containers
docker compose -f deployments/docker-compose/docker-compose.yml ps

# Tail logs for a specific service (e.g. postgres)
docker compose -f deployments/docker-compose/docker-compose.yml logs -f postgres
```

### Stopping Services & Cleaning Volumes

```bash
# Stop running containers
docker compose -f deployments/docker-compose/docker-compose.yml down

# Stop and wipe persistent volume data (clean state reset)
docker compose -f deployments/docker-compose/docker-compose.yml down -v
```
