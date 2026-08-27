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

## ☁️ Multi-Cloud Deployment Presets

Ready-to-use value presets and dedicated step-by-step guides are located in [`deployments/`](https://github.com/compassx-platform/compassx/tree/main/deployments):

### 1. Amazon Web Services (AWS EKS)
* **Guide**: [`deployments/aws/README.md`](https://github.com/compassx-platform/compassx/tree/main/deployments/aws)
* **In-Cluster (`gp3`)**: `helm install compassx ./deployments/helm/compassx -f ./deployments/aws/values-incluster.yaml -n compassx`
* **Managed (RDS + S3 + ElastiCache)**: `helm install compassx ./deployments/helm/compassx -f ./deployments/aws/values-managed.yaml -n compassx`

### 2. Microsoft Azure (Azure AKS)
* **Guide**: [`deployments/azure/README.md`](https://github.com/compassx-platform/compassx/tree/main/deployments/azure)
* **In-Cluster (`managed-csi`)**: `helm install compassx ./deployments/helm/compassx -f ./deployments/azure/values-incluster.yaml -n compassx`
* **Managed (Flexible Server + Blob + Redis)**: `helm install compassx ./deployments/helm/compassx -f ./deployments/azure/values-managed.yaml -n compassx`

### 3. Google Cloud Platform (Google GKE)
* **Guide**: [`deployments/gcp/README.md`](https://github.com/compassx-platform/compassx/tree/main/deployments/gcp)
* **In-Cluster (`standard-rwo`)**: `helm install compassx ./deployments/helm/compassx -f ./deployments/gcp/values-incluster.yaml -n compassx`
* **Managed (Cloud SQL + GCS + Memorystore)**: `helm install compassx ./deployments/helm/compassx -f ./deployments/gcp/values-managed.yaml -n compassx`

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
