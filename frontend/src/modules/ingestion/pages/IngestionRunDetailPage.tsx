/**
 * Ingestion Run Detail Page — /ingestion/runs/:runId
 * Shows run summary stats + per-param item breakdown table.
 */
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft, Loader2, AlertCircle, CheckCircle2, XCircle,
  AlertTriangle, FileJson, ChevronDown, ChevronUp,
} from 'lucide-react';
import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import * as api from '../lib/ingestionApi';
import type { IngestionRun, IngestionRunItem, RunStatus } from '../lib/ingestionTypes';

const STATUS_ICON = {
  running:   <Loader2 size={14} className="ing-spin" />,
  succeeded: <CheckCircle2 size={14} />,
  failed:    <XCircle size={14} />,
  partial:   <AlertTriangle size={14} />,
};

const STATUS_CLASS: Record<RunStatus, string> = {
  running:   'ing-badge-info',
  succeeded: 'ing-badge-success',
  failed:    'ing-badge-danger',
  partial:   'ing-badge-warning',
};

const ITEM_ICON = {
  succeeded: <CheckCircle2 size={13} />,
  failed:    <XCircle size={13} />,
  skipped:   <AlertTriangle size={13} />,
};

const ITEM_CLASS = {
  succeeded: 'ing-badge-success',
  failed:    'ing-badge-danger',
  skipped:   'ing-badge-neutral',
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

function duration(start?: string, end?: string) {
  if (!start) return '—';
  const endTs = end ? new Date(end).getTime() : Date.now();
  const ms = endTs - new Date(start).getTime();
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="ing-stat-card">
      <div className="ing-stat-value">{value}</div>
      <div className="ing-stat-label">{label}</div>
      {sub && <div className="ing-stat-sub">{sub}</div>}
    </div>
  );
}

export default function IngestionRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const workspace = useWorkspaceContext();
  const navigate = useScopedNavigate();

  const [statusFilter, setStatusFilter] = useState('');
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null);

  const { data: run, isLoading, isError } = useQuery<IngestionRun>({
    queryKey: ['ingestion-run', workspace.id, runId],
    queryFn: () => api.getRun(workspace.id, runId!),
    enabled: !!runId,
    refetchInterval: (query) =>
      query.state.data?.status === 'running' ? 3_000 : false,
  });

  const { data: items = [], isLoading: itemsLoading } = useQuery<IngestionRunItem[]>({
    queryKey: ['ingestion-run-items', workspace.id, runId, statusFilter],
    queryFn: () => api.getRunItems(workspace.id, runId!, statusFilter || undefined),
    enabled: !!runId,
    refetchInterval: run?.status === 'running' ? 5_000 : false,
  });

  if (isLoading) return (
    <div className="ing-page ing-loading"><Loader2 size={20} className="ing-spin" /> Loading…</div>
  );
  if (isError || !run) return (
    <div className="ing-page ing-error"><AlertCircle size={16} /> Run not found.</div>
  );

  const successRate = run.total_params > 0
    ? Math.round((run.succeeded_params / run.total_params) * 100)
    : 0;

  return (
    <div className="ing-page">
      {/* Breadcrumb */}
      <div className="ing-breadcrumb">
        <button className="ing-back-btn" onClick={() => navigate(`/ingestion/job-configs/${run.job_config_id}`)}>
          <ArrowLeft size={14} /> Job Config
        </button>
        <span className="ing-breadcrumb-sep">/</span>
        <span className="ing-breadcrumb-current">Run {run.id.slice(0, 8)}…</span>
      </div>

      <div className="ing-detail-header">
        <div className="ing-detail-title-row">
          <h1 className="ing-page-title">Run Detail</h1>
          <span className={`ing-badge ${STATUS_CLASS[run.status]}`}>
            {STATUS_ICON[run.status]} {run.status}
          </span>
        </div>
        <div className="ing-run-meta">
          <span>Started {relTime(run.started_at)}</span>
          {run.finished_at && <span>· Finished {relTime(run.finished_at)}</span>}
          {run.airflow_dag_run_id && (
            <span className="ing-mono">· DAG: {run.airflow_dag_run_id}</span>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="ing-stats-row">
        <StatCard label="Params" value={run.total_params} />
        <StatCard
          label="Succeeded"
          value={run.succeeded_params}
          sub={`${successRate}%`}
        />
        <StatCard label="Failed" value={run.failed_params} />
        <StatCard label="Rows Landed" value={run.total_rows_landed.toLocaleString()} />
        <StatCard label="Bytes Landed" value={formatBytes(run.total_bytes_landed)} />
        <StatCard label="Duration" value={duration(run.started_at, run.finished_at)} />
      </div>

      {run.error_summary && (
        <div className="ing-error-banner">
          <AlertTriangle size={14} />
          <span>{run.error_summary}</span>
        </div>
      )}

      {/* Item breakdown */}
      <div className="ing-section ing-section-full">
        <div className="ing-section-header-row">
          <h2 className="ing-section-title">Per-Param Breakdown ({items.length})</h2>
          <div className="ing-filter-pills">
            {['', 'succeeded', 'failed', 'skipped'].map((s) => (
              <button
                key={s}
                className={`ing-filter-pill${statusFilter === s ? ' active' : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s || 'All'}
              </button>
            ))}
          </div>
        </div>

        {itemsLoading ? (
          <div className="ing-loading"><Loader2 size={16} className="ing-spin" /> Loading items…</div>
        ) : items.length === 0 ? (
          <p className="ing-empty-inline">No items{statusFilter ? ` with status '${statusFilter}'` : ''}.</p>
        ) : (
          <div className="ing-table-wrap">
            <table className="ing-table">
              <thead>
                <tr>
                  <th>Param Value</th>
                  <th>Status</th>
                  <th>Pages</th>
                  <th>Rows</th>
                  <th>Bytes</th>
                  <th>Duration</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const isExpanded = expandedItemId === item.id;
                  return (
                    <>
                      <tr
                        key={item.id}
                        className="ing-table-row-hover"
                        onClick={() => setExpandedItemId(isExpanded ? null : item.id)}
                      >
                        <td className="ing-td-bold ing-mono">{item.param_value}</td>
                        <td>
                          <span className={`ing-badge ${ITEM_CLASS[item.status]}`}>
                            {ITEM_ICON[item.status]} {item.status}
                          </span>
                        </td>
                        <td className="ing-td-muted">{item.pages_fetched}</td>
                        <td className="ing-td-muted">{item.rows_landed.toLocaleString()}</td>
                        <td className="ing-td-muted">{formatBytes(item.bytes_landed)}</td>
                        <td className="ing-td-muted">{duration(item.started_at, item.finished_at)}</td>
                        <td>
                          {isExpanded
                            ? <ChevronUp size={14} className="ing-chevron" />
                            : <ChevronDown size={14} className="ing-chevron" />}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${item.id}-detail`} className="ing-item-expand-row">
                          <td colSpan={7}>
                            <div className="ing-item-detail">
                              {item.bronze_path && (
                                <div className="ing-item-detail-row">
                                  <FileJson size={13} />
                                  <span className="ing-label">Bronze path:</span>
                                  <span className="ing-mono ing-td-muted">{item.bronze_path}</span>
                                </div>
                              )}
                              {item.error_message && (
                                <div className="ing-item-detail-row ing-item-error">
                                  <XCircle size={13} />
                                  <span className="ing-label">Error:</span>
                                  <span className="ing-error-text">{item.error_message}</span>
                                </div>
                              )}
                              <div className="ing-item-detail-row">
                                <span className="ing-label">Started:</span>
                                <span className="ing-td-muted">{new Date(item.started_at).toLocaleString()}</span>
                                {item.finished_at && (
                                  <>
                                    <span className="ing-label" style={{ marginLeft: 16 }}>Finished:</span>
                                    <span className="ing-td-muted">{new Date(item.finished_at).toLocaleString()}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
