import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getManagers } from '../lib/jupyter';
import { useNotebookStore } from '../store/notebookStore';
import type { KernelStatus, SelectedPod } from '../store/notebookStore';
import api from '@/lib/api';
import { getPrincipalInfo } from '@/lib/auth';
import { computeApi } from '@/modules/compute/computeApi';


interface ServerConfig {
  base_url: string;
  ws_url: string;
  token: string;
}

async function fetchJupyterConfig(): Promise<ServerConfig> {
  const res = await api.get<ServerConfig>('/notebook/config');
  return res.data;
}

/** Returned by useKernel so Notebook.tsx can render the connect modal when needed. */
export interface KernelHookResult {
  showConnectModal: boolean;
  dismissConnectModal: () => void;
  connectToDefault: () => Promise<void>;
}

export function useKernel(notebookPath: string): KernelHookResult {
  const { data: config } = useQuery({
    queryKey: ['notebook-config'],
    queryFn: fetchJupyterConfig,
    staleTime: Infinity,
  });

  const setKernel = useNotebookStore((s) => s.setKernel);
  const setKernelStatus = useNotebookStore((s) => s.setKernelStatus);
  const setKernelInfo = useNotebookStore((s) => s.setKernelInfo);
  const setSelectedPod = useNotebookStore((s) => s.setSelectedPod);
  const kernelRef = useNotebookStore((s) => s.kernelRef);
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const lastComputeInfo = useNotebookStore((s) => s.lastComputeInfo);
  const notebookComputeLoaded = useNotebookStore((s) => s.notebookComputeLoaded);
  const connectingRef = useRef(false);
  const autoConnectAttemptedRef = useRef<string | null>(null);

  const [showConnectModal, setShowConnectModal] = useState(false);
  const [autoConnectDone, setAutoConnectDone] = useState(false);

  const selectedPodResourceId = selectedPod?.resource_id ?? null;
  const selectedPodKernelId = selectedPod?.kernel_id ?? null;
  const selectedPodKernelName = selectedPod?.kernel_name ?? null;

  const normalizeStatus = (status: string): KernelStatus => {
    if (status === 'idle' || status === 'busy' || status === 'dead') return status;
    if (status === 'starting' || status === 'restarting' || status === 'autorestarting') return 'connecting';
    return 'unknown';
  };

  async function connectToKernel(targetKernelId: string, targetKernelName: string, resolvedConfig: ServerConfig, podSnapshot: SelectedPod) {
    if (connectingRef.current) return;
    connectingRef.current = true;
    setKernelStatus('connecting');

    try {
      const jupyterConfig = {
        baseUrl: resolvedConfig.base_url,
        wsUrl: resolvedConfig.ws_url,
        token: resolvedConfig.token,
      };
      const { kernelManager } = getManagers(jupyterConfig);
      await kernelManager.ready;

      const kernel = kernelManager.connectTo({
        model: { id: targetKernelId, name: targetKernelName },
      });

      console.log('[notebook] kernel connected:', kernel.id, 'status:', kernel.status);
      setKernel(kernel);
      setKernelStatus(normalizeStatus(kernel.status));

      // Inject notebook path context into kernel environment
      const currentNbPath = useNotebookStore.getState().notebookPath;
      if (currentNbPath) {
        kernel.requestExecute({
          code: `import os; os.environ['COMPASSX_NOTEBOOK_PATH'] = ${JSON.stringify(currentNbPath)}; os.environ['NOTEBOOK_PATH'] = ${JSON.stringify(currentNbPath)}`,
          store_history: false,
          silent: true,
        });
      }

      kernel.statusChanged.connect((_k: any, status: string) => {
        setKernelStatus(normalizeStatus(status));
      });

      kernel.requestKernelInfo().then((info: any) => {
        if (info && info.content) {
          const langInfo = (info.content as { language_info?: { name?: string; version?: string } }).language_info;
          setKernelInfo({
            name: kernel.name,
            language: langInfo?.name ?? 'python',
            version: langInfo?.version ?? '',
          });
        }
      });

      const currentPod = useNotebookStore.getState().selectedPod;
      if (currentPod?.kernel_id === targetKernelId) {
        setSelectedPod({ ...currentPod, state: 'connected' });
      }
    } catch (err) {
      console.error('[notebook] kernel connect failed:', err);
      setKernelStatus('dead');
    } finally {
      connectingRef.current = false;
    }
  }

  // Auto-reconnect when lastComputeInfo is available and no kernel connected yet
  useEffect(() => {
    if (!config) return;
    if (selectedPodKernelId) return; // already have kernel
    if (autoConnectDone) return;

    // Wait until NotebookPage has finished loading the notebook and set compute info
    if (!notebookComputeLoaded) return;

    if (!lastComputeInfo) {
      // Loaded and no last compute — show connect modal
      setAutoConnectDone(true);
      setShowConnectModal(true);
      return;
    }

    const resourceId = lastComputeInfo.resource_id;
    if (autoConnectAttemptedRef.current === resourceId) return;
    autoConnectAttemptedRef.current = resourceId;
    setAutoConnectDone(true);

    const currentUserId = getPrincipalInfo()?.principal_id;
    if (!currentUserId) return;

    (async () => {
      try {
        // Set starting pod immediately so UI trigger shows connecting spinner right away
        setSelectedPod({
          resource_id: resourceId,
          runtime_id: null,
          runtime: 'duckdb',
          kernel_id: null,
          kernel_name: null,
          state: 'starting',
        });
        setKernelStatus('connecting');

        const kernelResp = await computeApi.startResourceKernel(resourceId, currentUserId) as { id: string; name: string };
        const pod: SelectedPod = {
          resource_id: resourceId,
          runtime_id: null,
          runtime: 'duckdb',
          kernel_id: kernelResp.id,
          kernel_name: kernelResp.name || kernelResp.id,
          state: 'starting',
        };
        setSelectedPod(pod);
        // connectToKernel will fire from the selectedPodKernelId effect below
      } catch (err) {
        console.warn('[notebook] auto-reconnect failed:', err);
        setSelectedPod(null);
        setKernelStatus('unknown');
        setShowConnectModal(true);
      }
    })();
  }, [config, lastComputeInfo, notebookComputeLoaded, selectedPodKernelId, autoConnectDone]);

  // Reset auto-connect state when notebook changes
  useEffect(() => {
    setAutoConnectDone(false);
    setShowConnectModal(false);
    autoConnectAttemptedRef.current = null;
  }, [notebookPath]);

  // Connect to kernel when selectedPod gains a kernel_id
  useEffect(() => {
    if (!config) return;
    if (!selectedPodKernelId) return;
    if (kernelRef?.id === selectedPodKernelId) return;

    const resolvedConfig = config;
    const targetKernelId = selectedPodKernelId;
    const targetKernelName = selectedPodKernelName ?? targetKernelId;

    const pod: SelectedPod = {
      resource_id: selectedPodResourceId ?? '',
      runtime_id: null,
      runtime: 'duckdb',
      kernel_id: targetKernelId,
      kernel_name: targetKernelName,
      state: 'starting',
    };
    connectToKernel(targetKernelId, targetKernelName, resolvedConfig, pod);
  }, [config, selectedPodKernelId, selectedPodKernelName, kernelRef?.id]);

  async function connectToDefault() {
    const currentUserId = getPrincipalInfo()?.principal_id;
    if (!currentUserId || !config) return;
    setShowConnectModal(false);
    try {
      // Find the resource named "default"
      const resources = await computeApi.listResources(currentUserId) as Array<{ id: string; name: string; runtime: string; phase?: string }>;
      const defaultResource = resources.find((r) => r.name === 'default');
      if (!defaultResource) {
        console.error('[notebook] No compute resource named "default" found');
        setShowConnectModal(true);
        return;
      }

      const kernelResp = await computeApi.startResourceKernel(defaultResource.id, currentUserId) as { id: string; name: string };
      const pod: SelectedPod = {
        resource_id: defaultResource.id,
        runtime_id: null,
        runtime: defaultResource.runtime ?? 'duckdb',
        kernel_id: kernelResp.id,
        kernel_name: kernelResp.name || kernelResp.id,
        state: 'starting',
      };
      setSelectedPod(pod);

      // Save this as the last compute for this notebook
      const notebookId = useNotebookStore.getState().notebookId;
      if (notebookId) {
        api.put(`/notebook/${notebookId}/compute`, {
          resource_id: defaultResource.id,
          kernel_name: kernelResp.name || kernelResp.id,
        }).catch(() => {});
      }
    } catch (err) {
      console.error('[notebook] connect to default failed:', err);
      setKernelStatus('dead');
    }
  }

  return {
    showConnectModal,
    dismissConnectModal: () => setShowConnectModal(false),
    connectToDefault,
  };
}




