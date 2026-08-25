# GCP Deployment Guide for CompassX

This folder provides ready-to-use Helm values presets and instructions for deploying CompassX on **Google Cloud Platform (GCP)** using **Google Kubernetes Engine (GKE)**.

---

## 📁 Available Presets

| File | Type | Description |
| :--- | :--- | :--- |
| [`values-incluster.yaml`](./values-incluster.yaml) | **Self-Contained** | Full CompassX stack running in GKE with Google Persistent Disk `standard-rwo` CSI storage. |
| [`values-managed.yaml`](./values-managed.yaml) | **Enterprise Managed** | GKE + Google Cloud SQL for PostgreSQL (pgvector) + Cloud Memorystore for Redis + Google Cloud Storage (GCS). |

---

## 🚀 Quickstart: Deploying on Google Cloud GKE

### 1. Prerequisites
- Google Cloud SDK (`gcloud auth login`)
- `kubectl` and `helm` (v3.8+)

### 2. Create GKE Cluster (if not already existing)
```bash
gcloud container clusters create compassx-cluster \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type e2-standard-4 \
  --enable-autoscaling --min-nodes 2 --max-nodes 6

gcloud container clusters get-credentials compassx-cluster --zone us-central1-a
```

### 3. Option A: Install Self-Contained GKE Stack
```bash
kubectl create namespace compassx

helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/gcp/values-incluster.yaml \
  --set ingress.hosts[0].host="compassx.yourcompany.com"
```

### 4. Option B: Install with Managed GCP Services (Cloud SQL + GCS + Memorystore)
```bash
kubectl create namespace compassx

helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/gcp/values-managed.yaml \
  --set externalPostgresql.host="10.0.0.5" \
  --set externalPostgresql.password="YOUR_CLOUD_SQL_PASSWORD" \
  --set externalStorage.bucket="your-gcs-datalake-bucket" \
  --set externalStorage.accessKey="YOUR_GCS_HMAC_KEY" \
  --set externalStorage.secretKey="YOUR_GCS_HMAC_SECRET" \
  --set ingress.hosts[0].host="app.compassx.yourcompany.com"
```
