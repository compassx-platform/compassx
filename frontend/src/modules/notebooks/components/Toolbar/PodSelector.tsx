import { useState, useRef, useEffect } from 'react';
import { getPrincipalInfo } from '@/lib/auth';
import { useScopedNavigate } from '@/lib/appNavigation';
import { ChevronDown, Plus, RefreshCw, Loader2 } from 'lucide-react';
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
}

interface KernelStartResponse {
  id: string;
  name: string;
}

function getPhaseDotClass(phase: string): string {
  const normalized = (phase || '').trim().toLowerCase();
  if (normalized === 'running') return 'notebook-pod-dot--connected';
  if (normalized === 'pending' || normalized === 'starting') return 'notebook-pod-dot--connecting';
  if (normalized === 'stopped' || normalized === 'failed' || normalized === 'terminated') return 'notebook-pod-dot--stopped';
  return 'notebook-pod-dot--unknown';
}

function getPhaseLabel(phase: string): string {
  const normalized = (phase || '').trim().toLowerCase();
  return normalized || 'unknown';
}

export default function PodSelector() {
  const currentUserId = getPrincipalInfo()?.principal_id;
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const setSelectedPod = useNotebookStore((s) => s.setSelectedPod);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);
  const navigate = useScopedNavigate();

  const [resources, setResources] = useState<ResourcePod[]>([]);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
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
        setSelectedPod(null);
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

  async function handleSelectResource(resource: ResourcePod | null) {
    setIsOpen(false);
    if (!resource) {
      setSelectedPod(null);
      return;
    }

    setConnecting(true);
    setError(null);

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
      const kernelResp = await computeApi.startResourceKernel(resource.id) as KernelStartResponse;
      const connectedPod: SelectedPod = {
        ...startingPod,
        kernel_id: kernelResp.id,
        kernel_name: kernelResp.name || kernelResp.id,
      };
      setSelectedPod(connectedPod);

      const notebookId = useNotebookStore.getState().notebookId;
      if (notebookId) {
        api.put(`/notebook/${notebookId}/compute`, {
          resource_id: resource.id,
          kernel_name: kernelResp.name || kernelResp.id,
        }).catch((err: any) => {
          console.warn('[notebook] Failed to save last compute info:', err);
        });
      }
    } catch (err: any) {
      const msg = err?.response?.data?.message ?? 'Failed to start kernel.';
      setError(msg);
      setSelectedPod(null);
    } finally {
      setConnecting(false);
    }
  }

  // Trigger dot/spinner: kernel connection status when selected, spinner when connecting
  const renderTriggerIcon = () => {
    if (!selectedPod) return null;
    if (isStarting || kernelStatus === 'connecting') {
      return (
        <span title="Connecting to kernel...">
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
  const selectedPodLabel = selectedResource
    ? (selectedResource.name || selectedResource.runtime)
    : (selectedPod?.runtime || 'Select compute...');

  return (
    <div className="notebook-pod-selector-wrapper" ref={containerRef} title={error ?? undefined}>
      <div className={`notebook-pod-btn-wrapper ${disabled ? 'is-disabled' : ''}`} onClick={handleToggleOpen}>
        {selectedPod && (
          <span className="notebook-pod-status" aria-hidden="true">
            {renderTriggerIcon()}
          </span>
        )}
        <span className="notebook-pod-trigger-text">
          {loading ? 'Loading pods...' : selectedPod ? selectedPodLabel : 'Select compute...'}
        </span>
        <ChevronDown size={13} className="notebook-pod-chevron" />
      </div>

      {isOpen && (
        <div className="notebook-pod-menu">
          <div className="notebook-pod-menu-header">
            <span>Compute Pods</span>
            <button className="notebook-pod-refresh-btn" onClick={loadResources} title="Refresh compute pods">
              <RefreshCw size={11} className={loading ? 'is-spinning' : ''} />
            </button>
          </div>

          <div className="notebook-pod-menu-list">
            {/* None option */}
            <button
              type="button"
              className={`notebook-pod-menu-item ${!selectedPod ? 'is-selected' : ''}`}
              onClick={() => handleSelectResource(null)}
            >
              <span className="notebook-pod-menu-item-name" style={{ color: '#6b7280' }}>
                No compute selected
              </span>
            </button>

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
                  <span className="notebook-pod-menu-item-name">
                    {resource.name || resource.runtime}
                  </span>
                </button>
              );
            })}

            {!loading && resources.length === 0 && (
              <div className="notebook-pod-menu-empty">
                No compute pods available
              </div>
            )}
          </div>

          <div className="notebook-pod-menu-footer">
            <button
              type="button"
              className="notebook-pod-create-btn"
              onClick={() => {
                setIsOpen(false);
                navigate('/compute');
              }}
            >
              <Plus size={12} />
              <span>Create / Manage Pods</span>
            </button>
          </div>
        </div>
      )}

      {error && <span className="notebook-pod-error" title={error}>!</span>}
    </div>
  );
}
