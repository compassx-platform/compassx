/**
 * Jobs module API layer — all calls use the shared axios instance from @/lib/api
 */
import api from '@/lib/api';
import type {
  Job, JobRun, JobVersion, DraftUpdate,
} from './jobsTypes';

const BASE = '/jobs';
const RUN_BASE = '/job-runs';

// ── Jobs ─────────────────────────────────────────────────────────────────────

export async function listJobs(params?: {
  search?: string;
  status?: string;
  workspace_id?: string;
}): Promise<Job[]> {
  const res = await api.get(BASE, { params });
  return res.data;
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await api.get(`${BASE}/${jobId}`);
  return res.data;
}

export async function createJob(body: { name: string; description?: string; workspace_id?: string }): Promise<Job> {
  const res = await api.post(BASE, body);
  return res.data;
}

export async function updateJob(jobId: string, body: { name?: string; description?: string }): Promise<Job> {
  const res = await api.put(`${BASE}/${jobId}`, body);
  return res.data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`${BASE}/${jobId}`);
}

export async function saveDraft(jobId: string, body: DraftUpdate): Promise<JobVersion> {
  const res = await api.put(`${BASE}/${jobId}/draft`, body);
  return res.data;
}

export async function publishJob(jobId: string): Promise<Job> {
  const res = await api.post(`${BASE}/${jobId}/publish`);
  return res.data;
}

export async function getPublishStatus(jobId: string): Promise<{
  state: 'draft' | 'publishing' | 'active' | 'error';
  confirmed_at?: string;
  dag_id?: string;
}> {
  const res = await api.get(`${BASE}/${jobId}/status`);
  return res.data;
}

export async function getVersion(jobId: string, which: 'published' | 'draft' = 'published'): Promise<JobVersion> {
  const res = await api.get(`${BASE}/${jobId}/version`, { params: { which } });
  return res.data;
}

export async function pauseJob(jobId: string): Promise<Job> {
  const res = await api.post(`${BASE}/${jobId}/pause`);
  return res.data;
}

export async function resumeJob(jobId: string): Promise<Job> {
  const res = await api.post(`${BASE}/${jobId}/resume`);
  return res.data;
}

export async function archiveJob(jobId: string): Promise<Job> {
  const res = await api.post(`${BASE}/${jobId}/archive`);
  return res.data;
}

export async function triggerRun(jobId: string): Promise<JobRun> {
  const res = await api.post(`${BASE}/${jobId}/run`, {});
  return res.data;
}

export async function listRuns(jobId: string, limit = 50): Promise<JobRun[]> {
  const res = await api.get(`${BASE}/${jobId}/runs`, { params: { limit } });
  return res.data;
}

// ── Job Runs ──────────────────────────────────────────────────────────────────

export async function getRun(runId: string): Promise<JobRun> {
  const res = await api.get(`${RUN_BASE}/${runId}`);
  return res.data;
}

export async function cancelRun(runId: string): Promise<JobRun> {
  const res = await api.post(`${RUN_BASE}/${runId}/cancel`);
  return res.data;
}

export async function rerun(runId: string): Promise<JobRun> {
  const res = await api.post(`${RUN_BASE}/${runId}/rerun`);
  return res.data;
}

export async function retryTask(runId: string, taskKey: string): Promise<JobRun> {
  const res = await api.post(`${RUN_BASE}/${runId}/tasks/${encodeURIComponent(taskKey)}/retry`);
  return res.data;
}
