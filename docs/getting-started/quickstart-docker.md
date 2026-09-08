# Quickstart with Docker

The fastest way to evaluate and test CompassX is using the pre-packaged Docker Compose stack. This launches the complete platform &mdash; frontend, backend, PostgreSQL with `pgvector`, MinIO object storage, Airflow orchestration, and the Enterprise Gateway &mdash; in isolated containers with zero manual configuration.

---

## 1. Clone the Repository

Clone the CompassX repository to your local workstation:

```bash
git clone https://github.com/compassx-platform/compassx.git
cd compassx
```

---

## 2. Launch the Platform

From the repository root directory, start the container stack:

```bash
docker compose -f deployments/docker-compose/docker-compose.yml up -d
```

> [!TIP]
> Alternatively, if you prefer using the unified platform CLI helper:
> ```bash
> ./compassx up --profile docker      # Linux / macOS
> .\compassx.cmd up --profile docker  # Windows
> ```

---

## 3. Verify Container Startup

First-time startup typically takes 1 to 3 minutes while container images are downloaded and the database migrations execute.

Check that all services report healthy status:

```bash
docker compose -f deployments/docker-compose/docker-compose.yml ps
```

You should see all primary services running:

| Container Service | Role | Port Mapping | Health Target |
| :--- | :--- | :--- | :--- |
| `compassx-frontend` | React + TypeScript Web UI | `5173:80` | `http://localhost:5173` |
| `compassx-backend` | FastAPI REST & WebSockets | `8000:8000` | `http://localhost:8000/healthcheck` |
| `compassx-postgres` | PostgreSQL with `pgvector` | `5433:5432` | `pg_isready` on port 5433 |
| `compassx-minio` | S3-Compatible Object Store | `9000:9000`, `9001:9001` | MinIO Console on port 9001 |
| `compassx-airflow-webserver` | Airflow DAG Web UI | `8080:8080` | Airflow Webserver on port 8080 |
| `compassx-enterprise-gateway` | Jupyter Kernel Gateway | `8888:8888` | Gateway API on port 8888 |
| `compassx-redis` | In-Memory Cache & Broker | `6379:6379` | `redis-cli ping` |
| `compassx-prometheus` | Metrics & Monitoring | `9090:9090` | Prometheus UI on port 9090 |

---

## 4. Open the Web Workspace

Once the containers are running, navigate to the frontend interface in your browser:

👉 **[http://localhost:5173](http://localhost:5173)**

Log in using the default administrative credentials:

- **Username**: `admin`
- **Password**: `admin`

---

## 5. Stopping and Resetting

### Stop the Platform
To pause and stop all containers without losing stored data:

```bash
docker compose -f deployments/docker-compose/docker-compose.yml down
```

### Complete State Reset (Wipe Volumes)
To completely wipe all metadata, uploaded files, and database records for a fresh installation:

```bash
docker compose -f deployments/docker-compose/docker-compose.yml down -v
```

---

## 6. Troubleshooting Common Issues

### Issue 1: Port Conflict (Port Already in Use)
**Symptom**: `Error: Bind for 0.0.0.0:8000 failed: port is already allocated`.  
**Resolution**: Ensure no local services (e.g., local PostgreSQL on 5433, local FastAPI on 8000, or local Vite dev servers on 5173) are occupying the required ports. Stop conflicting processes or run `docker compose down` on previous instances.

### Issue 2: Docker Engine Not Running
**Symptom**: `Cannot connect to the Docker daemon`.  
**Resolution**: Ensure Docker Desktop or the Docker systemd daemon is started and running before executing the compose command.

### Issue 3: Memory Allocation Limit
**Symptom**: Containers abruptly exit with code `137` (Out of Memory).  
**Resolution**: Allocate at least 8 GB of RAM to Docker in Docker Desktop &rarr; Settings &rarr; Resources &rarr; Memory.

---

## Next Steps

Now that your platform is up and running, proceed to **[Workspace Navigation & UI](workspace-navigation.md)** to learn how the interface is structured.
