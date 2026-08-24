# Kubernetes Cloud Deployment (Helm Chart)

CompassX provides a production-grade Helm chart for deploying the full platform stack on Kubernetes (AWS EKS, Azure AKS, Google Cloud GKE, or custom Kubernetes clusters).

The chart files are located in [`deployments/helm/compassx/`](https://github.com/compassx-platform/compassx/tree/main/deployments/helm/compassx).

---

## 🏗️ Architecture on Kubernetes

In a Kubernetes Cloud deployment:
- **Backend (FastAPI)**: Runs as a Deployment with automated horizontal autoscaling (HPA) and health probes.
- **Frontend (React/Vite/Nginx)**: Runs as a Deployment serving the single-page application and proxying WebSocket / REST calls.
- **Enterprise Gateway**: Manages remote Jupyter kernels dynamically inside Kubernetes pods across multiple runtimes (DuckDB, Spark, Ray, Flink).
- **Airflow**: Runs with automated DB migration & user initialization Job, Webserver, and Scheduler with persistent volume logging and DAG synchronization.
- **Datastores & Caches**: Supports both in-cluster instances (PostgreSQL with `pgvector`, Redis, MinIO) and Bring-Your-Own cloud managed services (AWS RDS / Aurora, ElastiCache, S3, Azure Database for PostgreSQL, Azure Blob Storage).
- **Ingress**: Cloud-native Ingress routing with TLS termination and WebSocket upgrades.

---

## 📋 Prerequisites

1. **Kubernetes Cluster (v1.24+)**
2. **Helm (v3.8+)**
3. **Ingress Controller** (e.g. `ingress-nginx`, AWS Load Balancer Controller, or Azure Application Gateway Ingress)
4. **CSI Storage Provisioner** (e.g. AWS `gp3`, Azure `managed-csi`, GCP `standard-rwo`)

---

## 🚀 Quickstart: In-Cluster Stack

Deploy all services directly in a dedicated namespace:

```bash
# 1. Create namespace
kubectl create namespace compassx

# 2. Install CompassX Helm release
helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  --set ingress.hosts[0].host=compassx.yourcompany.com

# 3. Check status
kubectl get pods -n compassx
```

---

## ☁️ Enterprise Cloud Deployment (Managed Datastores)

For production workloads, use cloud-native managed databases and object stores.

### 1. Store Credentials in Kubernetes Secrets

```bash
# PostgreSQL Credentials
kubectl create secret generic compassx-rds-credentials \
  --namespace compassx \
  --from-literal=password='YOUR_DATABASE_PASSWORD'

# S3 Storage Credentials
kubectl create secret generic compassx-s3-credentials \
  --namespace compassx \
  --from-literal=secret-key='YOUR_AWS_SECRET_KEY'
```

### 2. Deploy using `values-cloud.yaml`

```bash
helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/helm/compassx/values-cloud.yaml \
  --set externalPostgresql.host="your-rds-endpoint.rds.amazonaws.com" \
  --set externalPostgresql.password="YOUR_DATABASE_PASSWORD" \
  --set externalRedis.host="your-redis-endpoint.cache.amazonaws.com" \
  --set externalStorage.bucket="your-s3-bucket-name" \
  --set externalStorage.accessKey="YOUR_AWS_ACCESS_KEY_ID" \
  --set externalStorage.secretKey="YOUR_AWS_SECRET_KEY" \
  --set ingress.hosts[0].host="app.compassx.yourcompany.com"
```

---

## ⚙️ Key Configuration Parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `backend.replicaCount` | Number of backend replicas | `1` |
| `backend.image.tag` | Container image tag | `v0.2.0` |
| `backend.autoscaling.enabled` | Enable Horizontal Pod Autoscaler | `false` |
| `frontend.replicaCount` | Number of frontend replicas | `1` |
| `enterpriseGateway.replicaCount` | Number of EG replicas | `1` |
| `airflow.enabled` | Enable Airflow orchestration | `true` |
| `postgresql.enabled` | Deploy in-cluster PostgreSQL | `true` |
| `externalPostgresql.host` | External DB host | `""` |
| `redis.enabled` | Deploy in-cluster Redis | `true` |
| `externalRedis.host` | External Redis host | `""` |
| `minio.enabled` | Deploy in-cluster MinIO | `true` |
| `externalStorage.backend` | Storage type (`s3`, `azure`, `minio`) | `"s3"` |
| `ingress.enabled` | Enable Ingress resource | `true` |
| `ingress.className` | Ingress controller class name | `"nginx"` |

For complete documentation on all variables, see [`deployments/helm/compassx/values.yaml`](https://github.com/compassx-platform/compassx/tree/main/deployments/helm/compassx/values.yaml).
