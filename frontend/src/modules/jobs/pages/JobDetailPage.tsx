/**
 * Job Detail Page — /jobs/:jobId
 * Tabs: Tasks (graph editor), Runs (history), Schedule, Permissions
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight, Play, Pause, RotateCcw, Archive, Trash2,
  Plus, Save, Upload, MoreVertical, AlertCircle, Pencil,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as jobsApi from '../lib/jobsApi';
import { cronToHuman, relativeTime, formatDuration } from '../lib/cronUtils';
import type { Job, TaskDefinition, JobRun } from '../lib/jobsTypes';
import StatusPill from '../components/StatusPill';
import JobFormModal from '../components/JobFormModal';
import TaskDrawer from '../components/TaskDrawer';
import TaskGraphCanvas from '../components/TaskGraphCanvas';
import ScheduleBuilder from '../components/ScheduleBuilder';
import ConfirmActionModal from '../components/ConfirmActionModal';
import JobRunsTimelineChart from '../components/JobRunsTimelineChart';

type Tab = 'runs' | 'tasks' | 'schedule' | 'permissions';

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useScopedNavigate();

  const rawTab = searchParams.get('tab');
  const activeTab: Tab = (rawTab === 'tasks' || rawTab === 'schedule' || rawTab === 'permissions') ? rawTab : 'runs';

  const handleTabChange = useCallback((id: Tab) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (id === 'runs') {
        next.delete('tab');
      } else {
        next.set('tab', id);
      }
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  const [editJobOpen, setEditJobOpen] = useState(false);
  const [overflowOpen, setOverflowOpen] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmRun, setConfirmRun] = useState(false);

  // Task editor state
  const [editingTaskKey, setEditingTaskKey] = useState<string | null>(null);
  const [addingTask, setAddingTask] = useState(false);
  const [localTasks, setLocalTasks] = useState<TaskDefinition[] | null>(null);
  const [localCron, setLocalCron] = useState<string | undefined>(undefined);
  const [localTz, setLocalTz] = useState('UTC');
  const [localMaxRuns, setLocalMaxRuns] = useState(1);
  const [draftDirty, setDraftDirty] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // ── Queries ───────────────────────────────────────────────────────────────

  const { data: job, isLoading, isError } = useQuery<Job>({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJob(jobId!),
    enabled: !!jobId,
  });

  const { data: runs = [] } = useQuery<JobRun[]>({
    queryKey: ['job-runs', jobId],
    queryFn: () => jobsApi.listRuns(jobId!),
    enabled: !!jobId && activeTab === 'runs',
    refetchInterval: (q) => {
      const anyLive = q.state.data?.some((r: { state: string }) => r.state === 'running' || r.state === 'queued');
      return anyLive ? 2000 : false;
    },
  });

  const sortedRuns = useMemo(() => {
    const list = [...runs];
    const getRunTime = (r: JobRun) => {
      if (r.started_at) return new Date(r.started_at).getTime();
      if ((r as any).created_at) return new Date((r as any).created_at).getTime();
      return Date.now();
    };
    list.sort((a, b) => getRunTime(b) - getRunTime(a));
    return list;
  }, [runs]);

  const { data: publishStatus } = useQuery({
    queryKey: ['job-publish-status', jobId],
    queryFn: () => jobsApi.getPublishStatus(jobId!),
    enabled: !!jobId && !!job?.current_version,
    refetchInterval: (query) => query.state.data?.state === 'publishing' ? 3000 : false,
  });

  useEffect(() => {
    if (!job || localTasks !== null) return;
    setLocalTasks(job.task_definitions ?? []);
    setLocalCron(job.schedule_cron ?? undefined);
    setLocalTz(job.timezone ?? 'UTC');
    setLocalMaxRuns(job.max_active_runs ?? 1);
  }, [job, localTasks]);

  const tasks = localTasks ?? job?.task_definitions ?? [];

  // ── Mutations ─────────────────────────────────────────────────────────────

  const updateMut = useMutation({
    mutationFn: (body: { name?: string; description?: string }) => jobsApi.updateJob(jobId!, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['job', jobId] }); toast.success('Job updated.'); setEditJobOpen(false); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const runMut = useMutation({
    mutationFn: () => jobsApi.triggerRun(jobId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', jobId] });
      qc.invalidateQueries({ queryKey: ['job-runs', jobId] });
      toast.success('Run started.');
      setConfirmRun(false);
    },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmRun(false); },
  });

  const pauseMut = useMutation({
    mutationFn: () => job?.status === 'paused' ? jobsApi.resumeJob(jobId!) : jobsApi.pauseJob(jobId!),
    onSuccess: (j) => { qc.invalidateQueries({ queryKey: ['job', jobId] }); toast.info(j.status === 'paused' ? 'Job paused.' : 'Job resumed.'); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const archiveMut = useMutation({
    mutationFn: () => jobsApi.archiveJob(jobId!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); toast.info('Job archived.'); navigate('/jobs'); },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmArchive(false); },
  });

  const deleteMut = useMutation({
    mutationFn: () => jobsApi.deleteJob(jobId!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); toast.success('Job deleted.'); navigate('/jobs'); },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmDelete(false); },
  });

  const publishMut = useMutation({
    mutationFn: () => jobsApi.publishJob(jobId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', jobId] });
      qc.invalidateQueries({ queryKey: ['job-publish-status', jobId] });
      toast.success('Job published. Waiting for scheduler registration.');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  // ── Draft save ────────────────────────────────────────────────────────────

  const handleSaveDraft = useCallback(async (tasksOverride?: TaskDefinition[]) => {
    if (!jobId) return;
    setSavingDraft(true);
    try {
      await jobsApi.saveDraft(jobId, {
        schedule_cron: localCron,
        timezone: localTz,
        max_active_runs: localMaxRuns,
        retry_policy: { retries: 0, retry_delay_seconds: 300, backoff_factor: 1.0 },
        task_definitions: tasksOverride ?? tasks,
      });
      qc.invalidateQueries({ queryKey: ['job', jobId] });
      toast.success('Draft saved.');
      setDraftDirty(false);
    } catch (err) {
      toast.error(extractApiError(err));
    } finally {
      setSavingDraft(false);
    }
  }, [jobId, localCron, localTz, localMaxRuns, tasks, qc, toast]);

  // ── Task editor callbacks ─────────────────────────────────────────────────

  const handleTaskSave = useCallback((task: TaskDefinition) => {
    const next = editingTaskKey
      ? tasks.map((t) => t.task_key === editingTaskKey ? task : t)
      : [...tasks, task];
    setLocalTasks(next);
    setEditingTaskKey(null);
    setAddingTask(false);
    setDraftDirty(true);
    handleSaveDraft(next);
  }, [editingTaskKey, tasks, handleSaveDraft]);

  const handleTaskDelete = useCallback((taskKey: string) => {
    const next = tasks.filter((t) => t.task_key !== taskKey);
    setLocalTasks(next);
    setEditingTaskKey(null);
    setDraftDirty(true);
    handleSaveDraft(next);
  }, [tasks, handleSaveDraft]);

  const handleTaskClick = useCallback((key: string) => {
    setAddingTask(false);
    setEditingTaskKey(key);
  }, []);

  const handleAddTask = useCallback(() => {
    setEditingTaskKey(null);
    setAddingTask(true);
  }, []);

  const handleTaskConnect = useCallback((sourceKey: string, targetKey: string) => {
    if (sourceKey === targetKey) return;
    const next = tasks.map((t) => {
      if (t.task_key === targetKey) {
        const deps = t.depends_on ?? [];
        if (!deps.includes(sourceKey)) {
          return { ...t, depends_on: [...deps, sourceKey] };
        }
      }
      return t;
    });
    setLocalTasks(next);
    setDraftDirty(true);
    handleSaveDraft(next);
  }, [tasks, handleSaveDraft]);

  // ── Schedule change ───────────────────────────────────────────────────────

  const handleScheduleChange = useCallback((cron: string | undefined, tz: string) => {
    setLocalCron(cron);
    setLocalTz(tz);
    setDraftDirty(true);
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return <div style={{ padding: '2rem 1.5rem', color: 'var(--color-text-muted)' }}>Loading job…</div>;
  }
  if (isError || !job) {
    return <div style={{ padding: '2rem 1.5rem', color: 'var(--color-danger)' }}>Job not found.</div>;
  }

  const editingTask = editingTaskKey ? tasks.find((t) => t.task_key === editingTaskKey) : undefined;
  const showDrawer = addingTask || !!editingTaskKey;
  const schedulerActive = publishStatus?.state === 'active' || job.publish_state === 'active';

  return (
    <div
      className="job-detail-shell"
      style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}
      onClick={() => setOverflowOpen(false)}
    >
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.625rem 1.5rem 0', fontSize: '0.8rem' }}>
        <button className="jd-bc-link" onClick={() => navigate('/jobs')}>Jobs</button>
      </div>

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        padding: '0.5rem 1.5rem 0', gap: 12, flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>{job.name}</h1>
            <StatusPill state={job.status} size="sm" />
            {job.has_unpublished_changes && (
              <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#d97706', display: 'flex', alignItems: 'center', gap: 4 }}>
                <AlertCircle size={12} /> Unpublished changes
              </span>
            )}
            {!job.has_unpublished_changes && job.current_version && !schedulerActive && (
              <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#2563eb' }}>
                Publishing...
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Run now */}
          {job.status !== 'archived' && (
            <button
              className="btn btn-primary"
              onClick={() => setConfirmRun(true)}
              disabled={!job.current_version || !schedulerActive}
              title={!job.current_version
                ? 'Publish the job first to run it'
                : !schedulerActive
                  ? 'Waiting for scheduler registration'
                  : 'Run now'}
            >
              <Play size={14} /> Run now
            </button>
          )}

          {/* Vertical Three Dots Menu */}
          <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
            <button className="btn-icon" title="More options" onClick={(e) => { e.stopPropagation(); setOverflowOpen(!overflowOpen); }}>
              <MoreVertical size={16} />
            </button>
            {overflowOpen && (
              <div className="jd-dropdown" style={{ right: 0, minWidth: 170 }}>
                {/* Save draft */}
                {draftDirty && (
                  <button
                    className="jd-dropdown-item"
                    onClick={() => { setOverflowOpen(false); handleSaveDraft(); }}
                    disabled={savingDraft}
                  >
                    <Save size={14} /> {savingDraft ? 'Saving draft…' : 'Save draft'}
                  </button>
                )}

                {/* Publish */}
                {job.has_unpublished_changes && (
                  <button
                    className="jd-dropdown-item"
                    onClick={() => { setOverflowOpen(false); publishMut.mutate(); }}
                    disabled={publishMut.isPending}
                  >
                    <Upload size={14} /> {publishMut.isPending ? 'Publishing…' : 'Publish'}
                  </button>
                )}

                {/* Pause/Resume */}
                {job.status !== 'archived' && (
                  <button
                    className="jd-dropdown-item"
                    onClick={() => { setOverflowOpen(false); pauseMut.mutate(); }}
                    disabled={pauseMut.isPending}
                  >
                    {job.status === 'paused'
                      ? <><RotateCcw size={14} /> Resume job</>
                      : <><Pause size={14} /> Pause job</>}
                  </button>
                )}

                {/* Edit */}
                <button
                  className="jd-dropdown-item"
                  onClick={() => { setOverflowOpen(false); setEditJobOpen(true); }}
                >
                  <Pencil size={14} /> Edit details
                </button>

                {/* Archive */}
                {job.status !== 'archived' && (
                  <button
                    className="jd-dropdown-item"
                    onClick={() => { setOverflowOpen(false); setConfirmArchive(true); }}
                  >
                    <Archive size={14} /> Archive job
                  </button>
                )}

                {/* Delete */}
                <button
                  className="jd-dropdown-item"
                  style={{ color: 'var(--color-danger)' }}
                  onClick={() => { setOverflowOpen(false); setConfirmDelete(true); }}
                >
                  <Trash2 size={14} /> Delete job
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, padding: '0.625rem 1.5rem 0', borderBottom: '1px solid var(--color-border)' }}>
        {([
          ['runs',        'Runs'],
          ['tasks',       'Tasks'],
          ['schedule',    'Schedule'],
          ['permissions', 'Permissions'],
        ] as [Tab, string][]).map(([id, label]) => (
          <button
            key={id}
            className={`jd-tab ${activeTab === id ? 'jd-tab-active' : ''}`}
            onClick={() => handleTabChange(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab body */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', minHeight: 0, position: 'relative' }}>

        {/* ── Tasks tab ─────────────────────────────────────────────────── */}
        {activeTab === 'tasks' && (
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 350, height: '100%', width: '100%', position: 'relative' }}>
            {/* Graph toolbar */}
            <div style={{
              position: 'absolute', top: 10, left: 16, zIndex: 10,
              display: 'flex', gap: 6,
            }}>
              <button
                className="btn btn-secondary"
                style={{ padding: '5px 12px', fontSize: '0.78rem' }}
                onClick={handleAddTask}
              >
                <Plus size={13} /> Add task
              </button>
            </div>

            <div style={{ flex: 1, display: 'flex', overflow: 'hidden', height: '100%', width: '100%' }}>
              <TaskGraphCanvas
                tasks={tasks}
                isEditor={true}
                onTaskClick={handleTaskClick}
                onAddTask={handleAddTask}
              />

              {/* Task drawer (slides in from right) */}
              {showDrawer && (
                <div style={{ width: 300, flexShrink: 0, borderLeft: '1px solid var(--color-border)', overflow: 'hidden' }}>
                  <TaskDrawer
                    key={editingTaskKey ?? 'new_task'}
                    task={editingTask}
                    allTaskKeys={tasks.map((t) => t.task_key)}
                    onSave={handleTaskSave}
                    onCancel={() => { setEditingTaskKey(null); setAddingTask(false); }}
                    onDelete={editingTaskKey ? () => handleTaskDelete(editingTaskKey) : undefined}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Runs tab ──────────────────────────────────────────────────── */}
        {activeTab === 'runs' && (
          <div style={{ flex: 1, overflow: 'auto', padding: '1rem 1.5rem' }}>
            {runs.length === 0 ? (
              <div className="table-empty" style={{ paddingTop: '3rem' }}>
                <Play size={36} style={{ opacity: 0.2, marginBottom: 8 }} />
                <div style={{ fontWeight: 600 }}>No runs yet</div>
                <div style={{ color: 'var(--color-text-subtle)', marginTop: 4, fontSize: '0.875rem' }}>
                  Click <strong>Run now</strong> to trigger the first run.
                </div>
              </div>
            ) : (
              <>
                <JobRunsTimelineChart
                  runs={runs}
                  tasks={tasks}
                  onRunClick={(runId) => navigate(`/jobs/${jobId}/runs/${runId}`)}
                />

                <table className="admin-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Status</th>
                    <th>Trigger</th>
                    <th>Started</th>
                    <th>Duration</th>
                    <th>Tasks</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRuns.map((run) => (
                    <tr
                      key={run.job_run_id}
                      className="table-row-clickable"
                      style={run.state === 'running' ? { background: 'rgba(59,130,246,0.08)' } : undefined}
                      onClick={() => navigate(`/jobs/${jobId}/runs/${run.job_run_id}`)}
                    >
                      <td>
                        <code style={{ fontSize: '0.75rem' }}>{run.job_run_id.slice(0, 8)}…</code>
                      </td>
                      <td><StatusPill state={run.state} size="sm" /></td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', textTransform: 'capitalize' }}>
                        {run.trigger_type}
                        {run.triggered_by && <span style={{ marginLeft: 4 }}>by {run.triggered_by}</span>}
                      </td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                        {relativeTime(run.started_at)}
                      </td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                        {formatDuration(run.duration_seconds)}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="badge-count">{run.task_runs.length}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </>
            )}
          </div>
        )}

        {/* ── Schedule tab ──────────────────────────────────────────────── */}
        {activeTab === 'schedule' && (
          <div style={{ flex: 1, overflow: 'auto', padding: '1.25rem 1.5rem', maxWidth: 800 }}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 2 }}>Schedule configuration</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                {job.schedule_cron
                  ? <>Currently running: <strong>{cronToHuman(job.schedule_cron)}</strong></>
                  : 'No active schedule — job runs manually only.'}
              </div>
            </div>

            <div style={{ background: 'var(--color-surface)', borderRadius: 8, border: '1px solid var(--color-border)', padding: '1.25rem' }}>
              <ScheduleBuilder
                value={localCron}
                timezone={localTz}
                onChange={handleScheduleChange}
              />

              <div style={{ marginTop: 14, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleSaveDraft()}
                  disabled={savingDraft}
                >
                  <Save size={14} /> {savingDraft ? 'Saving…' : 'Save draft'}
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => { handleSaveDraft().then(() => publishMut.mutate()); }}
                  disabled={publishMut.isPending || savingDraft}
                >
                  <Upload size={14} /> Save & publish
                </button>
              </div>
            </div>

            {/* Advanced */}
            <div style={{ marginTop: 16, background: 'var(--color-surface)', borderRadius: 8, border: '1px solid var(--color-border)', padding: '1.25rem' }}>
              <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: 12 }}>Advanced settings</div>
              <div className="form-field">
                <label className="form-label">Max concurrent runs</label>
                <input
                  type="number" className="form-input" min={1} max={10}
                  style={{ width: 100 }}
                  value={localMaxRuns}
                  onChange={(e) => { setLocalMaxRuns(parseInt(e.target.value) || 1); setDraftDirty(true); }}
                />
                <span className="form-hint">Maximum number of runs that can be active at the same time.</span>
              </div>
            </div>
          </div>
        )}

        {/* ── Permissions tab ───────────────────────────────────────────── */}
        {activeTab === 'permissions' && (
          <div style={{ flex: 1, overflow: 'auto', padding: '1.25rem 1.5rem', maxWidth: 800 }}>
            <div style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 8, padding: '1.25rem',
            }}>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 6 }}>Job owner</div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: 12 }}>
                {job.owner_user_id ?? 'Not assigned'}
              </div>
              <div style={{
                padding: '0.75rem', borderRadius: 6,
                background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)',
                fontSize: '0.8rem', color: '#92400e',
              }}>
                Fine-grained job permissions (per-user, per-group) will be available in a future release.
                Currently the job is accessible to all members of the workspace.
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Modals ──────────────────────────────────────────────────────── */}

      {editJobOpen && (
        <JobFormModal
          job={job}
          onSave={async (data) => { await updateMut.mutateAsync(data); }}
          onCancel={() => setEditJobOpen(false)}
        />
      )}

      {confirmRun && (
        <ConfirmActionModal
          title="Run this job now?"
          message={`A manual run of '${job.name}' will be triggered immediately using the published version.`}
          confirmLabel="Run now"
          variant="info"
          isLoading={runMut.isPending}
          onConfirm={() => runMut.mutate()}
          onCancel={() => setConfirmRun(false)}
        />
      )}

      {confirmArchive && (
        <ConfirmActionModal
          title="Archive this job?"
          message={`'${job.name}' will be paused. Scheduled runs will stop. All history is preserved.`}
          confirmLabel="Archive"
          variant="warning"
          isLoading={archiveMut.isPending}
          onConfirm={() => archiveMut.mutate()}
          onCancel={() => setConfirmArchive(false)}
        />
      )}

      {confirmDelete && (
        <ConfirmActionModal
          title="Delete this job?"
          message={`'${job.name}' and all its run history will be permanently deleted. This cannot be undone.`}
          confirmLabel="Delete permanently"
          variant="danger"
          isLoading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate()}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}


