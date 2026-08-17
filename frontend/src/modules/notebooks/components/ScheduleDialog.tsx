import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Plus, Trash2, X } from 'lucide-react';
import { extractApiError, useToast } from '@/lib/toast';
import ScheduleBuilder from '@/modules/jobs/components/ScheduleBuilder';
import * as jobsApi from '@/modules/jobs/lib/jobsApi';
import type {
  DraftUpdate,
  Job,
  JobVersion,
  TaskDefinition,
} from '@/modules/jobs/lib/jobsTypes';

interface Props {
  notebookPath: string;
  onClose: () => void;
}

interface ParameterRow {
  key: string;
  value: string;
}

const DEFAULT_RETRY_POLICY = {
  retries: 0,
  retry_delay_seconds: 300,
  backoff_factor: 1,
};

function notebookName(path: string): string {
  return path.split('/').filter(Boolean).pop()?.replace(/\.ipynb$/i, '') || 'Notebook';
}

function taskKey(name: string, tasks: TaskDefinition[]): string {
  const root = name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'run_notebook';
  const used = new Set(tasks.map((task) => task.task_key));
  if (!used.has(root)) return root;
  let suffix = 2;
  while (used.has(`${root}_${suffix}`)) suffix += 1;
  return `${root}_${suffix}`;
}

function parametersObject(rows: ParameterRow[]): Record<string, string> {
  return Object.fromEntries(
    rows.filter((row) => row.key.trim()).map((row) => [row.key.trim(), row.value]),
  );
}

export default function ScheduleDialog({ notebookPath, onClose }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const name = notebookName(notebookPath);
  const [mode, setMode] = useState<'new' | 'existing'>('new');
  const [selectedJobId, setSelectedJobId] = useState('');
  const [jobName, setJobName] = useState(`${name} Job`);
  const [taskName, setTaskName] = useState(`Run ${name}`);
  const [cron, setCron] = useState<string | undefined>('0 2 * * *');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [parameters, setParameters] = useState<ParameterRow[]>([]);
  const [dependsOn, setDependsOn] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.listJobs(),
  });

  const availableJobs = useMemo(
    () => jobs.filter((job) => job.status !== 'archived'),
    [jobs],
  );
  const selectedJob = availableJobs.find((job) => job.job_id === selectedJobId);
  const availableDependencies = selectedJob?.task_definitions ?? [];

  async function baseVersion(job: Job): Promise<JobVersion | null> {
    if (job.draft_version) return jobsApi.getVersion(job.job_id, 'draft');
    if (job.current_version) return jobsApi.getVersion(job.job_id, 'published');
    return null;
  }

  async function persist(publish: boolean) {
    setSaving(true);
    setError(null);
    try {
      let job: Job;
      let base: JobVersion | null = null;
      if (mode === 'new') {
        job = await jobsApi.createJob({
          name: jobName.trim() || `${name} Job`,
        });
      } else {
        if (!selectedJob) throw new Error('Select a job first.');
        job = selectedJob;
        base = await baseVersion(job);
      }

      const existingTasks = base?.task_definitions ?? [];
      const task: TaskDefinition = {
        task_key: taskKey(taskName, existingTasks),
        name: taskName.trim() || `Run ${name}`,
        task_type: 'notebook',
        target_ref: notebookPath,
        parameters: parametersObject(parameters),
        depends_on: dependsOn,
      };
      const draft: DraftUpdate = {
        schedule_cron: mode === 'existing' && base ? base.schedule_cron : cron,
        timezone: mode === 'existing' && base ? base.timezone : timezone,
        max_active_runs: base?.max_active_runs ?? 1,
        retry_policy: base?.retry_policy ?? DEFAULT_RETRY_POLICY,
        task_definitions: [...existingTasks, task],
      };

      await jobsApi.saveDraft(job.job_id, draft);
      if (publish) await jobsApi.publishJob(job.job_id);

      await queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast.success(
        publish
          ? `Job "${job.name}" published and is registering with the scheduler.`
          : `Notebook task saved to draft job "${job.name}".`,
      );
      onClose();
    } catch (cause) {
      const message = extractApiError(cause);
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="nb-schedule-overlay" onClick={onClose}>
      <div className="nb-schedule-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="nb-schedule-header">
          <span><CalendarClock size={15} /> Schedule notebook</span>
          <button className="nb-schedule-close" onClick={onClose} title="Close">
            <X size={15} />
          </button>
        </div>

        <div className="nb-schedule-body" style={{ gap: 18 }}>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{notebookPath}</div>

          <div className="nb-schedule-tabs">
            <button
              className={`nb-schedule-tab ${mode === 'new' ? 'active' : ''}`}
              onClick={() => setMode('new')}
            >
              Create new job
            </button>
            <button
              className={`nb-schedule-tab ${mode === 'existing' ? 'active' : ''}`}
              onClick={() => setMode('existing')}
            >
              Add to existing job
            </button>
          </div>

          {mode === 'new' ? (
            <>
              <div className="nb-schedule-field">
                <label className="nb-schedule-label">Job name</label>
                <input
                  className="nb-schedule-input"
                  value={jobName}
                  onChange={(event) => setJobName(event.target.value)}
                />
              </div>
              <ScheduleBuilder
                value={cron}
                timezone={timezone}
                onChange={(nextCron, nextTimezone) => {
                  setCron(nextCron);
                  setTimezone(nextTimezone);
                }}
              />
            </>
          ) : (
            <div className="nb-schedule-field">
              <label className="nb-schedule-label">Job</label>
              <select
                className="nb-schedule-select"
                value={selectedJobId}
                disabled={isLoading}
                onChange={(event) => {
                  setSelectedJobId(event.target.value);
                  setDependsOn([]);
                }}
              >
                <option value="">Select a job</option>
                {availableJobs.map((job) => (
                  <option key={job.job_id} value={job.job_id}>{job.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="nb-schedule-field">
            <label className="nb-schedule-label">Task name</label>
            <input
              className="nb-schedule-input"
              value={taskName}
              onChange={(event) => setTaskName(event.target.value)}
            />
          </div>

          {mode === 'existing' && availableDependencies.length > 0 && (
            <div className="nb-schedule-field">
              <label className="nb-schedule-label">Depends on</label>
              {availableDependencies.map((task) => (
                <label key={task.task_key} style={{ display: 'flex', gap: 7, fontSize: 12 }}>
                  <input
                    type="checkbox"
                    checked={dependsOn.includes(task.task_key)}
                    onChange={(event) => setDependsOn((current) => (
                      event.target.checked
                        ? [...current, task.task_key]
                        : current.filter((key) => key !== task.task_key)
                    ))}
                  />
                  {task.name}
                </label>
              ))}
            </div>
          )}

          <div className="nb-schedule-field">
            <div className="nb-schedule-row">
              <label className="nb-schedule-label" style={{ margin: 0 }}>Parameters</label>
              <button
                className="nb-schedule-add-param"
                onClick={() => setParameters((rows) => [...rows, { key: '', value: '' }])}
              >
                <Plus size={12} /> Add
              </button>
            </div>
            {parameters.map((parameter, index) => (
              <div className="nb-schedule-row" key={index}>
                <input
                  className="nb-schedule-input"
                  placeholder="Key"
                  value={parameter.key}
                  onChange={(event) => setParameters((rows) => rows.map((row, rowIndex) => (
                    rowIndex === index ? { ...row, key: event.target.value } : row
                  )))}
                />
                <input
                  className="nb-schedule-input"
                  placeholder="Value"
                  value={parameter.value}
                  onChange={(event) => setParameters((rows) => rows.map((row, rowIndex) => (
                    rowIndex === index ? { ...row, value: event.target.value } : row
                  )))}
                />
                <button
                  className="nb-schedule-remove-param"
                  onClick={() => setParameters((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>

          {error && <div style={{ fontSize: 12, color: '#b91c1c' }}>{error}</div>}
        </div>

        <div className="nb-schedule-footer">
          <button className="nb-schedule-btn" onClick={onClose}>Cancel</button>
          <button
            className="nb-schedule-btn"
            disabled={saving || (mode === 'existing' && !selectedJob)}
            onClick={() => void persist(false)}
          >
            Save as draft
          </button>
          <button
            className="nb-schedule-btn nb-schedule-btn-primary"
            disabled={saving || (mode === 'existing' && !selectedJob)}
            onClick={() => void persist(true)}
          >
            {saving ? 'Saving...' : mode === 'new' ? 'Create & Publish' : 'Add & Publish'}
          </button>
        </div>
      </div>
    </div>
  );
}
