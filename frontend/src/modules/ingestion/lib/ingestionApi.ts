/**
 * Ingestion module API layer.
 * All calls use the shared axios instance from @/lib/api.
 * Base URL pattern: /workspaces/{workspaceId}/ingestion/...
 */
import api from '@/lib/api';
import type {
  Connection, ConnectionCreate, ConnectionUpdate,
  JobConfig, JobConfigCreate, JobConfigUpdate,
  IngestionRun, IngestionRunItem, TriggerResponse,
} from './ingestionTypes';

function base(workspaceId: string) {
  return `/workspaces/${workspaceId}/ingestion`;
}

// ── Connections ───────────────────────────────────────────────────────────────

export async function listConnections(workspaceId: string): Promise<Connection[]> {
  const res = await api.get(`${base(workspaceId)}/connections`);
  return res.data;
}

export async function getConnection(workspaceId: string, connectionId: string): Promise<Connection> {
  const res = await api.get(`${base(workspaceId)}/connections/${connectionId}`);
  return res.data;
}

export async function createConnection(
  workspaceId: string,
  body: ConnectionCreate,
): Promise<Connection> {
  const res = await api.post(`${base(workspaceId)}/connections`, body);
  return res.data;
}

export async function updateConnection(
  workspaceId: string,
  connectionId: string,
  body: ConnectionUpdate,
): Promise<Connection> {
  const res = await api.patch(`${base(workspaceId)}/connections/${connectionId}`, body);
  return res.data;
}

export async function rotateConnectionSecret(
  workspaceId: string,
  connectionId: string,
  newSecretValue: string,
): Promise<void> {
  await api.post(`${base(workspaceId)}/connections/${connectionId}/rotate-secret`, {
    new_secret_value: newSecretValue,
  });
}

export async function deleteConnection(workspaceId: string, connectionId: string): Promise<void> {
  await api.delete(`${base(workspaceId)}/connections/${connectionId}`);
}

// ── Job Configs ───────────────────────────────────────────────────────────────

export async function listJobConfigs(
  workspaceId: string,
  connectionId?: string,
): Promise<JobConfig[]> {
  const params = connectionId ? { connection_id: connectionId } : {};
  const res = await api.get(`${base(workspaceId)}/job-configs`, { params });
  return res.data;
}

export async function getJobConfig(workspaceId: string, jobConfigId: string): Promise<JobConfig> {
  const res = await api.get(`${base(workspaceId)}/job-configs/${jobConfigId}`);
  return res.data;
}

export async function createJobConfig(
  workspaceId: string,
  body: JobConfigCreate,
): Promise<JobConfig> {
  const res = await api.post(`${base(workspaceId)}/job-configs`, body);
  return res.data;
}

export async function updateJobConfig(
  workspaceId: string,
  jobConfigId: string,
  body: JobConfigUpdate,
): Promise<JobConfig> {
  const res = await api.patch(`${base(workspaceId)}/job-configs/${jobConfigId}`, body);
  return res.data;
}

export async function enableJobConfig(workspaceId: string, jobConfigId: string): Promise<void> {
  await api.post(`${base(workspaceId)}/job-configs/${jobConfigId}/enable`);
}

export async function disableJobConfig(workspaceId: string, jobConfigId: string): Promise<void> {
  await api.post(`${base(workspaceId)}/job-configs/${jobConfigId}/disable`);
}

export async function triggerRun(
  workspaceId: string,
  jobConfigId: string,
): Promise<TriggerResponse> {
  const res = await api.post(`${base(workspaceId)}/job-configs/${jobConfigId}/trigger`);
  return res.data;
}

export async function deleteJobConfig(workspaceId: string, jobConfigId: string): Promise<void> {
  await api.delete(`${base(workspaceId)}/job-configs/${jobConfigId}`);
}

export async function resetWatermark(
  workspaceId: string,
  jobConfigId: string,
  paramValue?: string,
): Promise<void> {
  await api.post(`${base(workspaceId)}/job-configs/${jobConfigId}/watermarks/reset`, {
    param_value: paramValue ?? null,
  });
}

// ── Runs ──────────────────────────────────────────────────────────────────────

export async function listRuns(
  workspaceId: string,
  jobConfigId: string,
  limit = 50,
  status?: string,
): Promise<IngestionRun[]> {
  const params: Record<string, unknown> = { limit };
  if (status) params.status = status;
  const res = await api.get(`${base(workspaceId)}/job-configs/${jobConfigId}/runs`, { params });
  return res.data;
}

export async function getRun(workspaceId: string, runId: string): Promise<IngestionRun> {
  const res = await api.get(`${base(workspaceId)}/runs/${runId}`);
  return res.data;
}

export async function getRunItems(
  workspaceId: string,
  runId: string,
  status?: string,
): Promise<IngestionRunItem[]> {
  const params = status ? { status } : {};
  const res = await api.get(`${base(workspaceId)}/runs/${runId}/items`, { params });
  return res.data;
}
