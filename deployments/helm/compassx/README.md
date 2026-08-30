# CompassX Platform — Kubernetes Helm Chart

Production-grade Helm chart for deploying the **CompassX Platform** on Kubernetes (AWS EKS, Azure AKS, Google GKE, or self-managed cloud clusters).

---

## 🏗️ Architecture Overview

The CompassX Helm chart deploys the following stack:

```
                                  [ Ingress Controller ]
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    │                                               │
               / (Frontend)                                   /api (Backend)
                    │                                               │
          ┌─────────▼─────────┐                           ┌─────────▼─────────┐
          │  CompassX Frontend │                           │  CompassX Backend  │
          │   (React + Vite)  │                           │     (FastAPI)     │
          └───────────────────┘                           └─────────┬─────────┘
                                                                    │
           ┌─────────────────┬──────────────────┬───────────────────┼──────────────────┐
           │                 │                  │                   │                  │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌───────▼────────┐   ┌──────▼──────┐   ┌───────▼────────┐
    │ PostgreSQL  │   │    Redis    │   │  MinIO / S3    │   │   Airflow   │   │   Enterprise   │
    │  (pgvector) │   │   (Cache)   │   │(Object Storage)│   │(Orchestrator│   │    Gateway     │
    └─────────────┘   └─────────────┘   └────────────────┘   └─────────────┘   └───────┬────────┘
                                                                                       │
                                                                           ┌───────────▼───────────┐
                                                                           │ Dynamic Kernel Pods   │
                                                                           │ (DuckDB/Spark/Ray...) │
                                                                           └───────────────────────┘
```

---

## 📋 Prerequisites

- **Kubernetes 1.24+**
- **Helm 3.8+**
- **Ingress Controller** (e.g. `ingress-nginx`, AWS Load Balancer Controller, or Azure Application Gateway Ingress)
- Dynamic Volume Provisioner (e.g. AWS `gp3`, Azure `managed-csi`, or GCP `standard-rwo`)

---

## 🚀 Quick Start (All-in-One Cloud In-Cluster Stack)

To deploy a self-contained CompassX stack where databases and object storage run inside the cluster:

### 1. Add the Release Namespace
```bash
kubectl create namespace compassx
```

### 2. Install the Chart
```bash
helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  --set ingress.hosts[0].host=compassx.yourdomain.com
```

### 3. Verify Deployment
```bash
kubectl get pods -n compassx
helm status compassx -n compassx
```

---

## ☁️ Multi-Cloud Deployment Presets

Ready-to-use cloud presets and step-by-step guides are provided in the [`deployments/`](../) directory:

* **[Amazon Web Services (AWS EKS)](../aws/README.md)**:
  * In-Cluster (`gp3` EBS CSI): [`deployments/aws/values-incluster.yaml`](../aws/values-incluster.yaml)
  * Managed Cloud (RDS Aurora + ElastiCache + S3 + ALB): [`deployments/aws/values-managed.yaml`](../aws/values-managed.yaml)

* **[Microsoft Azure (Azure AKS)](../azure/README.md)**:
  * In-Cluster (`managed-csi` Disk): [`deployments/azure/values-incluster.yaml`](../azure/values-incluster.yaml)
  * Managed Cloud (Flexible Server + Cache for Redis + Blob Storage): [`deployments/azure/values-managed.yaml`](../azure/values-managed.yaml)

* **[Google Cloud Platform (Google GKE)](../gcp/README.md)**:
  * In-Cluster (`standard-rwo` Disk): [`deployments/gcp/values-incluster.yaml`](../gcp/values-incluster.yaml)
  * Managed Cloud (Cloud SQL + Memorystore + Cloud Storage): [`deployments/gcp/values-managed.yaml`](../gcp/values-managed.yaml)

---

## ⚙️ Configuration Parameters

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `global.imageRegistry` | Global container image registry | `""` |
| `global.imagePullSecrets` | Global image pull secrets | `[]` |
| `global.storageClass` | Global default StorageClass | `""` |
| `secrets.jwtSecret` | JWT secret for user authentication | `change-me-in-production...` |
| `secrets.secretKey` | Encryption key for connection credentials | `change-me-in-production...` |
| `secrets.catalogEncryptionKey` | Fernet 32-byte key for Data Catalog secrets | `""` |
| `backend.replicaCount` | Replicas for FastAPI backend | `1` |
| `backend.image.repository` | Backend container image | `ghcr.io/compassx-platform/backend` |
| `backend.image.tag` | Backend image tag | `v0.4.0` |
| `backend.resources` | Backend CPU/Memory requests & limits | `{requests: 500m/1Gi, limits: 2000m/4Gi}` |
| `backend.autoscaling.enabled` | Enable Horizontal Pod Autoscaling (HPA) | `false` |
| `frontend.replicaCount` | Replicas for Frontend UI | `1` |
| `frontend.image.repository` | Frontend container image | `ghcr.io/compassx-platform/frontend` |
| `frontend.image.tag` | Frontend image tag | `v0.4.0` |
| `enterpriseGateway.replicaCount` | Replicas for Jupyter Enterprise Gateway | `1` |
| `enterpriseGateway.image.repository` | Enterprise Gateway container image | `ghcr.io/compassx-platform/enterprise-gateway` |
| `enterpriseGateway.image.tag` | Enterprise Gateway image tag | `v0.4.0` |
| `airflow.enabled` | Enable Apache Airflow stack | `true` |
| `airflow.image.repository` | Airflow container image | `apache/airflow` |
| `airflow.image.tag` | Airflow image tag | `2.9.3-python3.11` |
| `postgresql.enabled` | Deploy in-cluster PostgreSQL (pgvector) | `true` |
| `postgresql.persistence.size` | Volume size for PostgreSQL data | `20Gi` |
| `externalPostgresql.host` | External PostgreSQL hostname | `""` |
| `redis.enabled` | Deploy in-cluster Redis | `true` |
| `externalRedis.host` | External Redis hostname | `""` |
| `minio.enabled` | Deploy in-cluster MinIO object storage | `true` |
| `minio.persistence.size` | Volume size for MinIO data | `50Gi` |
| `externalStorage.backend` | External storage type (`s3`, `azure`, `minio`) | `"s3"` |
| `externalStorage.bucket` | Storage bucket name | `"compassx"` |
| `prometheus.enabled` | Deploy in-cluster Prometheus monitoring | `true` |
| `ingress.enabled` | Enable Ingress controller routing | `true` |
| `ingress.className` | Ingress class (`nginx`, `alb`, `azure-application-gateway`) | `"nginx"` |
| `ingress.hosts` | List of ingress hostnames and path mappings | See `values.yaml` |
| `ingress.tls` | Ingress TLS certificate configurations | `[]` |

---

## 🔄 Upgrades & Maintenance

### Upgrade Release
```bash
helm upgrade compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f your-custom-values.yaml
```

### Rollback Release
```bash
helm rollback compassx <REVISION_NUMBER> --namespace compassx
```

### Uninstall Release
```bash
helm uninstall compassx --namespace compassx
```

---

## 🩺 Troubleshooting

- **Check Pod Logs**:
  ```bash
  kubectl logs -l app.kubernetes.io/component=backend -n compassx --tail=100 -f
  kubectl logs -l app.kubernetes.io/component=enterprise-gateway -n compassx --tail=100 -f
  ```
- **Verify Database Connectivity**:
  ```bash
  kubectl exec -it deployment/compassx-backend -n compassx -- python -c "import psycopg2; print('DB reachable')"
  ```
- **Inspect Ingress Routing**:
  ```bash
  kubectl describe ingress compassx -n compassx
  ```
