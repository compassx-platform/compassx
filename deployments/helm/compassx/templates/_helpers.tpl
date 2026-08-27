{{/*
Expand the name of the chart.
*/}}
{{- define "compassx.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "compassx.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "compassx.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "compassx.labels" -}}
helm.sh/chart: {{ include "compassx.chart" . }}
{{ include "compassx.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "compassx.selectorLabels" -}}
app.kubernetes.io/name: {{ include "compassx.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: compassx
{{- end }}

{{/*
Component fullname helpers
*/}}
{{- define "compassx.backendFullname" -}}
{{- printf "%s-backend" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.frontendFullname" -}}
{{- printf "%s-frontend" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.enterpriseGatewayFullname" -}}
{{- printf "%s-enterprise-gateway" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.airflowFullname" -}}
{{- printf "%s-airflow" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.postgresFullname" -}}
{{- printf "%s-postgres" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.redisFullname" -}}
{{- printf "%s-redis" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.minioFullname" -}}
{{- printf "%s-minio" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "compassx.prometheusFullname" -}}
{{- printf "%s-prometheus" (include "compassx.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Service Account names
*/}}
{{- define "compassx.backendServiceAccountName" -}}
{{- if .Values.backend.serviceAccount.create }}
{{- default (printf "%s-backend" (include "compassx.fullname" .)) .Values.backend.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.backend.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "compassx.enterpriseGatewayServiceAccountName" -}}
{{- if .Values.enterpriseGateway.serviceAccount.create }}
{{- default (printf "%s-eg" (include "compassx.fullname" .)) .Values.enterpriseGateway.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.enterpriseGateway.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "compassx.airflowServiceAccountName" -}}
{{- if .Values.airflow.serviceAccount.create }}
{{- default (printf "%s-airflow" (include "compassx.fullname" .)) .Values.airflow.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.airflow.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host & port helpers
*/}}
{{- define "compassx.postgresHost" -}}
{{- if .Values.postgresql.enabled }}
{{- include "compassx.postgresFullname" . }}
{{- else }}
{{- .Values.externalPostgresql.host }}
{{- end }}
{{- end }}

{{- define "compassx.postgresPort" -}}
{{- if .Values.postgresql.enabled }}
{{- "5432" }}
{{- else }}
{{- .Values.externalPostgresql.port | default "5432" }}
{{- end }}
{{- end }}

{{- define "compassx.postgresUser" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.username | default "postgres" }}
{{- else }}
{{- .Values.externalPostgresql.username | default "postgres" }}
{{- end }}
{{- end }}

{{- define "compassx.postgresSecretName" -}}
{{- if .Values.externalPostgresql.existingSecret }}
{{- .Values.externalPostgresql.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "compassx.fullname" .) }}
{{- end }}
{{- end }}

{{- define "compassx.postgresSecretKey" -}}
{{- if .Values.postgresql.enabled }}
{{- "pg-password" }}
{{- else if .Values.externalPostgresql.existingSecret }}
{{- default "password" .Values.externalPostgresql.secretKeys.password }}
{{- else }}
{{- "pg-password" }}
{{- end }}
{{- end }}

{{/*
Redis host & port helpers
*/}}
{{- define "compassx.redisHost" -}}
{{- if .Values.redis.enabled }}
{{- include "compassx.redisFullname" . }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{- define "compassx.redisPort" -}}
{{- if .Values.redis.enabled }}
{{- "6379" }}
{{- else }}
{{- .Values.externalRedis.port | default "6379" }}
{{- end }}
{{- end }}

{{- define "compassx.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s:6379/0" (include "compassx.redisFullname" .) }}
{{- else if .Values.externalRedis.url }}
{{- .Values.externalRedis.url }}
{{- else }}
{{- printf "redis://%s:%v/0" .Values.externalRedis.host (.Values.externalRedis.port | default "6379") }}
{{- end }}
{{- end }}

{{/*
MinIO / Storage endpoint helpers
*/}}
{{- define "compassx.storageEndpoint" -}}
{{- if .Values.minio.enabled }}
{{- printf "http://%s:9000" (include "compassx.minioFullname" .) }}
{{- else }}
{{- .Values.externalStorage.endpoint }}
{{- end }}
{{- end }}

{{- define "compassx.storageSecretName" -}}
{{- if .Values.externalStorage.existingSecret }}
{{- .Values.externalStorage.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "compassx.fullname" .) }}
{{- end }}
{{- end }}

{{- define "compassx.storageSecretKey" -}}
{{- if .Values.minio.enabled }}
{{- "minio-root-password" }}
{{- else if .Values.externalStorage.existingSecret }}
{{- default "secret-key" .Values.externalStorage.secretKeys.secretKey }}
{{- else }}
{{- "storage-secret-key" }}
{{- end }}
{{- end }}
