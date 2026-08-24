# Docker Compose Deployment

CompassX uses Docker Compose profiles to support different runtime environments: local development, testing, and full-stack local deployment.

---

## Available Profiles

| Profile | Command | Included Services |
| :--- | :--- | :--- |
| **`local-dev`** | `docker compose --profile local-dev up -d` | PostgreSQL, Redis, MinIO, Airflow, Enterprise Gateway, Prometheus. |
| **`full`** | `docker compose --profile full up -d` | All infrastructure services + Backend and Frontend containers. |

---

## Service Ports Reference

| Service | Internal Port | Host Port | Protocol | Description |
| :--- | :--- | :--- | :--- | :--- |
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
docker compose ps

# Tail logs for a specific service (e.g. postgres)
docker compose logs -f postgres
```

### Stopping Services & Cleaning Volumes

```bash
# Stop running containers
docker compose down

# Stop and wipe persistent volume data (clean state reset)
docker compose down -v
```
