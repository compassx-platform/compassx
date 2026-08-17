// TypeScript types for the Jobs module — mirrors backend Pydantic schemas

export type JobStatus = 'active' | 'paused' | 'archived';
export type RunState = 'queued' | 'running' | 'success' | 'failed' | 'up_for_retry' | 'cancelled';
export type TaskRunState = 'queued' | 'running' | 'success' | 'failed' | 'up_for_retry' | 'upstream_failed' | 'skipped';
export type TriggerType = 'scheduled' | 'manual' | 'rerun';
export type TaskType = 'notebook' | 'query' | 'dashboard_refresh';

export interface TaskDefinition {
  task_key: string;
  name: string;
  task_type: TaskType;
  target_ref?: string;
  parameters: Record<string, unknown>;
  depends_on: string[];
  retry_count?: number;
  retry_delay_seconds?: number;
}

export interface RetryPolicy {
  retries: number;
  retry_delay_seconds: number;
  backoff_factor: number;
}

export interface Job {
  job_id: string;
  workspace_id?: string;
  name: string;
  description?: string;
  owner_user_id?: string;
  status: JobStatus;
  current_version?: number;
  draft_version?: number;
  has_unpublished_changes: boolean;
  created_at: string;
  updated_at: string;
  schedule_cron?: string;
  timezone?: string;
  max_active_runs?: number;
  retry_policy?: RetryPolicy;
  task_definitions: TaskDefinition[];
  last_run_state?: RunState;
  last_run_started_at?: string;
  last_run_id?: string;
  task_count: number;
  recent_runs?: JobRun[];
  publish_state?: 'publishing' | 'active' | 'error';
  airflow_confirmed_at?: string;
}

export interface JobVersion {
  job_version_id: string;
  job_id: string;
  version_number: number;
  schedule_cron?: string;
  timezone: string;
  max_active_runs: number;
  retry_policy: RetryPolicy;
  task_definitions: TaskDefinition[];
  is_published: boolean;
  published_at?: string;
  published_by?: string;
  created_at: string;
  created_by?: string;
}

export interface TaskRun {
  task_run_id: string;
  job_run_id: string;
  task_key: string;
  try_number: number;
  state: TaskRunState;
  execution_ref?: string;
  started_at?: string;
  ended_at?: string;
  duration_seconds?: number;
}

export interface JobRun {
  job_run_id: string;
  job_id: string;
  job_version?: number;
  dag_run_id?: string;
  trigger_type: TriggerType;
  triggered_by?: string;
  parent_job_run_id?: string;
  state: RunState;
  started_at?: string;
  ended_at?: string;
  last_synced_at?: string;
  duration_seconds?: number;
  task_runs: TaskRun[];
}

export interface DraftUpdate {
  schedule_cron?: string;
  timezone: string;
  max_active_runs: number;
  retry_policy: RetryPolicy;
  task_definitions: TaskDefinition[];
}
