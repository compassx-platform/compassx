# Azure Deployment Guide for CompassX

This folder provides ready-to-use Helm values presets and instructions for deploying CompassX on **Microsoft Azure** using **Azure Kubernetes Service (AKS)**.

---

## 📁 Available Presets

| File | Type | Description |
| :--- | :--- | :--- |
| [`values-incluster.yaml`](./values-incluster.yaml) | **Self-Contained** | Full CompassX stack running in AKS with Azure Managed Disk `managed-csi` CSI storage. |
| [`values-managed.yaml`](./values-managed.yaml) | **Enterprise Managed** | AKS + Azure Database for PostgreSQL Flexible Server (pgvector) + Azure Cache for Redis + Azure Blob Storage. |

---

## 🚀 Quickstart: Deploying on Azure AKS

### 1. Prerequisites
- Azure CLI logged in (`az login`)
- `kubectl` and `helm` (v3.8+)

### 2. Create AKS Cluster (if not already existing)
```bash
az group create --name rg-compassx-prod --location eastus

az aks create \
  --resource-group rg-compassx-prod \
  --name aks-compassx-prod \
  --node-count 2 \
  --min-count 2 \
  --max-count 5 \
  --enable-cluster-autoscaler \
  --node-vm-size Standard_D4s_v5 \
  --enable-managed-identity \
  --generate-ssh-keys

az aks get-credentials --resource-group rg-compassx-prod --name aks-compassx-prod
```

### 3. Option A: Install Self-Contained AKS Stack
```bash
kubectl create namespace compassx

helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/azure/values-incluster.yaml \
  --set ingress.hosts[0].host="compassx.yourcompany.com"
```

### 4. Option B: Install with Managed Azure Services (Flexible Server + Blob Storage + Redis)
```bash
kubectl create namespace compassx

helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/azure/values-managed.yaml \
  --set externalPostgresql.host="compassx-db.postgres.database.azure.com" \
  --set externalPostgresql.password="YOUR_AZURE_PG_PASSWORD" \
  --set externalStorage.bucket="compassx-datalake-container" \
  --set externalStorage.accessKey="compassxstorageacct" \
  --set externalStorage.secretKey="YOUR_AZURE_STORAGE_KEY" \
  --set ingress.hosts[0].host="app.compassx.yourcompany.com"
```
