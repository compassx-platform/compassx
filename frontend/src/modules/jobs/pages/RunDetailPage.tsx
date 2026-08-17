import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight, RotateCcw, XCircle, Clock, User, RefreshCw, ExternalLink,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as jobsApi from '../lib/jobsApi';
import { formatDuration, relativeTime } from '../lib/cronUtils';
import type { TaskRun } from '../lib/jobsTypes';
import StatusPill from '../components/StatusPill';
import ConfirmActionModal from '../components/ConfirmActionModal';
import TaskGraphCanvas from '../components/TaskGraphCanvas';

type ViewMode = 'list' | 'graph';

export default function RunDetailPage() {
  const { jobId, runId } = useParams<{ jobId: string; runId: string }>();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useScopedNavigate();

  const [selectedTask, setSelectedTask] = useState<TaskRun | null>(null);
  const [view, setView] = useState<ViewMode>('graph');
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [confirmRerun, setConfirmRerun] = useState(false);

  const { data: run, isLoading } = useQuery({
    queryKey: ['job-run', runId],
    queryFn: () => jobsApi.getRun(runId!),
    enabled: !!runId,
    refetchInterval: (q) => {
      const state = q.state.data?.state;
      return state === 'running' || state === 'queued' ? 4000 : false;
    },
  });

  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJob(jobId!),
    enabled: !!jobId,
  });

  const cancelMut = useMutation({
    mutationFn: () => jobsApi.cancelRun(runId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-run', runId] });
      toast.info('Run cancelled.');
      setConfirmCancel(false);
    },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmCancel(false); },
  });

  const rerunMut = useMutation({
    mutationFn: () => jobsApi.rerun(runId!),
    onSuccess: (newRun) => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast.success('New run started.');
      setConfirmRerun(false);
      navigate(`/jobs/${jobId}/runs/${newRun.job_run_id}`);
    },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmRerun(false); },
  });

  const retryMut = useMutation({
    mutationFn: (taskKey: string) => jobsApi.retryTask(runId!, taskKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-run', runId] });
      toast.success('Task retry queued.');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  if (isLoading) {
    return (
      <div style={{ padding: '2rem 1.5rem', color: 'var(--color-text-muted)' }}>Loading run…</div>
    );
  }

  if (!run) {
    return <div style={{ padding: '2rem 1.5rem', color: 'var(--color-danger)' }}>Run not found.</div>;
  }

  const isLive = run.state === 'running' || run.state === 'queued';
  const isTerminal = ['success', 'failed', 'cancelled'].includes(run.state);
  const taskDefs = job?.task_definitions ?? [];

  return (
    <div className="job-detail-shell" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Breadcrumb */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '0.625rem 1.5rem 0', fontSize: '0.8rem',
      }}>
        <button className="jd-bc-link" onClick={() => navigate('/jobs')}>
          Jobs
        </button>
        <ChevronRight size={12} style={{ color: 'var(--color-text-subtle)' }} />
        <button className="jd-bc-link" onClick={() => navigate(`/jobs/${jobId}`)}>
          {job?.name ?? jobId}
        </button>
        <ChevronRight size={12} style={{ color: 'var(--color-text-subtle)' }} />
        <span style={{ color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: '0.75rem' }}>
          Run {run.job_run_id.slice(0, 8)}…
        </span>
      </div>

      {/* Title bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0.5rem 1.5rem', gap: 12, flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <StatusPill state={run.state} size="lg" />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
              Started {relativeTime(run.started_at)}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', display: 'flex', gap: 12, marginTop: 2 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={11} />
                {formatDuration(run.duration_seconds)}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {run.trigger_type === 'manual' || run.trigger_type === 'rerun'
                  ? <User size={11} /> : <Clock size={11} />}
                {run.trigger_type}
                {run.triggered_by ? ` by ${run.triggered_by}` : ''}
              </span>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {isTerminal && (
            <button
              className="btn btn-secondary"
              onClick={() => setConfirmRerun(true)}
            >
              <RefreshCw size={14} /> Rerun job
            </button>
          )}
          {isLive && (
            <button
              className="btn"
              style={{ background: 'var(--color-danger)', color: '#fff' }}
              onClick={() => setConfirmCancel(true)}
            >
              <XCircle size={14} /> Cancel run
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, padding: '0.625rem 1.5rem 0', borderBottom: '1px solid var(--color-border)' }}>
        {(['graph', 'list'] as ViewMode[]).map((v) => (
          <button
            key={v}
            className={`jd-tab ${view === v ? 'jd-tab-active' : ''}`}
            onClick={() => setView(v)}
          >
            {v === 'graph' ? 'Graph' : 'List'}
          </button>
        ))}
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', minHeight: 0 }}>
        {view === 'graph' ? (
          <div style={{ flex: 1, display: 'flex', padding: '0.5rem 1.5rem 1.25rem' }}>
            <TaskGraphCanvas
              tasks={taskDefs}
              taskRuns={run.task_runs}
              isEditor={false}
            />
          </div>
        ) : (
          /* Table list view */
          <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.5rem' }}>
            {run.task_runs.length === 0 ? (
              <div className="table-empty">No tasks recorded for this run.</div>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Ended</th>
                    <th>Duration</th>
                    <th>Execution Ref</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {run.task_runs.map((tr) => (
                    <tr
                      key={tr.task_run_id}
                      style={
                        tr.state === 'running'
                          ? { background: 'rgba(59,130,246,0.08)' }
                          : undefined
                      }
                    >
                      <td>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text)' }}>
                          {tr.task_key}
                          {tr.try_number > 1 && (
                            <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginLeft: 6 }}>
                              (Attempt {tr.try_number})
                            </span>
                          )}
                        </div>
                      </td>
                      <td><StatusPill state={tr.state} size="sm" /></td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                        {relativeTime(tr.started_at)}
                      </td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                        {relativeTime(tr.ended_at)}
                      </td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                        {formatDuration(tr.duration_seconds)}
                      </td>
                      <td>
                        {tr.execution_ref ? (
                          <code style={{ fontSize: '0.75rem', color: 'var(--color-primary)' }}>
                            {tr.execution_ref}
                          </code>
                        ) : (
                          <span style={{ color: 'var(--color-text-subtle)' }}>—</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {(tr.state === 'failed' || tr.state === 'upstream_failed') && (
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => retryMut.mutate(tr.task_key)}
                            disabled={retryMut.isPending}
                          >
                            <RotateCcw size={11} /> Retry task
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Confirm cancel */}
      {confirmCancel && (
        <ConfirmActionModal
          title="Cancel this run?"
          message="All running and queued tasks will be stopped."
          confirmLabel="Cancel run"
          variant="warning"
          isLoading={cancelMut.isPending}
          onConfirm={() => cancelMut.mutate()}
          onCancel={() => setConfirmCancel(false)}
        />
      )}

      {/* Confirm rerun */}
      {confirmRerun && (
        <ConfirmActionModal
          title="Rerun this job?"
          message="Starts a new run of the full job using the current published version."
          confirmLabel="Rerun job"
          variant="info"
          isLoading={rerunMut.isPending}
          onConfirm={() => rerunMut.mutate()}
          onCancel={() => setConfirmRerun(false)}
        />
      )}
    </div>
  );
}

function TaskDetail({ tr, onRetry, retrying }: { tr: TaskRun; onRetry: () => void; retrying: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div style={{ fontSize: '1rem', fontWeight: 700 }}>{tr.task_key}</div>
        {tr.try_number > 1 && (
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
            Attempt {tr.try_number}
          </div>
        )}
      </div>

      <StatusPill state={tr.state} size="lg" />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[
          ['Started', tr.started_at ? new Date(tr.started_at).toLocaleString() : '—'],
          ['Ended', tr.ended_at ? new Date(tr.ended_at).toLocaleString() : '—'],
          ['Duration', formatDuration(tr.duration_seconds)],
          ['Try number', String(tr.try_number)],
        ].map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: '0.8125rem' }}>
            <span style={{ color: 'var(--color-text-muted)' }}>{k}</span>
            <span style={{ fontWeight: 500 }}>{v}</span>
          </div>
        ))}
      </div>

      {tr.execution_ref && (
        <div>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            Execution
          </div>
          <a
            href={`#execution/${tr.execution_ref}`}
            style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-primary)', fontSize: '0.8125rem' }}
          >
            <ExternalLink size={13} />
            View execution logs
          </a>
        </div>
      )}

      {(tr.state === 'failed' || tr.state === 'upstream_failed') && (
        <button
          className="btn btn-secondary"
          onClick={onRetry}
          disabled={retrying}
          style={{ alignSelf: 'flex-start', marginTop: 8 }}
        >
          <RotateCcw size={14} /> {retrying ? 'Retrying…' : 'Retry this task'}
        </button>
      )}
    </div>
  );
}
