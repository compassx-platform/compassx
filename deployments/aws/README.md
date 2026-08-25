# AWS Deployment Guide for CompassX

This folder provides ready-to-use Helm values presets and instructions for deploying CompassX on **Amazon Web Services (AWS)** using **Amazon Elastic Kubernetes Service (EKS)**.

---

## 📁 Available Presets

| File | Type | Description |
| :--- | :--- | :--- |
| [`values-incluster.yaml`](./values-incluster.yaml) | **Self-Contained** | Full CompassX stack running in EKS with EBS `gp3` CSI storage. |
| [`values-managed.yaml`](./values-managed.yaml) | **Enterprise Managed** | EKS + AWS RDS PostgreSQL (pgvector) + ElastiCache Redis + Amazon S3. |

---

## 🚀 Quickstart: Deploying on AWS EKS

### 1. Prerequisites
- AWS CLI configured (`aws configure`)
- `kubectl` and `helm` (v3.8+)
- `eksctl` (optional, for cluster creation)

### 2. Create EKS Cluster (if not already existing)
```bash
eksctl create cluster \
  --name compassx-cluster \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type m5.xlarge \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 6 \
  --managed
```

### 3. Option A: Install Self-Contained EKS Stack
```bash
kubectl create namespace compassx

helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/aws/values-incluster.yaml \
  --set ingress.hosts[0].host="compassx.yourcompany.com"
```

### 4. Option B: Install with Managed AWS Services (RDS + S3 + ElastiCache)
```bash
kubectl create namespace compassx

helm install compassx ./deployments/helm/compassx \
  --namespace compassx \
  -f ./deployments/aws/values-managed.yaml \
  --set externalPostgresql.host="your-rds-endpoint.rds.amazonaws.com" \
  --set externalPostgresql.password="YOUR_RDS_PASSWORD" \
  --set externalRedis.host="your-elasticache-endpoint.cache.amazonaws.com" \
  --set externalStorage.bucket="your-company-compassx-datalake" \
  --set externalStorage.accessKey="YOUR_AWS_ACCESS_KEY_ID" \
  --set externalStorage.secretKey="YOUR_AWS_SECRET_KEY" \
  --set ingress.hosts[0].host="app.compassx.yourcompany.com"
```
