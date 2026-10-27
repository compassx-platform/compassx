import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical,
  ExternalLink,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  Layers,
  BarChart3,
  Sliders,
  Copy,
  Check,
  Package,
  Folder,
  FileText,
  Sparkles,
  Tag,
  ShieldCheck,
  Plus,
  Box,
} from 'lucide-react';
import api from '@/lib/api';
import { useNotebookStore } from '../../store/notebookStore';

interface RunData {
  run_id: string;
  run_name: string;
  status: string;
  start_time: number | null;
  end_time: number | null;
  duration_ms: number | null;
  artifact_uri?: string | null;
  metrics: Record<string, number>;
  params: Record<string, string>;
  tags: Record<string, string>;
  ui_url: string;
}

interface ExperimentDetails {
  experiment_id: string;
  name: string;
  artifact_location?: string;
  lifecycle_stage?: string;
}

interface ExperimentRunsResponse {
  connected: boolean;
  experiment?: ExperimentDetails | null;
  ui_url?: string;
  total_runs?: number;
  runs?: RunData[];
  message?: string;
}

interface ArtifactFile {
  path: string;
  is_dir: boolean;
  file_size?: number;
}

interface ModelVersion {
  version: string;
  creation_timestamp?: number;
  last_updated_timestamp?: number;
  current_stage?: string;
  aliases?: string[];
  status?: string;
  source?: string;
  run_id?: string;
  ui_url?: string;
}

interface RegisteredModel {
  name: string;
  creation_timestamp?: number;
  last_updated_timestamp?: number;
  description?: string;
  latest_versions: ModelVersion[];
  tags: Record<string, string>;
  ui_url?: string;
}

interface ModelsResponse {
  connected: boolean;
  models: RegisteredModel[];
  total_models?: number;
  message?: string;
}

function formatDuration(durationMs: number | null): string {
  if (durationMs === null || durationMs === undefined) return '—';
  if (durationMs < 1000) return `${durationMs}ms`;
  const secs = durationMs / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const remSecs = Math.floor(secs % 60);
  return `${mins}m ${remSecs}s`;
}

function formatRelativeTime(timestampMs: number | null): string {
  if (!timestampMs) return '—';
  const diffSec = Math.floor((Date.now() - timestampMs) / 1000);
  if (diffSec < 10) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function formatBytes(bytes?: number): string {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function ExperimentsPanel() {
  const notebookPath = useNotebookStore((s) => s.notebookPath);
  const [activeTab, setActiveTab] = useState<'runs' | 'models'>('runs');

  // Runs data state
  const [runsData, setRunsData] = useState<ExperimentRunsResponse | null>(null);
  const [runsLoading, setRunsLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [expandedRuns, setExpandedRuns] = useState<Record<string, boolean>>({});
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  // Artifacts state: run_id -> ArtifactFile[]
  const [artifactsMap, setArtifactsMap] = useState<Record<string, ArtifactFile[]>>({});
  const [artifactsLoading, setArtifactsLoading] = useState<Record<string, boolean>>({});
  const [expandedArtifacts, setExpandedArtifacts] = useState<Record<string, boolean>>({});

  // Models state
  const [modelsData, setModelsData] = useState<ModelsResponse | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsSearch, setModelsSearch] = useState('');

  // Register Model dialog state
  const [registeringRunId, setRegisteringRunId] = useState<string | null>(null);
  const [regModelName, setRegModelName] = useState('');
  const [regArtifactPath, setRegArtifactPath] = useState('model');
  const [regDescription, setRegDescription] = useState('');
  const [regSubmitting, setRegSubmitting] = useState(false);
  const [regFeedback, setRegFeedback] = useState<{ success: boolean; message: string } | null>(null);

  const fetchRuns = useCallback(async (showSpinner = false) => {
    if (!notebookPath) return;
    if (showSpinner) setRunsLoading(true);
    try {
      const res = await api.get('/notebook/experiments/runs', {
        params: { path: notebookPath, max_results: 50 },
      });
      setRunsData(res.data);
    } catch (err: any) {
      console.warn('[notebook] Failed to fetch MLflow experiment runs:', err);
      setRunsData({
        connected: false,
        message: err.response?.data?.message || err.message || 'Failed to query MLflow',
        runs: [],
      });
    } finally {
      if (showSpinner) setRunsLoading(false);
    }
  }, [notebookPath]);

  const fetchModels = useCallback(async (showSpinner = false) => {
    if (showSpinner) setModelsLoading(true);
    try {
      const res = await api.get('/notebook/experiments/models', {
        params: { max_results: 50 },
      });
      setModelsData(res.data);
    } catch (err: any) {
      console.warn('[notebook] Failed to fetch MLflow models:', err);
      setModelsData({
        connected: false,
        models: [],
        message: err.response?.data?.message || err.message || 'Failed to query Model Registry',
      });
    } finally {
      if (showSpinner) setModelsLoading(false);
    }
  }, []);

  const fetchArtifacts = async (runId: string) => {
    if (artifactsMap[runId]) {
      setExpandedArtifacts((prev) => ({ ...prev, [runId]: !prev[runId] }));
      return;
    }
    setArtifactsLoading((prev) => ({ ...prev, [runId]: true }));
    setExpandedArtifacts((prev) => ({ ...prev, [runId]: true }));
    try {
      const res = await api.get(`/notebook/experiments/runs/${runId}/artifacts`);
      if (res.data?.connected && res.data.files) {
        setArtifactsMap((prev) => ({ ...prev, [runId]: res.data.files }));
      }
    } catch (err) {
      console.warn(`[notebook] Failed to load artifacts for run ${runId}:`, err);
    } finally {
      setArtifactsLoading((prev) => ({ ...prev, [runId]: false }));
    }
  };

  const handleRegisterModel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registeringRunId || !regModelName.trim()) return;
    setRegSubmitting(true);
    setRegFeedback(null);
    try {
      const res = await api.post('/notebook/experiments/models/register', {
        run_id: registeringRunId,
        model_name: regModelName.trim(),
        artifact_path: regArtifactPath.trim() || 'model',
        description: regDescription.trim(),
      });
      setRegFeedback({
        success: true,
        message: `Successfully registered version ${res.data?.version || '1'} of '${regModelName.trim()}'!`,
      });
      fetchModels(false);
      setTimeout(() => {
        setRegisteringRunId(null);
        setRegFeedback(null);
        setRegModelName('');
        setRegDescription('');
      }, 1800);
    } catch (err: any) {
      setRegFeedback({
        success: false,
        message: err.response?.data?.detail || err.message || 'Failed to register model',
      });
    } finally {
      setRegSubmitting(false);
    }
  };

  useEffect(() => {
    fetchRuns(true);
    fetchModels(false);
  }, [fetchRuns, fetchModels]);

  // Polling every 7 seconds when panel is open
  useEffect(() => {
    const timer = setInterval(() => {
      if (activeTab === 'runs') {
        fetchRuns(false);
      } else {
        fetchModels(false);
      }
    }, 7000);
    return () => clearInterval(timer);
  }, [fetchRuns, fetchModels, activeTab]);

  const toggleRunExpanded = (runId: string) => {
    setExpandedRuns((prev) => ({ ...prev, [runId]: !prev[runId] }));
  };

  const runs = runsData?.runs || [];
  const filteredRuns = runs.filter((r) => {
    if (!searchFilter.trim()) return true;
    const term = searchFilter.toLowerCase();
    return (
      r.run_name.toLowerCase().includes(term) ||
      r.run_id.toLowerCase().includes(term) ||
      Object.keys(r.params).some((k) => k.toLowerCase().includes(term) || r.params[k].toLowerCase().includes(term)) ||
      Object.keys(r.metrics).some((k) => k.toLowerCase().includes(term))
    );
  });

  const models = modelsData?.models || [];
  const filteredModels = models.filter((m) => {
    if (!modelsSearch.trim()) return true;
    const term = modelsSearch.toLowerCase();
    return (
      m.name.toLowerCase().includes(term) ||
      (m.description && m.description.toLowerCase().includes(term)) ||
      m.latest_versions.some((v) => v.current_stage?.toLowerCase().includes(term) || v.aliases?.some((a) => a.toLowerCase().includes(term)))
    );
  });

  const sampleSnippet = `import mlflow

with mlflow.start_run():
    mlflow.log_param("learning_rate", 0.01)
    mlflow.log_metric("accuracy", 0.94)`;

  const handleCopySnippet = () => {
    navigator.clipboard.writeText(sampleSnippet);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  if (!notebookPath) {
    return (
      <div className="dbx-config-empty">
        <div className="dbx-config-empty-icon">
          <FlaskConical size={24} />
        </div>
        <h4 className="dbx-config-empty-title">No Notebook Loaded</h4>
        <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>
          Open a notebook to view associated MLflow experiment runs and registered models.
        </p>
      </div>
    );
  }

  const isConnected = runsData?.connected !== false && modelsData?.connected !== false;

  return (
    <div className="dbx-config-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ── Subheader Controls ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
          <FlaskConical size={14} style={{ color: '#1b6ef3', flexShrink: 0 }} />
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#1e293b', whiteSpace: 'nowrap' }}>
            MLflow Tracking
          </span>
          {runsData?.experiment && (
            <span
              style={{
                fontSize: '10px',
                background: '#e0f2fe',
                color: '#0369a1',
                padding: '1px 6px',
                borderRadius: '999px',
                fontWeight: 600,
              }}
              title={`Experiment ID: ${runsData.experiment.experiment_id}`}
            >
              ID: {runsData.experiment.experiment_id}
            </span>
          )}
          <span
            style={{
              fontSize: '10px',
              background: '#f0fdf4',
              color: '#166534',
              border: '1px solid #bbf7d0',
              padding: '1px 5px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
              fontWeight: 500,
            }}
            title="Autologging is automatically active for Python kernels"
          >
            <Sparkles size={10} />
            <span>Autolog</span>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            type="button"
            onClick={() => {
              if (activeTab === 'runs') fetchRuns(true);
              else fetchModels(true);
            }}
            className="dbx-btn-icon"
            title="Refresh"
            disabled={runsLoading || modelsLoading}
            style={{
              padding: '4px 6px',
              borderRadius: '4px',
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              cursor: 'pointer',
              color: '#475569',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <RefreshCw size={12} className={runsLoading || modelsLoading ? 'animate-spin' : ''} />
          </button>

          {runsData?.ui_url && (
            <a
              href={runsData.ui_url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                padding: '4px 8px',
                borderRadius: '4px',
                background: '#1b6ef3',
                color: '#ffffff',
                textDecoration: 'none',
                fontWeight: 500,
              }}
              title="Open MLflow UI in new tab"
            >
              <span>Open MLflow</span>
              <ExternalLink size={11} />
            </a>
          )}
        </div>
      </div>

      {/* ── Tabs (Runs vs Models) ── */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid #e2e8f0',
          background: '#ffffff',
          padding: '0 8px',
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab('runs')}
          style={{
            flex: 1,
            padding: '8px 12px',
            fontSize: '12px',
            fontWeight: activeTab === 'runs' ? 600 : 500,
            color: activeTab === 'runs' ? '#1b6ef3' : '#64748b',
            border: 'none',
            borderBottom: activeTab === 'runs' ? '2px solid #1b6ef3' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <Layers size={13} />
          <span>Runs</span>
          <span
            style={{
              fontSize: '10px',
              background: activeTab === 'runs' ? '#eff6ff' : '#f1f5f9',
              color: activeTab === 'runs' ? '#1d4ed8' : '#64748b',
              padding: '1px 6px',
              borderRadius: '999px',
            }}
          >
            {runs.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab('models');
            if (!modelsData) fetchModels(true);
          }}
          style={{
            flex: 1,
            padding: '8px 12px',
            fontSize: '12px',
            fontWeight: activeTab === 'models' ? 600 : 500,
            color: activeTab === 'models' ? '#1b6ef3' : '#64748b',
            border: 'none',
            borderBottom: activeTab === 'models' ? '2px solid #1b6ef3' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
          }}
        >
          <Package size={13} />
          <span>Model Registry</span>
          <span
            style={{
              fontSize: '10px',
              background: activeTab === 'models' ? '#eff6ff' : '#f1f5f9',
              color: activeTab === 'models' ? '#1d4ed8' : '#64748b',
              padding: '1px 6px',
              borderRadius: '999px',
            }}
          >
            {models.length}
          </span>
        </button>
      </div>

      {/* ── Disconnected / Error Alert ── */}
      {!isConnected && (
        <div
          style={{
            margin: '10px 14px',
            padding: '8px 12px',
            background: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#b45309',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
          }}
        >
          <AlertCircle size={15} style={{ marginTop: '2px', flexShrink: 0 }} />
          <div>
            <div style={{ fontWeight: 600 }}>MLflow Not Reachable</div>
            <div style={{ fontSize: '11px', marginTop: '2px' }}>
              {runsData?.message || modelsData?.message || 'Start the MLflow service using compassx up to enable ambient tracking.'}
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 1: RUNS
      ───────────────────────────────────────────────────────────── */}
      {activeTab === 'runs' && (
        <>
          {/* Search Bar */}
          {runs.length > 0 && (
            <div style={{ padding: '8px 14px', borderBottom: '1px solid #f1f5f9' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  padding: '4px 8px',
                }}
              >
                <Search size={13} style={{ color: '#94a3b8' }} />
                <input
                  type="text"
                  placeholder="Filter runs by name, param, metric..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    outline: 'none',
                    fontSize: '12px',
                    width: '100%',
                    color: '#1e293b',
                  }}
                />
              </div>
            </div>
          )}

          {/* Runs Feed */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
            {runs.length === 0 ? (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '28px 12px',
                  textAlign: 'center',
                  gap: '12px',
                }}
              >
                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '8px',
                    background: '#f1f5f9',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#64748b',
                  }}
                >
                  <FlaskConical size={22} />
                </div>

                <div>
                  <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: '#1e293b' }}>
                    No Runs Tracked Yet
                  </h4>
                  <p style={{ margin: '4px 0 0 0', fontSize: '11px', color: '#64748b', maxWidth: '280px' }}>
                    This notebook is linked to its own experiment. Execute any cell using <code>mlflow.start_run()</code> or autologging to see live runs here.
                  </p>
                </div>

                <div
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: '#0f172a',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    position: 'relative',
                    marginTop: '4px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '6px',
                      borderBottom: '1px solid #334155',
                      paddingBottom: '4px',
                    }}
                  >
                    <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>QUICKSTART</span>
                    <button
                      type="button"
                      onClick={handleCopySnippet}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: copiedSnippet ? '#34d399' : '#94a3b8',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '10px',
                      }}
                      title="Copy code snippet"
                    >
                      {copiedSnippet ? <Check size={11} /> : <Copy size={11} />}
                      <span>{copiedSnippet ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      color: '#e2e8f0',
                      lineHeight: '1.4',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {sampleSnippet}
                  </pre>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: '#64748b' }}>
                  <span>Showing {filteredRuns.length} of {runs.length} runs</span>
                  <span>Sorted by start time</span>
                </div>

                {filteredRuns.map((run) => {
                  const isExpanded = !!expandedRuns[run.run_id];
                  const isFinished = run.status === 'FINISHED';
                  const isRunning = run.status === 'RUNNING';
                  const isFailed = run.status === 'FAILED';

                  const metricsKeys = Object.keys(run.metrics);
                  const paramsKeys = Object.keys(run.params);
                  const isArtifactsOpen = !!expandedArtifacts[run.run_id];
                  const artifacts = artifactsMap[run.run_id] || [];

                  return (
                    <div
                      key={run.run_id}
                      style={{
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px',
                        background: '#ffffff',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        transition: 'border-color 0.12s',
                      }}
                    >
                      {/* Run Card Header */}
                      <div
                        onClick={() => toggleRunExpanded(run.run_id)}
                        style={{
                          padding: '10px 12px',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                            {isExpanded ? <ChevronDown size={14} style={{ color: '#64748b' }} /> : <ChevronRight size={14} style={{ color: '#64748b' }} />}
                            
                            {isFinished && <CheckCircle2 size={13} style={{ color: '#10b981', flexShrink: 0 }} />}
                            {isRunning && <RefreshCw size={13} className="animate-spin" style={{ color: '#3b82f6', flexShrink: 0 }} />}
                            {isFailed && <AlertCircle size={13} style={{ color: '#ef4444', flexShrink: 0 }} />}
                            {!isFinished && !isRunning && !isFailed && <Clock size={13} style={{ color: '#94a3b8', flexShrink: 0 }} />}

                            <span
                              style={{
                                fontSize: '12px',
                                fontWeight: 600,
                                color: '#0f172a',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                              title={run.run_name}
                            >
                              {run.run_name}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 600,
                                padding: '1px 6px',
                                borderRadius: '4px',
                                background: isFinished ? '#ecfdf5' : isRunning ? '#eff6ff' : isFailed ? '#fef2f2' : '#f1f5f9',
                                color: isFinished ? '#047857' : isRunning ? '#1d4ed8' : isFailed ? '#b91c1c' : '#475569',
                              }}
                            >
                              {run.status}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: '#64748b' }}>
                          <span>{formatRelativeTime(run.start_time)}</span>
                          <span>Duration: {formatDuration(run.duration_ms)}</span>
                        </div>

                        {/* Quick Metrics Badges Preview */}
                        {metricsKeys.length > 0 && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '2px' }}>
                            {metricsKeys.slice(0, 3).map((k) => (
                              <span
                                key={k}
                                style={{
                                  fontSize: '10px',
                                  background: '#f8fafc',
                                  border: '1px solid #e2e8f0',
                                  borderRadius: '4px',
                                  padding: '1px 5px',
                                  color: '#334155',
                                }}
                              >
                                <strong>{k}:</strong> {typeof run.metrics[k] === 'number' ? run.metrics[k].toFixed(4).replace(/\.?0+$/, '') : run.metrics[k]}
                              </span>
                            ))}
                            {metricsKeys.length > 3 && (
                              <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                                +{metricsKeys.length - 3} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Expanded Run Details */}
                      {isExpanded && (
                        <div
                          style={{
                            padding: '10px 12px',
                            borderTop: '1px solid #f1f5f9',
                            background: '#f8fafc',
                            borderBottomLeftRadius: '6px',
                            borderBottomRightRadius: '6px',
                            fontSize: '11px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                          }}
                        >
                          {/* Parameters Section */}
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                              <Sliders size={12} />
                              <span>Parameters ({paramsKeys.length})</span>
                            </div>
                            {paramsKeys.length === 0 ? (
                              <div style={{ color: '#94a3b8', fontStyle: 'italic' }}>No parameters logged</div>
                            ) : (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {paramsKeys.map((p) => (
                                  <span
                                    key={p}
                                    style={{
                                      background: '#ffffff',
                                      border: '1px solid #cbd5e1',
                                      borderRadius: '4px',
                                      padding: '1px 6px',
                                      color: '#1e293b',
                                    }}
                                  >
                                    {p}: <code>{run.params[p]}</code>
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* All Metrics Section */}
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                              <BarChart3 size={12} />
                              <span>Metrics ({metricsKeys.length})</span>
                            </div>
                            {metricsKeys.length === 0 ? (
                              <div style={{ color: '#94a3b8', fontStyle: 'italic' }}>No metrics logged</div>
                            ) : (
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '4px' }}>
                                {metricsKeys.map((m) => (
                                  <div
                                    key={m}
                                    style={{
                                      background: '#ffffff',
                                      border: '1px solid #cbd5e1',
                                      borderRadius: '4px',
                                      padding: '3px 6px',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                    }}
                                  >
                                    <span style={{ color: '#64748b' }}>{m}</span>
                                    <span style={{ fontWeight: 600, color: '#0f172a' }}>{run.metrics[m]}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Artifacts Explorer Accordion */}
                          <div>
                            <div
                              onClick={() => fetchArtifacts(run.run_id)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                cursor: 'pointer',
                                padding: '4px 6px',
                                background: '#f1f5f9',
                                borderRadius: '4px',
                                fontWeight: 600,
                                color: '#334155',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <Box size={12} />
                                <span>Artifacts & Models</span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                {artifactsLoading[run.run_id] && <RefreshCw size={11} className="animate-spin" />}
                                {isArtifactsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                              </div>
                            </div>

                            {isArtifactsOpen && (
                              <div style={{ marginTop: '4px', paddingLeft: '4px' }}>
                                {artifacts.length === 0 && !artifactsLoading[run.run_id] ? (
                                  <div style={{ color: '#94a3b8', fontStyle: 'italic', padding: '4px 0' }}>
                                    No artifacts logged for this run
                                  </div>
                                ) : (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                    {artifacts.map((f) => (
                                      <div
                                        key={f.path}
                                        style={{
                                          display: 'flex',
                                          alignItems: 'center',
                                          justifyContent: 'space-between',
                                          padding: '2px 4px',
                                          fontSize: '10px',
                                          color: '#334155',
                                        }}
                                      >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                          {f.is_dir ? <Folder size={11} style={{ color: '#3b82f6' }} /> : <FileText size={11} style={{ color: '#64748b' }} />}
                                          <span>{f.path}</span>
                                        </div>
                                        {f.file_size !== undefined && (
                                          <span style={{ color: '#94a3b8' }}>{formatBytes(f.file_size)}</span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>

                          {/* Footer Actions: Register Model & MLflow UI */}
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              marginTop: '4px',
                              paddingTop: '6px',
                              borderTop: '1px solid #e2e8f0',
                            }}
                          >
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setRegisteringRunId(run.run_id);
                                setRegModelName(run.run_name.replace(/[^a-zA-Z0-9_\-]/g, '_'));
                              }}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                fontSize: '10px',
                                fontWeight: 600,
                                borderRadius: '4px',
                                background: '#f0fdf4',
                                border: '1px solid #86efac',
                                color: '#166534',
                                cursor: 'pointer',
                              }}
                              title="Register model from this run into the MLflow Model Registry"
                            >
                              <Package size={11} />
                              <span>Register Model</span>
                            </button>

                            <a
                              href={run.ui_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                color: '#1b6ef3',
                                textDecoration: 'none',
                                fontWeight: 500,
                                fontSize: '11px',
                              }}
                            >
                              <span>View in MLflow UI</span>
                              <ExternalLink size={11} />
                            </a>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 2: MODEL REGISTRY
      ───────────────────────────────────────────────────────────── */}
      {activeTab === 'models' && (
        <>
          {/* Models Search Bar */}
          <div style={{ padding: '8px 14px', borderBottom: '1px solid #f1f5f9' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                padding: '4px 8px',
              }}
            >
              <Search size={13} style={{ color: '#94a3b8' }} />
              <input
                type="text"
                placeholder="Search registered models, stages, aliases..."
                value={modelsSearch}
                onChange={(e) => setModelsSearch(e.target.value)}
                style={{
                  border: 'none',
                  background: 'transparent',
                  outline: 'none',
                  fontSize: '12px',
                  width: '100%',
                  color: '#1e293b',
                }}
              />
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
            {filteredModels.length === 0 ? (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '36px 12px',
                  textAlign: 'center',
                  gap: '10px',
                }}
              >
                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '8px',
                    background: '#f1f5f9',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#64748b',
                  }}
                >
                  <Package size={22} />
                </div>
                <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: '#1e293b' }}>
                  No Registered Models Yet
                </h4>
                <p style={{ margin: 0, fontSize: '11px', color: '#64748b', maxWidth: '280px' }}>
                  Register models directly from your experiment runs in the <b>Runs</b> tab or use <code>mlflow.register_model()</code>.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {filteredModels.map((m) => (
                  <div
                    key={m.name}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '6px',
                      background: '#ffffff',
                      padding: '10px 12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Package size={14} style={{ color: '#1b6ef3' }} />
                        <span style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>{m.name}</span>
                      </div>

                      {m.ui_url && (
                        <a
                          href={m.ui_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px',
                            color: '#1b6ef3',
                            fontSize: '11px',
                            textDecoration: 'none',
                          }}
                        >
                          <span>Registry UI</span>
                          <ExternalLink size={10} />
                        </a>
                      )}
                    </div>

                    {m.description && (
                      <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>{m.description}</p>
                    )}

                    {/* Versions list */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                      <span style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>LATEST VERSIONS</span>
                      {m.latest_versions.map((v) => (
                        <div
                          key={v.version}
                          style={{
                            background: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            fontSize: '11px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ fontWeight: 600, color: '#1e293b' }}>v{v.version}</span>
                            {v.current_stage && v.current_stage !== 'None' && (
                              <span
                                style={{
                                  fontSize: '9px',
                                  padding: '1px 5px',
                                  borderRadius: '3px',
                                  background: v.current_stage === 'Production' ? '#ecfdf5' : '#eff6ff',
                                  color: v.current_stage === 'Production' ? '#047857' : '#1d4ed8',
                                  fontWeight: 600,
                                }}
                              >
                                {v.current_stage}
                              </span>
                            )}
                            {v.aliases && v.aliases.map((a) => (
                              <span
                                key={a}
                                style={{
                                  fontSize: '9px',
                                  padding: '1px 5px',
                                  borderRadius: '3px',
                                  background: '#fef3c7',
                                  color: '#92400e',
                                  fontWeight: 600,
                                }}
                              >
                                @{a}
                              </span>
                            ))}
                          </div>

                          <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                            {formatRelativeTime(v.creation_timestamp || null)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ─────────────────────────────────────────────────────────────
          REGISTER MODEL MODAL / DIALOG
      ───────────────────────────────────────────────────────────── */}
      {registeringRunId && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 50,
            padding: '16px',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '8px',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
              width: '100%',
              maxWidth: '340px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Package size={16} style={{ color: '#166534' }} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>Register Model</span>
              </div>
              <button
                type="button"
                onClick={() => setRegisteringRunId(null)}
                style={{
                  border: 'none',
                  background: 'transparent',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  fontSize: '14px',
                }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRegisterModel} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#334155', marginBottom: '3px' }}>
                  Model Name *
                </label>
                <input
                  type="text"
                  required
                  value={regModelName}
                  onChange={(e) => setRegModelName(e.target.value)}
                  placeholder="e.g. churn_classifier"
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    border: '1px solid #cbd5e1',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#334155', marginBottom: '3px' }}>
                  Artifact Subpath
                </label>
                <input
                  type="text"
                  value={regArtifactPath}
                  onChange={(e) => setRegArtifactPath(e.target.value)}
                  placeholder="model"
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    border: '1px solid #cbd5e1',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
                <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                  Subpath under run artifacts (defaults to <code>model</code>).
                </span>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#334155', marginBottom: '3px' }}>
                  Description (optional)
                </label>
                <textarea
                  rows={2}
                  value={regDescription}
                  onChange={(e) => setRegDescription(e.target.value)}
                  placeholder="Production candidate trained on latest quarterly dataset"
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    border: '1px solid #cbd5e1',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                    resize: 'none',
                  }}
                />
              </div>

              {regFeedback && (
                <div
                  style={{
                    padding: '6px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    background: regFeedback.success ? '#ecfdf5' : '#fef2f2',
                    color: regFeedback.success ? '#047857' : '#b91c1c',
                    border: `1px solid ${regFeedback.success ? '#86efac' : '#fca5a5'}`,
                  }}
                >
                  {regFeedback.message}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', marginTop: '4px' }}>
                <button
                  type="button"
                  onClick={() => setRegisteringRunId(null)}
                  style={{
                    padding: '5px 10px',
                    borderRadius: '4px',
                    border: '1px solid #cbd5e1',
                    background: '#ffffff',
                    fontSize: '11px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={regSubmitting || !regModelName.trim()}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '4px',
                    border: 'none',
                    background: '#166534',
                    color: '#ffffff',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {regSubmitting && <RefreshCw size={11} className="animate-spin" />}
                  <span>{regSubmitting ? 'Registering...' : 'Register'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
