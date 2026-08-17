/**
 * Connections List Page — /ingestion/connections
 * Lists all ingestion connections for the workspace with create modal.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Cable, Plus, Search, ChevronRight, Key, Globe, Cpu,
  AlertCircle, Loader2, Trash2,
} from 'lucide-react';
import { useScopedPath } from '@/lib/appNavigation';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useToast } from '@/lib/toast';
import { extractApiError } from '@/lib/toast';
import * as api from '../lib/ingestionApi';
import type { Connection, ConnectionCreate, AuthType } from '../lib/ingestionTypes';

const AUTH_TYPE_LABELS: Record<AuthType, string> = {
  none: 'No Auth',
  api_key_header: 'API Key (Header)',
  api_key_query: 'API Key (Query Param)',
  bearer_token: 'Bearer Token',
  basic_auth: 'Basic Auth',
};

function ConnectionFormModal({
  onClose,
  onSave,
  loading,
}: {
  onClose: () => void;
  onSave: (data: ConnectionCreate) => void;
  loading: boolean;
}) {
  const [form, setForm] = useState<ConnectionCreate>({
    name: '',
    base_url: '',
    auth_type: 'none',
    auth_config: {},
    secret_value: '',
    rate_limit_rps: 5,
    max_concurrency: 5,
  });

  const set = (k: keyof ConnectionCreate, v: unknown) =>
    setForm((f) => ({ ...f, [k]: v }));

  const authConfigPlaceholder: Record<AuthType, string> = {
    none: '',
    api_key_header: 'Header name, e.g. "X-API-Key"',
    api_key_query: 'Param name, e.g. "api_key"',
    bearer_token: '',
    basic_auth: 'Username',
  };

  const authConfigKey: Record<AuthType, string | null> = {
    none: null,
    api_key_header: 'header_name',
    api_key_query: 'param_name',
    bearer_token: null,
    basic_auth: 'username',
  };

  const configKey = authConfigKey[form.auth_type];

  return (
    <div className="ing-modal-overlay" onClick={onClose}>
      <div className="ing-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ing-modal-header">
          <h2 className="ing-modal-title">New Connection</h2>
          <button className="ing-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="ing-modal-body">
          <div className="ing-form-group">
            <label className="ing-label">Name *</label>
            <input
              className="ing-input"
              placeholder="e.g. Weather API"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Base URL *</label>
            <input
              className="ing-input"
              placeholder="https://api.example.com/v2"
              value={form.base_url}
              onChange={(e) => set('base_url', e.target.value)}
            />
          </div>
          <div className="ing-form-group">
            <label className="ing-label">Description</label>
            <input
              className="ing-input"
              placeholder="Optional description"
              value={form.description || ''}
              onChange={(e) => set('description', e.target.value)}
            />
          </div>
          <div className="ing-form-row">
            <div className="ing-form-group">
              <label className="ing-label">Auth Type</label>
              <select
                className="ing-select"
                value={form.auth_type}
                onChange={(e) => set('auth_type', e.target.value as AuthType)}
              >
                {(Object.keys(AUTH_TYPE_LABELS) as AuthType[]).map((t) => (
                  <option key={t} value={t}>{AUTH_TYPE_LABELS[t]}</option>
                ))}
              </select>
            </div>
          </div>
          {configKey && (
            <div className="ing-form-group">
              <label className="ing-label">{authConfigPlaceholder[form.auth_type]}</label>
              <input
                className="ing-input"
                placeholder={authConfigPlaceholder[form.auth_type]}
                value={(form.auth_config?.[configKey] as string) || ''}
                onChange={(e) =>
                  set('auth_config', { ...form.auth_config, [configKey]: e.target.value })
                }
              />
            </div>
          )}
          {form.auth_type !== 'none' && (
            <div className="ing-form-group">
              <label className="ing-label">
                Secret Value
                <span className="ing-label-hint"> (encrypted at rest — never shown again)</span>
              </label>
              <input
                className="ing-input"
                type="password"
                placeholder="Paste API key / token / password"
                value={form.secret_value || ''}
                onChange={(e) => set('secret_value', e.target.value)}
              />
            </div>
          )}
          <div className="ing-form-row">
            <div className="ing-form-group">
              <label className="ing-label">Rate Limit (req/s)</label>
              <input
                className="ing-input"
                type="number"
                min={0.1}
                step={0.5}
                value={form.rate_limit_rps}
                onChange={(e) => set('rate_limit_rps', parseFloat(e.target.value))}
              />
            </div>
            <div className="ing-form-group">
              <label className="ing-label">Max Concurrency</label>
              <input
                className="ing-input"
                type="number"
                min={1}
                max={50}
                value={form.max_concurrency}
                onChange={(e) => set('max_concurrency', parseInt(e.target.value))}
              />
            </div>
          </div>
        </div>
        <div className="ing-modal-footer">
          <button className="ing-btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="ing-btn-primary"
            disabled={loading || !form.name || !form.base_url}
            onClick={() => onSave(form)}
          >
            {loading ? <Loader2 size={14} className="ing-spin" /> : null}
            Create Connection
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConnectionsPage() {
  const workspace = useWorkspaceContext();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const scopedPath = useScopedPath();

  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);

  const { data: connections = [], isLoading, isError } = useQuery<Connection[]>({
    queryKey: ['ingestion-connections', workspace.id],
    queryFn: () => api.listConnections(workspace.id),
    refetchInterval: 30_000,
  });

  const createMut = useMutation({
    mutationFn: (body: ConnectionCreate) => api.createConnection(workspace.id, body),
    onSuccess: (conn) => {
      qc.invalidateQueries({ queryKey: ['ingestion-connections', workspace.id] });
      toast.success(`Connection '${conn.name}' created.`);
      setShowCreate(false);
      navigate(scopedPath(`/ingestion/connections/${conn.id}`));
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const filtered = connections.filter((c) =>
    !search || c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.base_url.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="ing-page">
      <div className="ing-page-header">
        <div className="ing-page-title-row">
          <Cable size={22} className="ing-page-icon" />
          <div>
            <h1 className="ing-page-title">API Connections</h1>
            <p className="ing-page-subtitle">
              Reusable endpoint + auth configs for pull-based API ingestion
            </p>
          </div>
        </div>
        <button className="ing-btn-primary" onClick={() => setShowCreate(true)} id="create-connection-btn">
          <Plus size={15} />
          New Connection
        </button>
      </div>

      <div className="ing-toolbar">
        <div className="ing-search-wrap">
          <Search size={14} className="ing-search-icon" />
          <input
            className="ing-search"
            placeholder="Search connections…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="ing-count">{filtered.length} connection{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {isLoading && (
        <div className="ing-loading"><Loader2 size={20} className="ing-spin" /> Loading…</div>
      )}
      {isError && (
        <div className="ing-error"><AlertCircle size={16} /> Failed to load connections.</div>
      )}

      {!isLoading && !isError && filtered.length === 0 && (
        <div className="ing-empty">
          <Cable size={40} className="ing-empty-icon" />
          <p className="ing-empty-title">No connections yet</p>
          <p className="ing-empty-sub">Create a connection to start ingesting data from a REST API.</p>
          <button className="ing-btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={14} /> New Connection
          </button>
        </div>
      )}

      <div className="ing-card-grid">
        {filtered.map((c) => (
          <div
            key={c.id}
            className="ing-card ing-card-hover"
            onClick={() => navigate(scopedPath(`/ingestion/connections/${c.id}`))}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && navigate(scopedPath(`/ingestion/connections/${c.id}`))}
          >
            <div className="ing-card-top">
              <div className="ing-card-icon-wrap">
                <Globe size={18} />
              </div>
              <span className="ing-badge ing-badge-neutral">
                {AUTH_TYPE_LABELS[c.auth_type]}
              </span>
            </div>
            <h3 className="ing-card-name">{c.name}</h3>
            {c.description && <p className="ing-card-desc">{c.description}</p>}
            <p className="ing-card-url">{c.base_url}</p>
            <div className="ing-card-meta">
              {c.has_secret && (
                <span className="ing-meta-chip">
                  <Key size={11} /> Secret set
                </span>
              )}
              <span className="ing-meta-chip">
                <Cpu size={11} /> {c.max_concurrency} workers
              </span>
              <span className="ing-meta-chip">
                {c.rate_limit_rps} req/s
              </span>
            </div>
            <div className="ing-card-arrow">
              <ChevronRight size={16} />
            </div>
          </div>
        ))}
      </div>

      {showCreate && (
        <ConnectionFormModal
          onClose={() => setShowCreate(false)}
          onSave={(data) => createMut.mutate(data)}
          loading={createMut.isPending}
        />
      )}
    </div>
  );
}
