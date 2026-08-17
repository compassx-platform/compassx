/**
 * Job Config Detail Page — /ingestion/job-configs/:jobConfigId
 * Full config editor, enable/disable toggle, trigger run, run history.
 */
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Settings, Play, Power, PowerOff, RotateCcw,
  Trash2, Save, Loader2, AlertCircle, ChevronRight, Clock,
  CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as api from '../lib/ingestionApi';
import type { JobConfig, JobConfigUpdate, IngestionRun, Connection, PaginationType, ParamSourceType } from '../lib/ingestionTypes';

const STATUS_ICON = {
  running: <Loader2 size={13} className="ing-spin" />,
  succeeded: <CheckCircle2 size={13} />,
  failed: <XCircle size={13} />,
  partial: <AlertTriangle size={13} />,
};

const STATUS_CLASS = {
  running: 'ing-badge-info',
  succeeded: 'ing-badge-success',
  failed: 'ing-badge-danger',
  partial: 'ing-badge-warning',
};

function relTime(iso?: string) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export default function JobConfigDetailPage() {
  const { jobConfigId } = useParams<{ jobConfigId: string }>();
  const workspace = useWorkspaceContext();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useScopedNavigate();

  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState<JobConfigUpdate>({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const { data: cfg, isLoading, isError } = useQuery<JobConfig>({
    queryKey: ['ingestion-job-config', workspace.id, jobConfigId],
    queryFn: () => api.getJobConfig(workspace.id, jobConfigId!),
    enabled: !!jobConfigId,
    refetchInterval: editMode ? false : 10_000,
  });

  const { data: runs = [] } = useQuery<IngestionRun[]>({
    queryKey: ['ingestion-runs', workspace.id, jobConfigId],
    queryFn: () => api.listRuns(workspace.id, jobConfigId!, 20),
    enabled: !!jobConfigId,
    refetchInterval: 10_000,
  });

  const { data: connections = [] } = useQuery<Connection[]>({
    queryKey: ['ingestion-connections', workspace.id],
    queryFn: () => api.listConnections(workspace.id),
  });

  useEffect(() => {
    if (cfg && editMode) setEditForm({ ...cfg });
  }, [cfg, editMode]);

  const updateMut = useMutation({
    mutationFn: (body: JobConfigUpdate) =>
      api.updateJobConfig(workspace.id, jobConfigId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-job-config', workspace.id, jobConfigId] });
      qc.invalidateQueries({ queryKey: ['ingestion-job-configs', workspace.id] });
      toast.success('Job config updated.');
      setEditMode(false);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const enableMut = useMutation({
    mutationFn: () => api.enableJobConfig(workspace.id, jobConfigId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-job-config', workspace.id, jobConfigId] });
      toast.success('Job config enabled.');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const disableMut = useMutation({
    mutationFn: () => api.disableJobConfig(workspace.id, jobConfigId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-job-config', workspace.id, jobConfigId] });
      toast.info('Job config disabled.');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const triggerMut = useMutation({
    mutationFn: () => api.triggerRun(workspace.id, jobConfigId!),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['ingestion-runs', workspace.id, jobConfigId] });
      toast.success(`Run started. ID: ${res.run_id.slice(0, 8)}…`);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const deleteMut = useMutation({
    mutationFn: () => api.deleteJobConfig(workspace.id, jobConfigId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-job-configs', workspace.id] });
      toast.success('Job config deleted.');
      navigate('/ingestion/job-configs');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const resetMut = useMutation({
    mutationFn: () => api.resetWatermark(workspace.id, jobConfigId!),
    onSuccess: () => {
      toast.success('Watermark reset. Next run will re-fetch all data.');
      setShowResetConfirm(false);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  if (isLoading) return (
    <div className="ing-page ing-loading"><Loader2 size={20} className="ing-spin" /> Loading…</div>
  );
  if (isError || !cfg) return (
    <div className="ing-page ing-error"><AlertCircle size={16} /> Job config not found.</div>
  );

  const connName = connections.find((c) => c.id === cfg.connection_id)?.name ?? cfg.connection_id;
  const setField = (k: keyof JobConfigUpdate, v: unknown) =>
    setEditForm((f) => ({ ...f, [k]: v }));
  const form = editMode ? editForm : cfg;

  return (
    <div className="ing-page">
      {/* Breadcrumb */}
      <div className="ing-breadcrumb">
        <button className="ing-back-btn" onClick={() => navigate('/ingestion/job-configs')}>
          <ArrowLeft size={14} /> Job Configs
        </button>
        <span className="ing-breadcrumb-sep">/</span>
        <span className="ing-breadcrumb-current">{cfg.name}</span>
      </div>

      <div className="ing-detail-header">
        <div className="ing-detail-title-row">
          <div className="ing-card-icon-wrap ing-card-icon-wrap--lg">
            <Settings size={20} />
          </div>
          <div>
            <h1 className="ing-page-title">{cfg.name}</h1>
            <p className="ing-page-subtitle">{connName} · <span className="ing-mono">{cfg.path_template}</span></p>
          </div>
          {cfg.is_enabled ? (
            <span className="ing-badge ing-badge-success"><Power size={10} /> Enabled</span>
          ) : (
            <span className="ing-badge ing-badge-neutral"><PowerOff size={10} /> Disabled</span>
          )}
        </div>
        <div className="ing-detail-actions">
          {/* Toggle enabled */}
          {cfg.is_enabled ? (
            <button className="ing-btn-ghost" onClick={() => disableMut.mutate()} disabled={disableMut.isPending}>
              <PowerOff size={13} /> Disable
            </button>
          ) : (
            <button className="ing-btn-ghost" onClick={() => enableMut.mutate()} disabled={enableMut.isPending}>
              <Power size={13} /> Enable
            </button>
          )}
          {/* Trigger */}
          <button
            className="ing-btn-primary"
            onClick={() => triggerMut.mutate()}
            disabled={!cfg.is_enabled || triggerMut.isPending}
            title={!cfg.is_enabled ? 'Enable the job first' : 'Trigger a manual run'}
          >
            {triggerMut.isPending ? <Loader2 size={13} className="ing-spin" /> : <Play size={13} />}
            Run Now
          </button>
          {editMode ? (
            <>
              <button className="ing-btn-ghost" onClick={() => setEditMode(false)}>Cancel</button>
              <button className="ing-btn-primary" disabled={updateMut.isPending} onClick={() => updateMut.mutate(editForm)}>
                {updateMut.isPending ? <Loader2 size={13} className="ing-spin" /> : <Save size={13} />} Save
              </button>
            </>
          ) : (
            <button className="ing-btn-ghost" onClick={() => setEditMode(true)}>Edit</button>
          )}
          <button className="ing-btn-danger-outline" onClick={() => setShowDeleteConfirm(true)}>
            <Trash2 size={13} /> Delete
          </button>
        </div>
      </div>

      <div className="ing-detail-grid">
        {/* Config card */}
        <div className="ing-section">
          <h2 className="ing-section-title">Configuration</h2>
          <div className="ing-form-row">
            <div className="ing-form-group" style={{ flex: '0 0 90px' }}>
              <label className="ing-label">Method</label>
              {editMode
                ? <select className="ing-select" value={editForm.http_method ?? cfg.http_method} onChange={(e) => setField('http_method', e.target.value)}>
                    <option value="GET">GET</option><option value="POST">POST</option>
                  </select>
                : <div className="ing-value"><span className="ing-code-pill">{cfg.http_method}</span></div>}
            </div>
            <div className="ing-form-group">
              <label className="ing-label">Path Template</label>
              {editMode
                ? <input className="ing-input ing-mono" value={editForm.path_template ?? cfg.path_template} onChange={(e) => setField('path_template', e.target.value)} />
                : <div className="ing-value ing-mono">{cfg.path_template}</div>}
            </div>
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Schedule (cron)</label>
            {editMode
              ? <input className="ing-input ing-mono" value={editForm.schedule_cron ?? cfg.schedule_cron} onChange={(e) => setField('schedule_cron', e.target.value)} />
              : <div className="ing-value ing-mono"><Clock size={13} style={{ marginRight: 5, verticalAlign: 'middle' }} />{cfg.schedule_cron}</div>}
          </div>
          <div className="ing-form-row">
            <div className="ing-form-group">
              <label className="ing-label">Param Source</label>
              {editMode
                ? <select className="ing-select" value={editForm.param_source_type ?? cfg.param_source_type} onChange={(e) => setField('param_source_type', e.target.value as ParamSourceType)}>
                    <option value="static">Static list</option>
                    <option value="catalog_query">Catalog query</option>
                    <option value="parent_api">Parent API</option>
                  </select>
                : <div className="ing-value">{cfg.param_source_type}</div>}
            </div>
            <div className="ing-form-group">
              <label className="ing-label">Pagination</label>
              {editMode
                ? <select className="ing-select" value={editForm.pagination_type ?? cfg.pagination_type} onChange={(e) => setField('pagination_type', e.target.value as PaginationType)}>
                    <option value="none">None</option>
                    <option value="offset">Offset</option>
                    <option value="page">Page</option>
                    <option value="cursor_field">Cursor field</option>
                  </select>
                : <div className="ing-value">{cfg.pagination_type}</div>}
            </div>
          </div>
          {cfg.cursor_field_path && (
            <div className="ing-form-group">
              <label className="ing-label">Cursor Field Path</label>
              <div className="ing-value ing-mono">{cfg.cursor_field_path}</div>
            </div>
          )}
          <div className="ing-form-group">
            <label className="ing-label">Bronze Bucket</label>
            <div className="ing-value ing-mono">{cfg.target_bronze_bucket}</div>
          </div>
        </div>

        {/* Watermark controls */}
        <div className="ing-section">
          <h2 className="ing-section-title">Watermark</h2>
          <p className="ing-section-desc">
            The watermark tracks how far each parameter has been ingested.
            Resetting will cause the next run to re-fetch all data from the beginning.
          </p>
          <button
            className="ing-btn-danger-outline ing-btn-sm"
            onClick={() => setShowResetConfirm(true)}
          >
            <RotateCcw size={13} /> Reset All Watermarks
          </button>
        </div>
      </div>

      {/* Run history */}
      <div className="ing-section ing-section-full">
        <h2 className="ing-section-title">Recent Runs ({runs.length})</h2>
        {runs.length === 0 ? (
          <p className="ing-empty-inline">No runs yet. Click <strong>Run Now</strong> to trigger a manual run.</p>
        ) : (
          <div className="ing-table-wrap">
            <table className="ing-table">
              <thead>
                <tr>
                  <th>Started</th>
                  <th>Status</th>
                  <th>Params</th>
                  <th>Rows</th>
                  <th>Bytes</th>
                  <th>Duration</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const durationMs = r.finished_at
                    ? new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()
                    : null;
                  const durationStr = durationMs !== null
                    ? durationMs < 60_000
                      ? `${(durationMs / 1000).toFixed(1)}s`
                      : `${Math.floor(durationMs / 60_000)}m ${Math.floor((durationMs % 60_000) / 1000)}s`
                    : r.status === 'running' ? 'Running…' : '—';

                  return (
                    <tr
                      key={r.id}
                      className="ing-table-row-hover"
                      onClick={() => navigate(`/ingestion/runs/${r.id}`)}
                    >
                      <td className="ing-td-muted">{relTime(r.started_at)}</td>
                      <td>
                        <span className={`ing-badge ${STATUS_CLASS[r.status]}`}>
                          {STATUS_ICON[r.status]} {r.status}
                        </span>
                      </td>
                      <td className="ing-td-muted">
                        {r.succeeded_params}/{r.total_params}
                        {r.failed_params > 0 && <span className="ing-fail-count"> ({r.failed_params} failed)</span>}
                      </td>
                      <td className="ing-td-muted">{r.total_rows_landed.toLocaleString()}</td>
                      <td className="ing-td-muted">{formatBytes(r.total_bytes_landed)}</td>
                      <td className="ing-td-muted">{durationStr}</td>
                      <td><ChevronRight size={14} className="ing-chevron" /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete confirm */}
      {showDeleteConfirm && (
        <div className="ing-modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="ing-modal ing-modal--sm" onClick={(e) => e.stopPropagation()}>
            <div className="ing-modal-header"><h2 className="ing-modal-title">Delete Job Config?</h2></div>
            <div className="ing-modal-body">
              <p className="ing-confirm-text">
                Delete <strong>{cfg.name}</strong>? All run history and watermarks will also be deleted.
              </p>
            </div>
            <div className="ing-modal-footer">
              <button className="ing-btn-ghost" onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
              <button className="ing-btn-danger" disabled={deleteMut.isPending} onClick={() => deleteMut.mutate()}>
                {deleteMut.isPending ? <Loader2 size={13} className="ing-spin" /> : <Trash2 size={13} />} Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset watermark confirm */}
      {showResetConfirm && (
        <div className="ing-modal-overlay" onClick={() => setShowResetConfirm(false)}>
          <div className="ing-modal ing-modal--sm" onClick={(e) => e.stopPropagation()}>
            <div className="ing-modal-header"><h2 className="ing-modal-title">Reset Watermarks?</h2></div>
            <div className="ing-modal-body">
              <p className="ing-confirm-text">
                This will delete all watermark state for <strong>{cfg.name}</strong>.
                The next run will re-fetch all data from the beginning (full backfill).
              </p>
            </div>
            <div className="ing-modal-footer">
              <button className="ing-btn-ghost" onClick={() => setShowResetConfirm(false)}>Cancel</button>
              <button className="ing-btn-danger" disabled={resetMut.isPending} onClick={() => resetMut.mutate()}>
                {resetMut.isPending ? <Loader2 size={13} className="ing-spin" /> : <RotateCcw size={13} />} Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
