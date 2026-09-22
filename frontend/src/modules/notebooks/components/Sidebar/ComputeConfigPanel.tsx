import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  ChevronUp,
  ChevronDown,
  ExternalLink,
  Folder,
  Trash2,
  Plus,
  Check,
  MoreVertical,
  RotateCcw,
  Square,
  Play,
  Loader2,
  AlertTriangle,
  Layers,
  FileCode,
  Zap,
  Server,
  RefreshCw,
  Search,
} from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import api from '@/lib/api';
import { useNotebookStore } from '../../store/notebookStore';
import type { SelectedPod } from '../../store/notebookStore';
import type { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';
import { useAccountSettings } from '@/lib/accountSettingsApi';

interface ComputeResourceDetails {
  id: string;
  name: string;
  runtime: string;
  profile: string;
  phase?: string;
  desired_status?: string;
  custom_image?: string | null;
  extra_env?: string | null;
  pod_name?: string | null;
  message?: string | null;
  is_default?: boolean;
}

interface InstalledPackage {
  name: string;
  version: string;
}

const RUNTIME_OPTIONS = [
  { id: 'duckdb', label: 'DuckDB (SQL & Analytics)', version: 'DuckDB 0.10 • Python 3.12' },
  { id: 'spark', label: 'Apache Spark (Distributed)', version: 'Spark 3.5 • Python 3.12' },
  { id: 'ray', label: 'Ray (AI & Machine Learning)', version: 'Ray 2.35 • Python 3.12' },
  { id: 'flink', label: 'Apache Flink (Streaming)', version: 'Flink 1.18 • Python 3.12' },
];

export interface MemoryProfileOption {
  id: string;
  label: string;
  raw: string;
  ramGb: number;
  cpuLimit: string;
  cpuRequest: string;
  ramLimit: string;
  ramRequest: string;
}

const MEMORY_PROFILES: MemoryProfileOption[] = [
  {
    id: 'local',
    label: 'Small (2GB • 1 vCPU)',
    raw: 'local',
    ramGb: 2,
    cpuLimit: '1 vCPU',
    cpuRequest: '250m',
    ramLimit: '2 GB',
    ramRequest: '512 MB',
  },
  {
    id: 'cloud-s',
    label: 'Medium (4GB • 2 vCPU)',
    raw: 'cloud-s',
    ramGb: 4,
    cpuLimit: '2 vCPU',
    cpuRequest: '1 vCPU',
    ramLimit: '4 GB',
    ramRequest: '2 GB',
  },
  {
    id: 'cloud-l',
    label: 'Standard (16GB • 4 vCPU)',
    raw: 'cloud-l',
    ramGb: 16,
    cpuLimit: '4 vCPU',
    cpuRequest: '2 vCPU',
    ramLimit: '16 GB',
    ramRequest: '8 GB',
  },
  {
    id: 'heavy',
    label: 'Large (64GB • 8 vCPU)',
    raw: 'cloud-l',
    ramGb: 64,
    cpuLimit: '8 vCPU',
    cpuRequest: '4 vCPU',
    ramLimit: '64 GB',
    ramRequest: '32 GB',
  },
  {
    id: 'gpu',
    label: 'GPU (32GB • 4 vCPU • NVIDIA Dedicated)',
    raw: 'gpu',
    ramGb: 32,
    cpuLimit: '4 vCPU',
    cpuRequest: '4 vCPU',
    ramLimit: '32 GB (1 GPU)',
    ramRequest: '16 GB',
  },
];

export default function ComputeConfigPanel() {
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const setSelectedPod = useNotebookStore((s) => s.setSelectedPod);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const notebookId = useNotebookStore((s) => s.notebookId);
  const setActiveRightSidebarTab = useNotebookStore((s) => s.setActiveRightSidebarTab);

  const { data: accountData } = useAccountSettings();
  const computeSettings = accountData?.settings?.compute;
  const vmCapacityGib = computeSettings?.vm_capacity_gib ?? (
    computeSettings?.vm_size?.includes('B2s') || computeSettings?.vm_size?.includes('B2als') ? 4 :
    computeSettings?.vm_size?.includes('D2s') ? 8 :
    computeSettings?.vm_size?.includes('D8s') || computeSettings?.vm_size?.includes('E4s') ? 32 :
    computeSettings?.vm_size?.includes('D16s') || computeSettings?.vm_size?.includes('E8s') ? 64 : 16
  );
  const currentVmName = computeSettings?.vm_size || 'Standard_D4s_v5';

  const [resource, setResource] = useState<ComputeResourceDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Accordion section collapse state
  const [hardwareOpen, setHardwareOpen] = useState(true);
  const [envOpen, setEnvOpen] = useState(true);

  // Form selections
  const [selectedProfile, setSelectedProfile] = useState('local');
  const [selectedRuntime, setSelectedRuntime] = useState('duckdb');
  const [depTab, setDepTab] = useState<'added' | 'installed'>('added');

  // Dependencies / Pip requirements list
  const [dependencies, setDependencies] = useState<string[]>([
    'simplejson==3.19.*',
    '-r requirements.txt',
  ]);
  const [newDepInput, setNewDepInput] = useState('');
  const [showAddDep, setShowAddDep] = useState(false);

  // Live Installed packages from kernel
  const [installedPackages, setInstalledPackages] = useState<InstalledPackage[]>([]);
  const [loadingPackages, setLoadingPackages] = useState(false);
  const [packageSearch, setPackageSearch] = useState('');

  // More options context menu
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [isApplying, setIsApplying] = useState(false);

  // Fetch installed packages from active kernel
  const fetchInstalledPackages = useCallback(() => {
    const kernel = kernelRef as IKernelConnection | null;
    if (!kernel || kernelStatus === 'dead' || kernelStatus === 'unknown') {
      return;
    }
    setLoadingPackages(true);
    const code = `
try:
    import importlib.metadata as _im, json as _js
    _dists = sorted([{"name": _d.metadata["Name"], "version": _d.version} for _d in _im.distributions() if _d.metadata and _d.metadata.get("Name")], key=lambda x: str(x["name"]).lower())
    print("__COMPASSX_PKGS__" + _js.dumps(_dists))
except Exception as _e:
    print("__COMPASSX_PKGS_ERR__" + str(_e))
`;
    const future = kernel.requestExecute({ code, store_history: false, silent: true });
    let rawOutput = '';
    future.onIOPub = (msg) => {
      if (msg.header.msg_type === 'stream') {
        const text = ((msg.content as any)?.text as string) || '';
        rawOutput += text;
        if (rawOutput.includes('__COMPASSX_PKGS__')) {
          const jsonStr = rawOutput.split('__COMPASSX_PKGS__')[1]?.trim();
          if (jsonStr) {
            try {
              const parsed = JSON.parse(jsonStr);
              if (Array.isArray(parsed)) {
                setInstalledPackages(parsed);
              }
            } catch {}
          }
        }
      }
    };
    future.done.finally(() => {
      setLoadingPackages(false);
    });
  }, [kernelRef, kernelStatus]);

  // Trigger fetch when user opens installed tab or when kernel is connected
  useEffect(() => {
    if (depTab === 'installed' && kernelRef && installedPackages.length === 0) {
      fetchInstalledPackages();
    }
  }, [depTab, kernelRef, fetchInstalledPackages, installedPackages.length]);

  // Close context menu on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    }
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  // Load resource details when selectedPod changes and poll while pending
  useEffect(() => {
    if (!selectedPod?.resource_id) {
      setResource(null);
      return;
    }

    let isCancelled = false;
    let pollTimer: any = null;

    const fetchStatus = (isInitial = false) => {
      if (isInitial) setLoading(true);
      computeApi
        .getResourceStatus(selectedPod.resource_id)
        .then((data: any) => {
          if (isCancelled) return;
          setResource(data);
          if (isInitial) {
            setSelectedRuntime(data.runtime || 'duckdb');
            setSelectedProfile(data.profile || 'local');
          }
          if (data?.phase === 'Pending' || data?.phase === 'Creating' || selectedPod?.state === 'starting') {
            pollTimer = setTimeout(() => fetchStatus(false), 3000);
          }
        })
        .catch((err: any) => {
          if (isCancelled) return;
          if (isInitial) {
            setError(err?.response?.data?.message ?? 'Failed to load compute resource details');
          }
        })
        .finally(() => {
          if (!isCancelled && isInitial) setLoading(false);
        });
    };

    fetchStatus(true);

    return () => {
      isCancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [selectedPod?.resource_id, selectedPod?.state]);

  const hasChanges =
    resource !== null &&
    (selectedRuntime !== resource.runtime || selectedProfile !== resource.profile);

  // Apply changes & re-provision
  async function handleApplyChanges() {
    if (!resource) return;
    setIsApplying(true);
    setStatusMessage('Applying compute changes & restarting container...');
    setError(null);

    try {
      await computeApi.updateResource(resource.id, {
        name: resource.name,
        runtime: selectedRuntime,
        profile: selectedProfile,
      });

      const res = await computeApi.ensureResourceRunningAndStartKernel(resource.id, (msg: string) => {
        setStatusMessage(msg);
      });

      const updatedPod: SelectedPod = {
        resource_id: resource.id,
        runtime_id: resource.id,
        runtime: selectedRuntime,
        kernel_id: res.kernel.id,
        kernel_name: res.kernel.name || res.kernel.id,
        state: 'connected',
      };
      setSelectedPod(updatedPod);

      if (notebookId) {
        api.put(`/notebook/${notebookId}/compute`, {
          resource_id: resource.id,
          kernel_name: res.kernel.name || res.kernel.id,
        }).catch(() => {});
      }

      setResource((prev) => (prev ? { ...prev, runtime: selectedRuntime, profile: selectedProfile } : prev));
      setStatusMessage(null);
    } catch (err: any) {
      setError(err?.response?.data?.message ?? err?.message ?? 'Failed to apply compute updates.');
    } finally {
      setIsApplying(false);
    }
  }

  const isLocalProfile = selectedProfile === 'local' || resource?.profile === 'local';
  const computeUnitName = isLocalProfile ? 'Container' : 'Pod';

  // Quick Action Handlers
  async function handleStartCompute() {
    if (!resource) return;
    setActionLoading(true);
    setStatusMessage(`Starting compute ${computeUnitName.toLowerCase()}...`);
    setError(null);
    try {
      const res = await computeApi.ensureResourceRunningAndStartKernel(resource.id, (msg: string) => {
        setStatusMessage(msg);
      });
      setSelectedPod({
        resource_id: resource.id,
        runtime_id: resource.id,
        runtime: resource.runtime,
        kernel_id: res.kernel.id,
        kernel_name: res.kernel.name || res.kernel.id,
        state: 'connected',
      });
      setResource((prev) => (prev ? { ...prev, phase: 'Running', desired_status: 'running' } : prev));
    } catch (err: any) {
      setError(err?.response?.data?.message ?? `Failed to start ${computeUnitName.toLowerCase()}.`);
    } finally {
      setActionLoading(false);
      setStatusMessage(null);
    }
  }

  async function handleStopCompute() {
    if (!resource) return;
    setActionLoading(true);
    setStatusMessage(`Killing ${computeUnitName.toLowerCase()}...`);
    setError(null);
    try {
      await computeApi.stopResource(resource.id);
      setSelectedPod({
        ...selectedPod!,
        state: 'starting',
        kernel_id: null,
      });
      setResource((prev) => (prev ? { ...prev, phase: 'Stopped', desired_status: 'stopped' } : prev));
    } catch (err: any) {
      setError(err?.response?.data?.message ?? `Failed to kill ${computeUnitName.toLowerCase()}.`);
    } finally {
      setActionLoading(false);
      setStatusMessage(null);
    }
  }

  function handleRestartKernel() {
    if (kernelRef) {
      kernelRef.restart();
    }
  }

  function handleDetach() {
    setSelectedPod(null);
  }

  function handleAddDependency() {
    if (newDepInput.trim()) {
      setDependencies((prev) => [...prev, newDepInput.trim()]);
      setNewDepInput('');
      setShowAddDep(false);
    }
  }

  function handleRemoveDependency(index: number) {
    setDependencies((prev) => prev.filter((_, i) => i !== index));
  }

  const selectedRuntimeObj = RUNTIME_OPTIONS.find((r) => r.id === selectedRuntime) || RUNTIME_OPTIONS[0];

  const filteredPackages = installedPackages.filter(
    (p) =>
      p.name.toLowerCase().includes(packageSearch.toLowerCase()) ||
      p.version.toLowerCase().includes(packageSearch.toLowerCase())
  );

  return (
    <div className="dbx-config-container">
      {loading ? (
        <div className="dbx-config-loading">
          <Loader2 size={18} className="notebook-pod-spinner" />
          <span>Loading configuration...</span>
        </div>
      ) : !selectedPod ? (
        <div className="dbx-config-empty">
          <div className="dbx-config-empty-icon">
            <Server size={32} />
          </div>
          <h4 className="dbx-config-empty-title">No Compute Attached</h4>
          <p className="dbx-config-empty-desc">
            Attach to Serverless Compute or a dedicated pod to configure hardware and runtime environment.
          </p>
          <button
            type="button"
            className="dbx-btn-primary"
            onClick={async () => {
              setActionLoading(true);
              setError(null);
              setStatusMessage('Provisioning Serverless DuckDB...');
              try {
                const currentNotebookId = useNotebookStore.getState().notebookId;
                const currentMetadata = useNotebookStore.getState().notebookMetadata;
                const notebookName = currentMetadata?.name || undefined;
                const serverless = await computeApi.ensureServerlessCompute(currentNotebookId || undefined, notebookName);
                setSelectedPod({
                  resource_id: serverless.id,
                  runtime_id: serverless.runtime_id ?? serverless.id,
                  runtime: serverless.runtime || 'duckdb',
                  kernel_id: null,
                  kernel_name: null,
                  state: 'starting',
                });
                const res = await computeApi.ensureResourceRunningAndStartKernel(serverless.id, (msg: string) => {
                  setStatusMessage(msg);
                });
                setSelectedPod({
                  resource_id: serverless.id,
                  runtime_id: serverless.runtime_id ?? serverless.id,
                  runtime: serverless.runtime || 'duckdb',
                  kernel_id: res.kernel.id,
                  kernel_name: res.kernel.name || res.kernel.id,
                  state: 'connected',
                });
                const notebookId = useNotebookStore.getState().notebookId;
                if (notebookId) {
                  api.put(`/notebook/${notebookId}/compute`, {
                    resource_id: serverless.id,
                    kernel_name: res.kernel.name || res.kernel.id,
                  }).catch(() => {});
                }
              } catch (err: any) {
                setError(err?.response?.data?.message ?? err?.message ?? 'Failed to attach serverless');
                setSelectedPod(null);
              } finally {
                setActionLoading(false);
                setStatusMessage(null);
              }
            }}
            disabled={actionLoading}
          >
            {actionLoading ? <Loader2 size={13} className="notebook-pod-spinner" /> : <Zap size={13} />}
            <span>Attach Serverless (DuckDB)</span>
          </button>
        </div>
      ) : (
        <div className="dbx-config-form">
          {/* Status & Error Alerts */}
          {statusMessage && (
            <div className="dbx-alert dbx-alert--info">
              <Loader2 size={13} className="notebook-pod-spinner" />
              <span>{statusMessage}</span>
            </div>
          )}
          {error && (
            <div className="dbx-alert dbx-alert--error">
              <AlertTriangle size={13} />
              <span>{error}</span>
            </div>
          )}

          {/* ── Section 0: Compute Lifecycle & Cost Optimization ── */}
          <div className="dbx-lifecycle-card">
            <div className="dbx-lifecycle-row">
              <div className="dbx-lifecycle-badge">
                <span
                  className={`dbx-lifecycle-dot ${
                    resource?.phase === 'Running'
                      ? 'is-running'
                      : resource?.phase === 'Stopped'
                      ? 'is-stopped'
                      : 'is-pending'
                  }`}
                />
                <span>
                  {computeUnitName}: {resource?.phase || (selectedPod ? 'Running' : 'Stopped')}
                </span>
              </div>
              {resource?.phase === 'Stopped' ? (
                <span style={{ fontSize: '10px', color: '#166534', fontWeight: 600, background: '#dcfce7', border: '1px solid #bbf7d0', padding: '1px 6px', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  $0 / hr • Scale to Zero
                </span>
              ) : (
                <span style={{ fontSize: '10.5px', color: '#64748b', fontWeight: 500 }}>
                  Active Compute
                </span>
              )}
            </div>

            <p className="dbx-lifecycle-desc">
              {resource?.phase === 'Stopped'
                ? `${computeUnitName} is stopped to conserve compute usage. Start compute when you want to execute cells.`
                : `Kill the running ${computeUnitName.toLowerCase()} to terminate active processes, release compute capacity, and trigger scale-to-zero autoscaling.`}
            </p>

            {resource?.phase === 'Stopped' ? (
              <button
                type="button"
                className="dbx-btn-start"
                onClick={handleStartCompute}
                disabled={actionLoading || isApplying}
                title={`Start ${computeUnitName.toLowerCase()}`}
              >
                {actionLoading ? <Loader2 size={13} className="notebook-pod-spinner" /> : <Play size={13} />}
                <span>Start {computeUnitName}</span>
              </button>
            ) : (
              <button
                type="button"
                className="dbx-btn-kill"
                onClick={handleStopCompute}
                disabled={actionLoading || isApplying}
                title={`Kill active ${computeUnitName.toLowerCase()} to save compute usage`}
              >
                {actionLoading ? <Loader2 size={13} className="notebook-pod-spinner" /> : <Square size={13} />}
                <span>Kill {computeUnitName} (Stop Compute)</span>
              </button>
            )}
          </div>

          {/* ── Section 1: Hardware ── */}
          <div className="dbx-accordion-section">
            <div
              className="dbx-accordion-header"
              onClick={() => setHardwareOpen(!hardwareOpen)}
              role="button"
              tabIndex={0}
            >
              <span className="dbx-accordion-title">Hardware</span>
              {hardwareOpen ? <ChevronUp size={15} className="dbx-accordion-icon" /> : <ChevronDown size={15} className="dbx-accordion-icon" />}
            </div>

            {hardwareOpen && (
              <div className="dbx-accordion-body">
                <div className="dbx-field-group">
                  <div className="dbx-field-label-row">
                    <label className="dbx-field-label" title="Memory & Sizing Profile">
                      Memory
                    </label>
                  </div>
                  <select
                    className="dbx-select"
                    value={selectedProfile}
                    onChange={(e) => setSelectedProfile(e.target.value)}
                  >
                    {MEMORY_PROFILES.map((prof) => {
                      const isExceeded = prof.ramGb > vmCapacityGib;
                      return (
                        <option key={prof.id} value={prof.raw} disabled={isExceeded}>
                          {prof.label} {isExceeded ? `(Locked • Exceeds ${vmCapacityGib}GB VM)` : ''}
                        </option>
                      );
                    })}
                  </select>
                  {(() => {
                    const activeProf = MEMORY_PROFILES.find((p) => p.raw === selectedProfile || p.id === selectedProfile) || MEMORY_PROFILES[0];
                    return (
                      <div style={{ marginTop: '6px', fontSize: '0.74rem', color: '#64748b', display: 'flex', flexDirection: 'column', gap: '3px', background: '#f8fafc', padding: '6px 8px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>Allocation Limit:</span>
                          <strong style={{ color: '#0f172a' }}>{activeProf.cpuLimit} • {activeProf.ramLimit}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>Guaranteed Request:</span>
                          <span style={{ color: '#475569' }}>{activeProf.cpuRequest} • {activeProf.ramRequest}</span>
                        </div>
                      </div>
                    );
                  })()}
                  <div style={{ marginTop: '6px', fontSize: '0.74rem', color: 'var(--color-text-muted)', lineHeight: '1.35' }}>
                    Constrained by <strong>{currentVmName}</strong> ({vmCapacityGib} GB RAM node pool). Upgrade in Account Settings to unlock higher tiers.
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="dbx-divider" />

          {/* ── Section 2: Environment ── */}
          <div className="dbx-accordion-section">
            <div
              className="dbx-accordion-header"
              onClick={() => setEnvOpen(!envOpen)}
              role="button"
              tabIndex={0}
            >
              <span className="dbx-accordion-title">Environment</span>
              {envOpen ? <ChevronUp size={15} className="dbx-accordion-icon" /> : <ChevronDown size={15} className="dbx-accordion-icon" />}
            </div>

            {envOpen && (
              <div className="dbx-accordion-body">
                {/* Base environment */}
                <div className="dbx-field-group">
                  <div className="dbx-field-label-row">
                    <label className="dbx-field-label" title="Base runtime container environment">
                      Base environment
                    </label>
                  </div>
                  <div className="dbx-select-with-action">
                    <select
                      className="dbx-select"
                      value={selectedRuntime}
                      onChange={(e) => setSelectedRuntime(e.target.value)}
                    >
                      {RUNTIME_OPTIONS.map((opt) => (
                        <option key={opt.id} value={opt.id}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="dbx-icon-link-btn"
                      title="Open environment logs"
                      onClick={() => setActiveRightSidebarTab('logs')}
                    >
                      <ExternalLink size={14} />
                    </button>
                  </div>
                  <div className="dbx-field-helper-text">{selectedRuntimeObj.version}</div>
                </div>

                {/* Dependencies */}
                <div className="dbx-field-group dbx-dependencies-group">
                  <div className="dbx-field-label-row">
                    <label className="dbx-field-label">Dependencies</label>
                  </div>

                  {/* Sub-tabs: Added / Installed */}
                  <div className="dbx-subtabs">
                    <button
                      type="button"
                      className={`dbx-subtab ${depTab === 'added' ? 'is-active' : ''}`}
                      onClick={() => setDepTab('added')}
                    >
                      Added
                    </button>
                    <button
                      type="button"
                      className={`dbx-subtab ${depTab === 'installed' ? 'is-active' : ''}`}
                      onClick={() => setDepTab('installed')}
                    >
                      Installed {installedPackages.length > 0 ? `(${installedPackages.length})` : ''}
                    </button>
                  </div>

                  {/* Tab content */}
                  {depTab === 'added' ? (
                    <div className="dbx-dep-list">
                      {dependencies.map((dep, idx) => (
                        <div key={idx} className="dbx-dep-item">
                          <span className="dbx-dep-text">{dep}</span>
                          <div className="dbx-dep-actions">
                            <button
                              type="button"
                              className="dbx-dep-action-icon"
                              title="Dependency details"
                            >
                              <Folder size={13} />
                            </button>
                            <button
                              type="button"
                              className="dbx-dep-action-icon dbx-dep-action-icon--del"
                              title="Remove dependency"
                              onClick={() => handleRemoveDependency(idx)}
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>
                      ))}

                      {showAddDep ? (
                        <div className="dbx-add-dep-form">
                          <input
                            type="text"
                            className="dbx-input"
                            placeholder="e.g. scikit-learn>=1.4.0 or -r requirements.txt"
                            value={newDepInput}
                            onChange={(e) => setNewDepInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleAddDependency();
                              if (e.key === 'Escape') setShowAddDep(false);
                            }}
                            autoFocus
                          />
                          <div className="dbx-add-dep-actions">
                            <button
                              type="button"
                              className="dbx-btn-sm dbx-btn-primary"
                              onClick={handleAddDependency}
                            >
                              Add
                            </button>
                            <button
                              type="button"
                              className="dbx-btn-sm dbx-btn-secondary"
                              onClick={() => setShowAddDep(false)}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="dbx-add-dep-trigger"
                          onClick={() => setShowAddDep(true)}
                        >
                          <Plus size={12} />
                          <span>Add dependency</span>
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="dbx-installed-container">
                      {/* Search & Refresh Controls */}
                      <div className="dbx-installed-controls">
                        <div className="dbx-search-box">
                          <Search size={11} className="dbx-search-icon" />
                          <input
                            type="text"
                            className="dbx-search-input"
                            placeholder="Search installed libraries..."
                            value={packageSearch}
                            onChange={(e) => setPackageSearch(e.target.value)}
                          />
                        </div>
                        <button
                          type="button"
                          className="dbx-refresh-btn"
                          onClick={fetchInstalledPackages}
                          disabled={loadingPackages || !kernelRef}
                          title="Refresh installed packages list from kernel"
                        >
                          <RefreshCw size={11} className={loadingPackages ? 'notebook-pod-spinner' : ''} />
                        </button>
                      </div>

                      {loadingPackages ? (
                        <div className="dbx-installed-loading">
                          <Loader2 size={13} className="notebook-pod-spinner" />
                          <span>Scanning kernel packages...</span>
                        </div>
                      ) : !kernelRef || kernelStatus === 'dead' ? (
                        <div className="dbx-installed-empty">
                          <span>Connect to compute kernel to inspect installed packages.</span>
                        </div>
                      ) : filteredPackages.length === 0 ? (
                        <div className="dbx-installed-empty">
                          <span>{packageSearch ? 'No matching packages found.' : 'No packages detected.'}</span>
                        </div>
                      ) : (
                        <div className="dbx-installed-list">
                          {filteredPackages.map((pkg, idx) => (
                            <div key={`${pkg.name}-${idx}`} className="dbx-installed-item">
                              <span className="dbx-installed-name">{pkg.name}</span>
                              <span className="dbx-installed-ver">{pkg.version}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Sticky Bottom Footer & Action Bar ── */}
      {selectedPod && (
        <div className="dbx-footer">
          <div className="dbx-footer-left">
            <span
              className={`dbx-status-indicator ${
                kernelStatus === 'idle' || kernelStatus === 'busy'
                  ? 'is-ready'
                  : kernelStatus === 'connecting'
                  ? 'is-pending'
                  : 'is-offline'
              }`}
              title={`Pod status: ${resource?.phase || 'Running'} • Kernel: ${kernelStatus}`}
            >
              <Check size={14} />
            </span>

            {/* Context Menu Trigger */}
            <div className="dbx-more-menu-container" ref={menuRef}>
              <button
                type="button"
                className="dbx-footer-icon-btn"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                title="More compute actions"
              >
                <MoreVertical size={14} />
              </button>

              {isMenuOpen && (
                <div className="dbx-dropdown-menu">
                  {resource?.phase === 'Stopped' ? (
                    <button
                      type="button"
                      className="dbx-menu-item"
                      onClick={() => {
                        setIsMenuOpen(false);
                        handleStartCompute();
                      }}
                    >
                      <Play size={13} />
                      <span>Start {computeUnitName}</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="dbx-menu-item dbx-menu-item--danger"
                      onClick={() => {
                        setIsMenuOpen(false);
                        handleStopCompute();
                      }}
                    >
                      <Square size={13} />
                      <span>Kill {computeUnitName}</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className="dbx-menu-item"
                    onClick={() => {
                      setIsMenuOpen(false);
                      handleRestartKernel();
                    }}
                  >
                    <RotateCcw size={13} />
                    <span>Restart Kernel</span>
                  </button>
                  <div className="dbx-menu-divider" />
                  <button
                    type="button"
                    className="dbx-menu-item dbx-menu-item--danger"
                    onClick={() => {
                      setIsMenuOpen(false);
                      handleDetach();
                    }}
                  >
                    <Trash2 size={13} />
                    <span>Detach Compute</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="dbx-footer-right">
            <button
              type="button"
              className="dbx-btn-secondary"
              onClick={() => setActiveRightSidebarTab('logs')}
              title="View compute logs"
            >
              pip logs
            </button>

            <button
              type="button"
              className="dbx-btn-primary"
              onClick={handleApplyChanges}
              disabled={isApplying || actionLoading || !hasChanges}
              title={hasChanges ? 'Apply configuration changes' : 'No changes to apply'}
            >
              {isApplying ? <Loader2 size={13} className="notebook-pod-spinner" /> : null}
              <span>Apply</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
