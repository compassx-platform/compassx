# CompassX Platform Deployments

This directory contains all deployment options for the **CompassX Platform**, organized by target runtime and cloud provider.

---

## 🗂️ Directory Structure

```
deployments/
├── docker-compose/              # Docker Compose stack (Local-dev & Full Docker container stack)
│   ├── docker-compose.yml
│   ├── postgres/
│   └── prometheus/
│
├── aws/                         # Amazon Web Services (AWS EKS)
│   ├── values-incluster.yaml    # Self-contained in-cluster EKS stack (EBS gp3)
│   ├── values-managed.yaml      # EKS + AWS RDS PostgreSQL + ElastiCache + S3 + ALB
│   └── README.md                # Step-by-step AWS deployment guide
│
├── azure/                       # Microsoft Azure (Azure AKS)
│   ├── values-incluster.yaml    # Self-contained in-cluster AKS stack (managed-csi)
│   ├── values-managed.yaml      # AKS + Azure Flexible Server + Blob Storage + Redis
│   └── README.md                # Step-by-step Azure deployment guide
│
├── gcp/                         # Google Cloud Platform (Google GKE)
│   ├── values-incluster.yaml    # Self-contained in-cluster GKE stack (standard-rwo)
│   ├── values-managed.yaml      # GKE + Cloud SQL + Memorystore + GCS
│   └── README.md                # Step-by-step GCP deployment guide
│
└── helm/
    └── compassx/                # The Core Helm Chart powering all cloud deployments
        ├── Chart.yaml
        ├── values.yaml          # Complete base configuration schema
        └── templates/           # Kubernetes manifests
```

---

## 🚀 Choosing Your Deployment Method

### 1. Local Development (`local-dev`)
Run frontend and backend natively on your host machine with containerized infrastructure:
```bash
./compassx up                     # Windows: .\compassx.cmd up
```

### 2. Standalone Docker Compose Stack
Deploy all services in local Docker containers:
```bash
docker compose -f deployments/docker-compose/docker-compose.yml up -d
# Or via CLI:
./compassx up --profile docker
```

### 3. Kubernetes Cloud Deployments (Helm)

Pick your cloud provider and deploy:

* **Amazon Web Services (AWS EKS)**: See [`deployments/aws/`](./aws/README.md)
  ```bash
  helm install compassx ./deployments/helm/compassx -n compassx -f ./deployments/aws/values-managed.yaml
  ```

* **Microsoft Azure (Azure AKS)**: See [`deployments/azure/`](./azure/README.md)
  ```bash
  helm install compassx ./deployments/helm/compassx -n compassx -f ./deployments/azure/values-managed.yaml
  ```

* **Google Cloud Platform (Google GKE)**: See [`deployments/gcp/`](./gcp/README.md)
  ```bash
  helm install compassx ./deployments/helm/compassx -n compassx -f ./deployments/gcp/values-managed.yaml
  ```
