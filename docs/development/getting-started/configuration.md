# Configuration & Environment Variables

CompassX uses environment variables for service configuration, database connections, security keys, and integration endpoints.

---

## Environment File Setup

The root `.env` file controls Docker Compose and backend execution. Copy the template:

```bash
cp .env.example .env
```

---

## Key Configuration Variables

### Database & Storage Settings

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `POSTGRES_USER` | `compassx` | PostgreSQL database user |
| `POSTGRES_PASSWORD` | `compassx_dev_password` | PostgreSQL database password |
| `POSTGRES_DB` | `compassx` | Primary database name (includes pgvector) |
| `POSTGRES_PORT` | `5433` | Host port mapped to PostgreSQL |
| `REDIS_PORT` | `6379` | Host port mapped to Redis |
| `MINIO_ROOT_USER` | `minioadmin` | MinIO root access key |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | MinIO root secret key |
| `MINIO_API_PORT` | `9000` | MinIO S3 API endpoint port |
| `MINIO_CONSOLE_PORT` | `9001` | MinIO Web Console UI port |

---

### Backend & Authentication Settings

| Variable | Description |
| :--- | :--- |
| `SECRET_KEY` | Secret key used for signing JWT access and refresh tokens. |
| `ALGORITHM` | Algorithm used for token encryption (default: `HS256`). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of authentication access tokens (default: `60`). |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins (default: `http://localhost:5173`). |

---

### Service Integrations

| Variable | Default Port | Description |
| :--- | :--- | :--- |
| `AIRFLOW_WEBSERVER_PORT` | `8080` | Apache Airflow Web UI |
| `ENTERPRISE_GATEWAY_PORT` | `8888` | Jupyter Enterprise Gateway daemon |
| `PROMETHEUS_PORT` | `9090` | Prometheus metrics scraping endpoint |

> [!WARNING]
> Never commit production `.env` files with real credentials or secret keys to version control. Keep secrets in a secure secret manager in production deployments.
