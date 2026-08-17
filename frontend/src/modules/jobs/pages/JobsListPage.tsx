import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase, Plus, Search, Play, Pause, RotateCcw,
  MoreHorizontal, Archive, Trash2, Clock, ChevronRight,
} from 'lucide-react';
import { useScopedPath } from '@/lib/appNavigation';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as jobsApi from '../lib/jobsApi';
import { cronToHuman, relativeTime, formatDuration } from '../lib/cronUtils';
import type { Job } from '../lib/jobsTypes';
import StatusPill from '../components/StatusPill';
import JobFormModal from '../components/JobFormModal';
import ConfirmActionModal from '../components/ConfirmActionModal';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'archived', label: 'Archived' },
];

export default function JobsListPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const scopedPath = useScopedPath();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [overflowOpen, setOverflowOpen] = useState<string | null>(null);
  const [confirmArchive, setConfirmArchive] = useState<Job | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Job | null>(null);

  const { data: jobs = [], isLoading, isError } = useQuery<Job[]>({
    queryKey: ['jobs', search, statusFilter],
    queryFn: () => jobsApi.listJobs({ search: search || undefined, status: statusFilter || undefined }),
    refetchInterval: 15_000,
  });

  const createMut = useMutation({
    mutationFn: (body: { name: string; description?: string }) => jobsApi.createJob(body),
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast.success(`Job '${job.name}' created.`);
      setShowCreate(false);
      navigate(scopedPath(`/jobs/${job.job_id}`));
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const runMut = useMutation({
    mutationFn: (jobId: string) => jobsApi.triggerRun(jobId),
    onSuccess: (_, jobId) => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      const j = jobs.find((j) => j.job_id === jobId);
      toast.success(`Run started for '${j?.name ?? 'job'}'.`);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const pauseMut = useMutation({
    mutationFn: (jobId: string) => jobsApi.pauseJob(jobId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); toast.info('Job paused.'); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const resumeMut = useMutation({
    mutationFn: (jobId: string) => jobsApi.resumeJob(jobId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); toast.info('Job resumed.'); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const archiveMut = useMutation({
    mutationFn: (jobId: string) => jobsApi.archiveJob(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast.info('Job archived. Scheduled runs have stopped.');
      setConfirmArchive(null);
    },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmArchive(null); },
  });

  const deleteMut = useMutation({
    mutationFn: (jobId: string) => jobsApi.deleteJob(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] });
      toast.success('Job deleted.');
      setConfirmDelete(null);
    },
    onError: (err) => { toast.error(extractApiError(err)); setConfirmDelete(null); },
  });

  const closeOverflow = useCallback(() => setOverflowOpen(null), []);

  return (
    <div className="jobs-list-page" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
      onClick={closeOverflow}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '1rem 1.5rem 0.75rem', flexWrap: 'wrap', gap: 12,
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Briefcase size={20} style={{ color: 'var(--color-primary)' }} />
            <h1 className="page-title" style={{ margin: 0 }}>Jobs</h1>
          </div>
          <p className="page-subtitle" style={{ marginTop: 2 }}>
            Schedule notebooks, queries, and dashboards to run automatically.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={15} /> Create job
        </button>
      </div>

      {/* Filter bar */}
      <div style={{
        display: 'flex', gap: 10, padding: '0 1.5rem 0.875rem',
        flexWrap: 'wrap', alignItems: 'center',
      }}>
        <div className="search-bar-wrapper" style={{ maxWidth: 280 }}>
          <Search size={14} className="search-icon" />
          <input
            className="search-input"
            placeholder="Search jobs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="form-input"
          style={{ width: 150 }}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 1.5rem 1.5rem' }}>
        {isLoading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            Loading jobs…
          </div>
        ) : isError ? (
          <div className="table-empty error">Failed to load jobs. Check your connection.</div>
        ) : jobs.length === 0 ? (
          <div className="table-empty" style={{ paddingTop: '4rem' }}>
            <Briefcase size={40} style={{ opacity: 0.25, marginBottom: 8 }} />
            <div style={{ fontWeight: 600, fontSize: '1rem' }}>No jobs yet</div>
            <div style={{ color: 'var(--color-text-subtle)', marginTop: 4, maxWidth: 360, textAlign: 'center' }}>
              Jobs let you schedule notebooks, queries, and dashboards to run automatically.
            </div>
            <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => setShowCreate(true)}>
              <Plus size={15} /> Create job
            </button>
          </div>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Schedule</th>
                  <th>Last run</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'center' }}>Last 5 Runs</th>
                  <th>Duration</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <JobRow
                    key={job.job_id}
                    job={job}
                    overflowOpen={overflowOpen === job.job_id}
                    onRowClick={() => navigate(scopedPath(`/jobs/${job.job_id}`))}
                    onRunClick={(e) => { e.stopPropagation(); runMut.mutate(job.job_id); }}
                    onPauseClick={(e) => {
                      e.stopPropagation();
                      job.status === 'paused' ? resumeMut.mutate(job.job_id) : pauseMut.mutate(job.job_id);
                    }}
                    onOverflowToggle={(e) => {
                      e.stopPropagation();
                      setOverflowOpen(overflowOpen === job.job_id ? null : job.job_id);
                    }}
                    onArchive={() => { setOverflowOpen(null); setConfirmArchive(job); }}
                    onDelete={() => { setOverflowOpen(null); setConfirmDelete(job); }}
                    scopedPath={scopedPath}
                    navigate={navigate}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      {showCreate && (
        <JobFormModal
          onSave={async (data) => { await createMut.mutateAsync(data); }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {confirmArchive && (
        <ConfirmActionModal
          title="Archive this job?"
          message={`'${confirmArchive.name}' will be paused. Scheduled runs will stop. Run history is preserved.`}
          confirmLabel="Archive"
          variant="warning"
          isLoading={archiveMut.isPending}
          onConfirm={() => archiveMut.mutate(confirmArchive.job_id)}
          onCancel={() => setConfirmArchive(null)}
        />
      )}

      {confirmDelete && (
        <ConfirmActionModal
          title="Delete this job?"
          message={`'${confirmDelete.name}' and all its run history will be permanently deleted. This cannot be undone.`}
          confirmLabel="Delete permanently"
          variant="danger"
          isLoading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate(confirmDelete.job_id)}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

// ── Row component ───────────────────────────────────────────────────────────────

function JobRow({
  job, overflowOpen,
  onRowClick, onRunClick, onPauseClick, onOverflowToggle,
  onArchive, onDelete, scopedPath, navigate,
}: {
  job: Job;
  overflowOpen: boolean;
  onRowClick: () => void;
  onRunClick: (e: React.MouseEvent) => void;
  onPauseClick: (e: React.MouseEvent) => void;
  onOverflowToggle: (e: React.MouseEvent) => void;
  onArchive: () => void;
  onDelete: () => void;
  scopedPath: (path: string) => string;
  navigate: (to: string) => void;
}) {
  return (
    <tr
      className="table-row-clickable"
      style={job.last_run_state === 'running' ? { background: 'rgba(59,130,246,0.08)' } : undefined}
      onClick={onRowClick}
    >
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text)' }}>
              {job.name}
            </div>
            {job.has_unpublished_changes && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                fontSize: '0.68rem', fontWeight: 600, color: '#d97706', marginTop: 2,
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#d97706' }} />
                Unpublished changes
              </span>
            )}
          </div>
        </div>
      </td>
      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Clock size={12} />
          {cronToHuman(job.schedule_cron)}
        </div>
      </td>
      <td>
        {job.last_run_state ? (
          <button
            className="btn-icon"
            style={{ all: 'unset', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
            onClick={(e) => {
              e.stopPropagation();
              if (job.last_run_id) navigate(scopedPath(`/jobs/${job.job_id}/runs/${job.last_run_id}`));
            }}
          >
            <StatusPill state={job.last_run_state} size="sm" />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              {relativeTime(job.last_run_started_at)}
            </span>
          </button>
        ) : (
          <span style={{ color: 'var(--color-text-subtle)', fontSize: '0.8rem' }}>—</span>
        )}
      </td>
      <td><StatusPill state={job.status} size="sm" /></td>
      <td style={{ textAlign: 'center' }}>
        {job.recent_runs && job.recent_runs.length > 0 ? (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'nowrap' }}>
            {job.recent_runs.map((r) => (
              <button
                key={r.job_run_id}
                style={{ all: 'unset', cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
                title={`Run ${r.job_run_id.slice(0, 8)} (${r.state}) - ${relativeTime(r.started_at)}`}
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(scopedPath(`/jobs/${job.job_id}/runs/${r.job_run_id}`));
                }}
              >
                <StatusPill state={r.state} size="sm" iconOnly />
              </button>
            ))}
          </div>
        ) : (
          <span style={{ color: 'var(--color-text-subtle)', fontSize: '0.8rem' }}>No runs</span>
        )}
      </td>
      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
        {job.last_run_state ? '—' : '—'}
      </td>
      <td onClick={(e) => e.stopPropagation()}>
        <div className="row-actions">
          {/* Run now */}
          {job.status !== 'archived' && (
            <button
              className="btn-icon"
              title="Run now"
              onClick={onRunClick}
              disabled={!job.current_version}
            >
              <Play size={14} />
            </button>
          )}
          {/* Pause/Resume */}
          {job.status !== 'archived' && (
            <button
              className="btn-icon"
              title={job.status === 'paused' ? 'Resume' : 'Pause'}
              onClick={onPauseClick}
            >
              {job.status === 'paused'
                ? <RotateCcw size={14} />
                : <Pause size={14} />}
            </button>
          )}
          {/* Overflow */}
          <div style={{ position: 'relative' }}>
            <button className="btn-icon" title="More actions" onClick={onOverflowToggle}>
              <MoreHorizontal size={15} />
            </button>
            {overflowOpen && (
              <div className="jd-dropdown" style={{ right: 0, minWidth: 160 }}>
                <button className="jd-dropdown-item" onClick={onArchive}>
                  <Archive size={14} /> Archive
                </button>
                <button
                  className="jd-dropdown-item"
                  style={{ color: 'var(--color-danger)' }}
                  onClick={onDelete}
                >
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}


