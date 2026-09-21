import { useState, useRef, useEffect } from 'react';
import { getPrincipalInfo } from '@/lib/auth';
import { useScopedNavigate } from '@/lib/appNavigation';
import { ChevronDown, Plus, RefreshCw, Loader2, Zap, Sliders, Check } from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import api from '@/lib/api';
import { useNotebookStore } from '../../store/notebookStore';
import type { SelectedPod } from '../../store/notebookStore';

interface ResourcePod {
  id: string;
  name?: string;
  runtime_id: string | null;
  phase: string;
  runtime: string;
  profile: string;
  is_default?: boolean;
}

function getPhaseDotClass(phase: string): string {
  const normalized = (phase || '').trim().toLowerCase();
  if (normalized === 'running') return 'notebook-pod-dot--connected';
  if (normalized === 'pending' || normalized === 'starting') return 'notebook-pod-dot--connecting';
  if (normalized === 'stopped' || normalized === 'failed' || normalized === 'terminated') return 'notebook-pod-dot--stopped';
  return 'notebook-pod-dot--unknown';
}

export default function PodSelector() {
  const currentUserId = getPrincipalInfo()?.principal_id;
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const setSelectedPod = useNotebookStore((s) => s.setSelectedPod);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);
  const toggleRightSidebarTab = useNotebookStore((s) => s.toggleRightSidebarTab);
  const navigate = useScopedNavigate();

  const [resources, setResources] = useState<ResourcePod[]>([]);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectingMessage, setConnectingMessage] = useState<string>('Connecting to kernel...');
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  const disabled = kernelStatus === 'busy' || connecting;
  const isStarting = connecting || selectedPod?.state === 'starting';

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  async function loadResources() {
    setLoading(true);
    setError(null);
    try {
      if (!currentUserId) {
        setResources([]);
        setError('No authenticated user is available. Please sign in again.');
        return;
      }
      const list = await computeApi.listResources();
      const currentResources = (Array.isArray(list) ? list : []) as ResourcePod[];
      setResources(currentResources);

      const currentSelection = useNotebookStore.getState().selectedPod;
      if (currentSelection && !currentResources.some((resource) => resource.id === currentSelection.resource_id)) {
        // Keep selection if it is active, otherwise reset
      }
    } catch (err: any) {
      setResources([]);
      const msg = err?.response?.data?.message ?? 'Failed to load compute pods.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  function handleToggleOpen() {
    if (disabled) return;
    if (!isOpen) {
      loadResources();
    }
    setIsOpen((prev) => !prev);
  }

  async function handleSelectServerless() {
    setIsOpen(false);
    setConnecting(true);
    setError(null);
    setConnectingMessage('Provisioning Serverless DuckDB...');

    try {
      const currentNotebookId = useNotebookStore.getState().notebookId;
      const currentMetadata = useNotebookStore.getState().notebookMetadata;
      const notebookName = currentMetadata?.name || undefined;

      // 1. Ensure serverless compute exists for this notebook
      const serverless = await computeApi.ensureServerlessCompute(currentNotebookId || undefined, notebookName);
      const resourceId = serverless.id;

      const startingPod: SelectedPod = {
        resource_id: resourceId,
        runtime_id: serverless.runtime_id ?? resourceId,
        runtime: serverless.runtime || 'duckdb',
        kernel_id: null,
        kernel_name: null,
        state: 'starting',
      };
      setSelectedPod(startingPod);

      // 2. Ensure running and start kernel
      const res = await computeApi.ensureResourceRunningAndStartKernel(resourceId, (msg: string) => {
        setConnectingMessage(msg);
      });

      const connectedPod: SelectedPod = {
        ...startingPod,
        kernel_id: res.kernel.id,
        kernel_name: res.kernel.name || res.kernel.id,
      };
      setSelectedPod(connectedPod);

      const notebookId = useNotebookStore.getState().notebookId;
      if (notebookId) {
        api.put(`/notebook/${notebookId}/compute`, {
          resource_id: resourceId,
          kernel_name: res.kernel.name || res.kernel.id,
        }).catch((err: any) => {
          console.warn('[notebook] Failed to save last compute info:', err);
        });
      }
    } catch (err: any) {
      const msg = err?.response?.data?.message ?? err?.message ?? 'Failed to start serverless compute.';
      setError(msg);
      setSelectedPod(null);
    } finally {
      setConnecting(false);
      setConnectingMessage('Connecting to kernel...');
    }
  }

  async function handleSelectResource(resource: ResourcePod | null) {
    setIsOpen(false);
    if (!resource) {
      setSelectedPod(null);
      return;
    }

    setConnecting(true);
    setError(null);
    setConnectingMessage('Starting compute pod...');

    const startingPod: SelectedPod = {
      resource_id: resource.id,
      runtime_id: resource.runtime_id ?? null,
      runtime: resource.runtime,
      kernel_id: null,
      kernel_name: null,
      state: 'starting',
    };
    setSelectedPod(startingPod);

    try {
      const res = await computeApi.ensureResourceRunningAndStartKernel(resource.id, (msg: string) => {
        setConnectingMessage(msg);
      });

      const connectedPod: SelectedPod = {
        ...startingPod,
        kernel_id: res.kernel.id,
        kernel_name: res.kernel.name || res.kernel.id,
      };
      setSelectedPod(connectedPod);

      const notebookId = useNotebookStore.getState().notebookId;
      if (notebookId) {
        api.put(`/notebook/${notebookId}/compute`, {
          resource_id: resource.id,
          kernel_name: res.kernel.name || res.kernel.id,
        }).catch((err: any) => {
          console.warn('[notebook] Failed to save last compute info:', err);
        });
      }
    } catch (err: any) {
      const msg = err?.response?.data?.message ?? err?.message ?? 'Failed to start kernel.';
      setError(msg);
      setSelectedPod(null);
    } finally {
      setConnecting(false);
      setConnectingMessage('Connecting to kernel...');
    }
  }

  // Trigger dot/spinner: kernel connection status when selected, spinner when connecting
  const renderTriggerIcon = () => {
    if (!selectedPod) return null;
    if (isStarting || kernelStatus === 'connecting') {
      return (
        <span title={connectingMessage}>
          <Loader2 size={12} className="notebook-pod-spinner" />
        </span>
      );
    }
    if (kernelStatus === 'idle' || kernelStatus === 'busy') {
      return <span className="notebook-pod-dot notebook-pod-dot--connected" title={`Kernel connected (${kernelStatus})`} />;
    }
    if (kernelStatus === 'dead') {
      return <span className="notebook-pod-dot notebook-pod-dot--stopped" title="Kernel dead" />;
    }
    return <span className="notebook-pod-dot notebook-pod-dot--unknown" title="Kernel status unknown" />;
  };

  // Get selected resource object for display label
  const selectedResource = resources.find((r) => r.id === selectedPod?.resource_id);
  const isServerlessSelected = selectedResource?.is_default || selectedResource?.name?.toLowerCase().includes('serverless') || (selectedPod && !selectedResource && selectedPod.runtime === 'duckdb');
  const selectedPodLabel = selectedPod
    ? (selectedResource?.name || (isServerlessSelected ? `Serverless (${selectedPod.runtime.toUpperCase()})` : selectedPod.runtime))
    : 'Select compute...';

  return (
    <div className="notebook-pod-selector-wrapper" ref={containerRef} title={error ?? undefined}>
      <div className={`notebook-pod-btn-wrapper ${disabled ? 'is-disabled' : ''}`} onClick={handleToggleOpen}>
        {selectedPod && (
          <span className="notebook-pod-status" aria-hidden="true">
            {renderTriggerIcon()}
          </span>
        )}
        <span className="notebook-pod-trigger-text">
          {isStarting ? connectingMessage : loading ? 'Loading pods...' : selectedPodLabel}
        </span>
        <ChevronDown size={13} className="notebook-pod-chevron" />
      </div>

      {isOpen && (
        <div className="notebook-pod-menu">
          <div className="notebook-pod-menu-header">
            <span>Compute</span>
            <button className="notebook-pod-refresh-btn" onClick={loadResources} title="Refresh compute">
              <RefreshCw size={11} className={loading ? 'is-spinning' : ''} />
            </button>
          </div>

          <div className="notebook-pod-menu-list">
            {/* 1. Serverless Option */}
            <button
              type="button"
              className={`notebook-pod-menu-item ${
                isServerlessSelected && selectedPod ? 'is-selected' : ''
              }`}
              onClick={handleSelectServerless}
            >
              <Zap size={14} className="notebook-pod-item-icon" />
              <div className="notebook-pod-menu-item-content">
                <div className="notebook-pod-menu-item-title-row">
                  <span className="notebook-pod-menu-item-name">Serverless (DuckDB)</span>
                  <span className="notebook-pod-badge-pill">Serverless</span>
                </div>
                <span className="notebook-pod-menu-item-sub">Auto-provisioned • Small</span>
              </div>
              {isServerlessSelected && selectedPod && (
                <Check size={14} className="notebook-pod-check" />
              )}
            </button>

            {/* 2. Custom Pods Section */}
            {resources.length > 0 && <div className="notebook-pod-section-divider" />}
            {resources.length > 0 && (
              <div className="notebook-pod-section-title">All-Purpose Compute</div>
            )}
            {resources.map((resource) => {
              const isCurrent = selectedPod?.resource_id === resource.id;
              return (
                <button
                  type="button"
                  key={resource.id}
                  className={`notebook-pod-menu-item ${isCurrent ? 'is-selected' : ''}`}
                  onClick={() => handleSelectResource(resource)}
                >
                  <span className={`notebook-pod-dot ${getPhaseDotClass(resource.phase)}`} />
                  <div className="notebook-pod-menu-item-content">
                    <span className="notebook-pod-menu-item-name">
                      {resource.name || resource.runtime}
                    </span>
                    <span className="notebook-pod-menu-item-sub">
                      {resource.runtime.toUpperCase()} • {resource.profile} • {resource.phase}
                    </span>
                  </div>
                  {isCurrent && <Check size={14} className="notebook-pod-check" />}
                </button>
              );
            })}

            {!loading && resources.length === 0 && (
              <div className="notebook-pod-menu-empty">
                No custom compute created
              </div>
            )}
          </div>

          <div className="notebook-pod-menu-footer">
            <button
              type="button"
              className="notebook-pod-action-item"
              onClick={() => {
                setIsOpen(false);
                toggleRightSidebarTab('config');
              }}
              title="Configure runtime and memory sizing"
            >
              <Sliders size={13} />
              <span>Configure Environment</span>
            </button>
            <button
              type="button"
              className="notebook-pod-action-item"
              onClick={() => {
                setIsOpen(false);
                navigate('/compute');
              }}
            >
              <Plus size={13} />
              <span>Manage Compute</span>
            </button>
          </div>
        </div>
      )}

      {error && <span className="notebook-pod-error" title={error}>!</span>}
    </div>
  );
}
