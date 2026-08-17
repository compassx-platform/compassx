/**
 * Connection Detail Page — /ingestion/connections/:connectionId
 * Edit metadata, rotate secret, view associated job configs, delete.
 */
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Globe, Key, RotateCcw, Trash2, Loader2,
  AlertCircle, Save, ChevronRight, Plus, Power, PowerOff,
} from 'lucide-react';
import { useScopedPath, useScopedNavigate } from '@/lib/appNavigation';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as api from '../lib/ingestionApi';
import type { Connection, JobConfig, AuthType } from '../lib/ingestionTypes';

const AUTH_TYPE_LABELS: Record<AuthType, string> = {
  none: 'No Auth',
  api_key_header: 'API Key (Header)',
  api_key_query: 'API Key (Query Param)',
  bearer_token: 'Bearer Token',
  basic_auth: 'Basic Auth',
};

export default function ConnectionDetailPage() {
  const { connectionId } = useParams<{ connectionId: string }>();
  const workspace = useWorkspaceContext();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useScopedNavigate();
  const scopedPath = useScopedPath();

  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState<Partial<Connection>>({});
  const [rotateSecret, setRotateSecret] = useState('');
  const [showRotate, setShowRotate] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: conn, isLoading, isError } = useQuery<Connection>({
    queryKey: ['ingestion-connection', workspace.id, connectionId],
    queryFn: () => api.getConnection(workspace.id, connectionId!),
    enabled: !!connectionId,
  });

  const { data: jobConfigs = [] } = useQuery<JobConfig[]>({
    queryKey: ['ingestion-job-configs', workspace.id, connectionId],
    queryFn: () => api.listJobConfigs(workspace.id, connectionId!),
    enabled: !!connectionId,
  });

  const updateMut = useMutation({
    mutationFn: (body: Partial<Connection>) =>
      api.updateConnection(workspace.id, connectionId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-connection', workspace.id, connectionId] });
      qc.invalidateQueries({ queryKey: ['ingestion-connections', workspace.id] });
      toast.success('Connection updated.');
      setEditMode(false);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const rotateMut = useMutation({
    mutationFn: () => api.rotateConnectionSecret(workspace.id, connectionId!, rotateSecret),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-connection', workspace.id, connectionId] });
      toast.success('Secret rotated successfully.');
      setShowRotate(false);
      setRotateSecret('');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const deleteMut = useMutation({
    mutationFn: () => api.deleteConnection(workspace.id, connectionId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ingestion-connections', workspace.id] });
      toast.success('Connection deleted.');
      navigate('/ingestion/connections');
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  if (isLoading) return (
    <div className="ing-page ing-loading"><Loader2 size={20} className="ing-spin" /> Loading…</div>
  );
  if (isError || !conn) return (
    <div className="ing-page ing-error"><AlertCircle size={16} /> Connection not found.</div>
  );

  const currentForm: Partial<Connection> = editMode ? editForm : conn;
  const setField = (k: keyof Connection, v: unknown) => setEditForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="ing-page">
      {/* Breadcrumb */}
      <div className="ing-breadcrumb">
        <button className="ing-back-btn" onClick={() => navigate('/ingestion/connections')}>
          <ArrowLeft size={14} /> Connections
        </button>
        <span className="ing-breadcrumb-sep">/</span>
        <span className="ing-breadcrumb-current">{conn.name}</span>
      </div>

      <div className="ing-detail-header">
        <div className="ing-detail-title-row">
          <div className="ing-card-icon-wrap ing-card-icon-wrap--lg">
            <Globe size={22} />
          </div>
          <div>
            <h1 className="ing-page-title">{conn.name}</h1>
            <p className="ing-page-subtitle">{conn.base_url}</p>
          </div>
          <span className="ing-badge ing-badge-neutral">{AUTH_TYPE_LABELS[conn.auth_type]}</span>
        </div>
        <div className="ing-detail-actions">
          {editMode ? (
            <>
              <button className="ing-btn-ghost" onClick={() => { setEditMode(false); setEditForm({}); }}>
                Cancel
              </button>
              <button
                className="ing-btn-primary"
                disabled={updateMut.isPending}
                onClick={() => updateMut.mutate(editForm)}
              >
                {updateMut.isPending ? <Loader2 size={13} className="ing-spin" /> : <Save size={13} />}
                Save
              </button>
            </>
          ) : (
            <>
              <button className="ing-btn-ghost" onClick={() => { setEditMode(true); setEditForm({ ...conn }); }}>
                Edit
              </button>
              <button
                className="ing-btn-danger-outline"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 size={13} /> Delete
              </button>
            </>
          )}
        </div>
      </div>

      <div className="ing-detail-grid">
        {/* Metadata card */}
        <div className="ing-section">
          <h2 className="ing-section-title">Connection Details</h2>
          <div className="ing-form-group">
            <label className="ing-label">Name</label>
            {editMode ? (
              <input className="ing-input" value={(currentForm.name as string) || ''} onChange={(e) => setField('name', e.target.value)} />
            ) : (
              <div className="ing-value">{conn.name}</div>
            )}
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Base URL</label>
            {editMode ? (
              <input className="ing-input" value={(currentForm.base_url as string) || ''} onChange={(e) => setField('base_url', e.target.value)} />
            ) : (
              <div className="ing-value ing-mono">{conn.base_url}</div>
            )}
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Description</label>
            {editMode ? (
              <input className="ing-input" value={(currentForm.description as string) || ''} onChange={(e) => setField('description', e.target.value)} />
            ) : (
              <div className="ing-value">{conn.description || '—'}</div>
            )}
          </div>
          <div className="ing-form-row">
            <div className="ing-form-group">
              <label className="ing-label">Rate Limit (req/s)</label>
              {editMode ? (
                <input className="ing-input" type="number" min={0.1} step={0.5} value={(currentForm.rate_limit_rps as number) ?? conn.rate_limit_rps} onChange={(e) => setField('rate_limit_rps', parseFloat(e.target.value))} />
              ) : (
                <div className="ing-value">{conn.rate_limit_rps}</div>
              )}
            </div>
            <div className="ing-form-group">
              <label className="ing-label">Max Concurrency</label>
              {editMode ? (
                <input className="ing-input" type="number" min={1} max={50} value={(currentForm.max_concurrency as number) ?? conn.max_concurrency} onChange={(e) => setField('max_concurrency', parseInt(e.target.value))} />
              ) : (
                <div className="ing-value">{conn.max_concurrency} workers</div>
              )}
            </div>
          </div>
        </div>

        {/* Auth + Secret card */}
        <div className="ing-section">
          <h2 className="ing-section-title">Authentication</h2>
          <div className="ing-form-group">
            <label className="ing-label">Auth Type</label>
            <div className="ing-value">{AUTH_TYPE_LABELS[conn.auth_type]}</div>
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Secret Status</label>
            <div className="ing-value ing-secret-status">
              {conn.has_secret ? (
                <span className="ing-badge ing-badge-success"><Key size={11} /> Secret configured</span>
              ) : (
                <span className="ing-badge ing-badge-neutral">No secret</span>
              )}
            </div>
          </div>
          {!showRotate ? (
            <button className="ing-btn-ghost ing-btn-sm" onClick={() => setShowRotate(true)}>
              <RotateCcw size={13} /> Rotate Secret
            </button>
          ) : (
            <div className="ing-rotate-form">
              <div className="ing-form-group">
                <label className="ing-label">New Secret Value</label>
                <input
                  className="ing-input"
                  type="password"
                  placeholder="Paste new API key / token"
                  value={rotateSecret}
                  onChange={(e) => setRotateSecret(e.target.value)}
                />
              </div>
              <div className="ing-rotate-actions">
                <button className="ing-btn-ghost ing-btn-sm" onClick={() => { setShowRotate(false); setRotateSecret(''); }}>Cancel</button>
                <button
                  className="ing-btn-primary ing-btn-sm"
                  disabled={!rotateSecret || rotateMut.isPending}
                  onClick={() => rotateMut.mutate()}
                >
                  {rotateMut.isPending ? <Loader2 size={12} className="ing-spin" /> : <RotateCcw size={12} />}
                  Rotate
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Job Configs associated with this connection */}
      <div className="ing-section ing-section-full">
        <div className="ing-section-header-row">
          <h2 className="ing-section-title">Job Configs ({jobConfigs.length})</h2>
          <button
            className="ing-btn-ghost ing-btn-sm"
            onClick={() => navigate(`/ingestion/job-configs?connection_id=${connectionId}`)}
          >
            <Plus size={13} /> New Job Config
          </button>
        </div>
        {jobConfigs.length === 0 ? (
          <p className="ing-empty-inline">No job configs for this connection yet.</p>
        ) : (
          <div className="ing-table-wrap">
            <table className="ing-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Method</th>
                  <th>Path Template</th>
                  <th>Schedule</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobConfigs.map((jc) => (
                  <tr
                    key={jc.id}
                    className="ing-table-row-hover"
                    onClick={() => navigate(`/ingestion/job-configs/${jc.id}`)}
                  >
                    <td className="ing-td-bold">{jc.name}</td>
                    <td><span className="ing-code-pill">{jc.http_method}</span></td>
                    <td className="ing-mono ing-td-muted">{jc.path_template}</td>
                    <td className="ing-mono ing-td-muted">{jc.schedule_cron}</td>
                    <td>
                      {jc.is_enabled ? (
                        <span className="ing-badge ing-badge-success">
                          <Power size={10} /> Enabled
                        </span>
                      ) : (
                        <span className="ing-badge ing-badge-neutral">
                          <PowerOff size={10} /> Disabled
                        </span>
                      )}
                    </td>
                    <td><ChevronRight size={15} className="ing-chevron" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete confirm modal */}
      {showDeleteConfirm && (
        <div className="ing-modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="ing-modal ing-modal--sm" onClick={(e) => e.stopPropagation()}>
            <div className="ing-modal-header">
              <h2 className="ing-modal-title">Delete Connection?</h2>
            </div>
            <div className="ing-modal-body">
              <p className="ing-confirm-text">
                Are you sure you want to delete <strong>{conn.name}</strong>?
                All disabled job configs referencing it will also be deleted.
                Enabled configs block deletion.
              </p>
            </div>
            <div className="ing-modal-footer">
              <button className="ing-btn-ghost" onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
              <button
                className="ing-btn-danger"
                disabled={deleteMut.isPending}
                onClick={() => deleteMut.mutate()}
              >
                {deleteMut.isPending ? <Loader2 size={13} className="ing-spin" /> : <Trash2 size={13} />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
