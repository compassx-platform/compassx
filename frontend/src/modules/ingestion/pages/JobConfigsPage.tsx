/**
 * Job Configs List Page — /ingestion/job-configs
 * Lists all job configs with connection filter, status badges, and trigger.
 */
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings, Plus, Search, Play, Power, PowerOff, ChevronRight,
  Loader2, AlertCircle, Clock,
} from 'lucide-react';
import { useScopedPath, useScopedNavigate } from '@/lib/appNavigation';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as api from '../lib/ingestionApi';
import type { JobConfig, JobConfigCreate, Connection, ParamSourceType, PaginationType } from '../lib/ingestionTypes';

const PARAM_SOURCE_LABELS: Record<ParamSourceType, string> = {
  static: 'Static list',
  catalog_query: 'Catalog query',
  parent_api: 'Parent API call',
};

function JobConfigFormModal({
  connections,
  prefillConnectionId,
  onClose,
  onSave,
  loading,
}: {
  connections: Connection[];
  prefillConnectionId?: string;
  onClose: () => void;
  onSave: (data: JobConfigCreate) => void;
  loading: boolean;
}) {
  const [form, setForm] = useState<JobConfigCreate>({
    connection_id: prefillConnectionId || (connections[0]?.id ?? ''),
    name: '',
    path_template: '',
    schedule_cron: '0 * * * *',
    http_method: 'GET',
    param_source_type: 'static',
    param_source_config: { values: [] },
    pagination_type: 'none',
    pagination_config: {},
    query_template: {},
    is_enabled: true,
  });

  const set = (k: keyof JobConfigCreate, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="ing-modal-overlay" onClick={onClose}>
      <div className="ing-modal ing-modal--wide" onClick={(e) => e.stopPropagation()}>
        <div className="ing-modal-header">
          <h2 className="ing-modal-title">New Job Config</h2>
          <button className="ing-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="ing-modal-body">
          <div className="ing-form-group">
            <label className="ing-label">Name *</label>
            <input className="ing-input" placeholder="e.g. Asset Readings Pull" value={form.name} onChange={(e) => set('name', e.target.value)} />
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Connection *</label>
            <select className="ing-select" value={form.connection_id} onChange={(e) => set('connection_id', e.target.value)}>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="ing-form-row">
            <div className="ing-form-group" style={{ flex: '0 0 100px' }}>
              <label className="ing-label">Method</label>
              <select className="ing-select" value={form.http_method} onChange={(e) => set('http_method', e.target.value as 'GET' | 'POST')}>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
            </div>
            <div className="ing-form-group">
              <label className="ing-label">Path Template *</label>
              <input className="ing-input ing-mono" placeholder="/assets/{asset_id}/readings" value={form.path_template} onChange={(e) => set('path_template', e.target.value)} />
            </div>
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Schedule (cron) *</label>
            <input className="ing-input ing-mono" placeholder="0 * * * *" value={form.schedule_cron} onChange={(e) => set('schedule_cron', e.target.value)} />
          </div>
          <div className="ing-form-row">
            <div className="ing-form-group">
              <label className="ing-label">Param Source</label>
              <select className="ing-select" value={form.param_source_type} onChange={(e) => set('param_source_type', e.target.value as ParamSourceType)}>
                {(Object.entries(PARAM_SOURCE_LABELS) as [ParamSourceType, string][]).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="ing-form-group">
              <label className="ing-label">Pagination</label>
              <select className="ing-select" value={form.pagination_type} onChange={(e) => set('pagination_type', e.target.value as PaginationType)}>
                <option value="none">None</option>
                <option value="offset">Offset</option>
                <option value="page">Page number</option>
                <option value="cursor_field">Cursor field</option>
              </select>
            </div>
          </div>
          {form.param_source_type === 'static' && (
            <div className="ing-form-group">
              <label className="ing-label">
                Static Values
                <span className="ing-label-hint"> (comma-separated)</span>
              </label>
              <input
                className="ing-input"
                placeholder="asset-001, asset-002, asset-003"
                value={(form.param_source_config?.values as string[] | undefined)?.join(', ') || ''}
                onChange={(e) =>
                  set('param_source_config', {
                    values: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  })
                }
              />
            </div>
          )}
        </div>
        <div className="ing-modal-footer">
          <button className="ing-btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="ing-btn-primary"
            disabled={loading || !form.name || !form.path_template || !form.connection_id}
            onClick={() => onSave(form)}
          >
            {loading ? <Loader2 size={14} className="ing-spin" /> : null}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

export default function JobConfigsPage() {
  const [searchParams] = useSearchParams();
  const workspace = useWorkspaceContext();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useScopedNavigate();
  const scopedPath = useScopedPath();

  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const prefillConn = searchParams.get('connection_id') || undefined;

  const { data: connections = [] } = useQuery<Connection[]>({
    queryKey: ['ingestion-connections', workspace.id],
    queryFn: () => api.listConnections(workspace.id),
  });

  const { data: jobConfigs = [], isLoading, isError } = useQuery<JobConfig[]>({
    queryKey: ['ingestion-job-configs', workspace.id],
    queryFn: () => api.listJobConfigs(workspace.id),
    refetchInterval: 20_000,
  });

  const createMut = useMutation({
    mutationFn: (body: JobConfigCreate) => api.createJobConfig(workspace.id, body),
    onSuccess: (cfg) => {
      qc.invalidateQueries({ queryKey: ['ingestion-job-configs', workspace.id] });
      toast.success(`Job config '${cfg.name}' created.`);
      setShowCreate(false);
      navigate(`/ingestion/job-configs/${cfg.id}`);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const triggerMut = useMutation({
    mutationFn: (jobConfigId: string) => api.triggerRun(workspace.id, jobConfigId),
    onSuccess: (res, jcId) => {
      const jc = jobConfigs.find((j) => j.id === jcId);
      toast.success(`Run started for '${jc?.name ?? 'job'}'. Run ID: ${res.run_id.slice(0, 8)}…`);
      navigate(`/ingestion/job-configs/${jcId}`);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const filtered = jobConfigs.filter((jc) =>
    !search || jc.name.toLowerCase().includes(search.toLowerCase()),
  );

  const connMap = Object.fromEntries(connections.map((c) => [c.id, c]));

  return (
    <div className="ing-page">
      <div className="ing-page-header">
        <div className="ing-page-title-row">
          <Settings size={22} className="ing-page-icon" />
          <div>
            <h1 className="ing-page-title">Job Configs</h1>
            <p className="ing-page-subtitle">
              Per-endpoint pull definitions — schedules, pagination, fan-out
            </p>
          </div>
        </div>
        <button
          className="ing-btn-primary"
          onClick={() => setShowCreate(true)}
          id="create-job-config-btn"
          disabled={connections.length === 0}
          title={connections.length === 0 ? 'Create a connection first' : undefined}
        >
          <Plus size={15} />
          New Job Config
        </button>
      </div>

      <div className="ing-toolbar">
        <div className="ing-search-wrap">
          <Search size={14} className="ing-search-icon" />
          <input
            className="ing-search"
            placeholder="Search job configs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="ing-count">{filtered.length} config{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {isLoading && <div className="ing-loading"><Loader2 size={20} className="ing-spin" /> Loading…</div>}
      {isError && <div className="ing-error"><AlertCircle size={16} /> Failed to load job configs.</div>}

      {!isLoading && !isError && filtered.length === 0 && (
        <div className="ing-empty">
          <Settings size={40} className="ing-empty-icon" />
          <p className="ing-empty-title">No job configs yet</p>
          <p className="ing-empty-sub">
            {connections.length === 0
              ? 'Create a Connection first, then add a Job Config.'
              : 'Define your first pull — set path template, pagination, and schedule.'}
          </p>
          <button className="ing-btn-primary" onClick={() => setShowCreate(true)} disabled={connections.length === 0}>
            <Plus size={14} /> New Job Config
          </button>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="ing-table-wrap">
          <table className="ing-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Connection</th>
                <th>Method + Path</th>
                <th>Schedule</th>
                <th>Param Source</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((jc) => (
                <tr
                  key={jc.id}
                  className="ing-table-row-hover"
                  onClick={() => navigate(`/ingestion/job-configs/${jc.id}`)}
                >
                  <td className="ing-td-bold">{jc.name}</td>
                  <td className="ing-td-muted">{connMap[jc.connection_id]?.name ?? '—'}</td>
                  <td>
                    <span className="ing-code-pill">{jc.http_method}</span>
                    <span className="ing-mono ing-td-muted" style={{ marginLeft: 6 }}>{jc.path_template}</span>
                  </td>
                  <td className="ing-mono ing-td-muted">
                    <Clock size={11} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                    {jc.schedule_cron}
                  </td>
                  <td className="ing-td-muted">{PARAM_SOURCE_LABELS[jc.param_source_type]}</td>
                  <td>
                    {jc.is_enabled ? (
                      <span className="ing-badge ing-badge-success"><Power size={10} /> Enabled</span>
                    ) : (
                      <span className="ing-badge ing-badge-neutral"><PowerOff size={10} /> Disabled</span>
                    )}
                  </td>
                  <td>
                    <button
                      className="ing-btn-icon"
                      title="Trigger run"
                      onClick={(e) => { e.stopPropagation(); triggerMut.mutate(jc.id); }}
                      disabled={!jc.is_enabled || triggerMut.isPending}
                    >
                      <Play size={14} />
                    </button>
                    <ChevronRight size={15} className="ing-chevron" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <JobConfigFormModal
          connections={connections}
          prefillConnectionId={prefillConn}
          onClose={() => setShowCreate(false)}
          onSave={(data) => createMut.mutate(data)}
          loading={createMut.isPending}
        />
      )}
    </div>
  );
}
