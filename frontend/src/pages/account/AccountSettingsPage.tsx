import React, { useState, useEffect } from 'react';
import {
  Layers,
  ExternalLink,
  ShieldCheck,
  Server,
  Info,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Clock,
  Loader2,
  Cpu,
  HardDrive,
  RefreshCw,
  Box,
  Sliders,
  Sparkles,
  Zap,
  Trash2,
} from 'lucide-react';
import {
  useAccountSettings,
  useUpdateAccountSettings,
  useSwitchoverAppNodePool,
  useProvisionComputeNodePool,
  useDeprovisionComputeNodePool,
  useSwitchoverComputeNodePool,
  VmSizeOption,
} from '@/lib/accountSettingsApi';
import { useToast } from '@/lib/toast';
import '../workspace/workspace-settings.css';

export default function AccountSettingsPage() {
  const toast = useToast();
  const { data: accountData, isLoading, error } = useAccountSettings();
  const updateSettingsMutation = useUpdateAccountSettings();
  const switchoverMutation = useSwitchoverAppNodePool();
  const provisionComputeMutation = useProvisionComputeNodePool();
  const deprovisionComputeMutation = useDeprovisionComputeNodePool();
  const switchoverComputeMutation = useSwitchoverComputeNodePool();

  const settings = accountData?.settings || {};
  
  // Airflow settings
  const airflow = settings.airflow || { webserver_enabled: false, webserver_status: 'stopped' };
  const isWebserverEnabled = Boolean(airflow.webserver_enabled);
  const webserverStatus = airflow.webserver_status || (isWebserverEnabled ? 'starting' : 'stopped');

  // App Node Pool settings
  const appNodePool = settings.app_node_pool || {
    dedicated_pool_enabled: false,
    pool_name: 'apppool',
    default_pool_name: 'userpoolv2',
    vm_size: 'Standard_B2s_v2',
    min_count: 1,
    max_count: 5,
    auto_scale: true,
    status: 'disabled',
  };

  const [isDedicatedEnabled, setIsDedicatedEnabled] = useState<boolean>(
    Boolean(appNodePool.dedicated_pool_enabled)
  );
  const [selectedVmSize, setSelectedVmSize] = useState<string>(
    appNodePool.vm_size || 'Standard_B2s_v2'
  );
  const [minCount, setMinCount] = useState<number>(Number(appNodePool.min_count || 1));
  const [maxCount, setMaxCount] = useState<number>(Number(appNodePool.max_count || 5));

  // Compute & Dedicated Node Pool settings
  const compute = settings.compute || {
    auto_stop_enabled: true,
    auto_stop_minutes: 5,
    dedicated_pool_enabled: true,
    pool_name: 'computepool',
    vm_size: 'Standard_D4ads_v5',
    min_count: 0,
    max_count: 10,
    auto_scale: true,
    is_provisioned: true,
  };
  const [isAutoStopEnabled, setIsAutoStopEnabled] = useState<boolean>(
    compute.auto_stop_enabled !== false
  );
  const [autoStopMinutes, setAutoStopMinutes] = useState<number>(
    compute.auto_stop_minutes || 5
  );
  const [isComputeDedicated, setIsComputeDedicated] = useState<boolean>(
    compute.dedicated_pool_enabled !== false
  );
  const [computeVmSize, setComputeVmSize] = useState<string>(
    compute.vm_size || 'Standard_D4ads_v5'
  );
  const [computeMinCount, setComputeMinCount] = useState<number>(
    compute.min_count !== undefined ? Number(compute.min_count) : 0
  );
  const [computeMaxCount, setComputeMaxCount] = useState<number>(
    compute.max_count !== undefined ? Number(compute.max_count) : 10
  );

  // Sync state when data arrives
  useEffect(() => {
    if (appNodePool) {
      setIsDedicatedEnabled(Boolean(appNodePool.dedicated_pool_enabled));
      if (appNodePool.vm_size) setSelectedVmSize(appNodePool.vm_size);
      if (appNodePool.min_count !== undefined) setMinCount(Number(appNodePool.min_count));
      if (appNodePool.max_count !== undefined) setMaxCount(Number(appNodePool.max_count));
    }
    if (settings.compute) {
      setIsAutoStopEnabled(settings.compute.auto_stop_enabled !== false);
      if (settings.compute.auto_stop_minutes) {
        setAutoStopMinutes(Number(settings.compute.auto_stop_minutes));
      }
      setIsComputeDedicated(settings.compute.dedicated_pool_enabled !== false);
      if (settings.compute.vm_size) {
        setComputeVmSize(settings.compute.vm_size);
      }
      if (settings.compute.min_count !== undefined) {
        setComputeMinCount(Number(settings.compute.min_count));
      }
      if (settings.compute.max_count !== undefined) {
        setComputeMaxCount(Number(settings.compute.max_count));
      }
    }
  }, [
    appNodePool.dedicated_pool_enabled,
    appNodePool.vm_size,
    appNodePool.min_count,
    appNodePool.max_count,
    settings.compute?.auto_stop_enabled,
    settings.compute?.auto_stop_minutes,
    settings.compute?.dedicated_pool_enabled,
    settings.compute?.vm_size,
    settings.compute?.min_count,
    settings.compute?.max_count,
  ]);

  const vmSizesCatalog: VmSizeOption[] = appNodePool.vm_sizes_catalog || [
    {
      id: 'Standard_D4ads_v5',
      name: 'Standard_D4ads_v5',
      label: 'Standard_D4ads_v5 (4 vCPU, 16 GiB RAM - AMD EPYC)',
      cpu: 4,
      memory_gib: 16,
      architecture: 'x86_64',
      category: 'High Performance Compute',
      description: 'Production compute tier for high concurrency, fast DuckDB analytics, and heavy notebook processing.',
      recommended: true,
    },
    {
      id: 'Standard_D2ads_v5',
      name: 'Standard_D2ads_v5',
      label: 'Standard_D2ads_v5 (2 vCPU, 8 GiB RAM - AMD EPYC)',
      cpu: 2,
      memory_gib: 8,
      architecture: 'x86_64',
      category: 'General Purpose (Dedicated)',
      description: 'Consistent performance for medium workloads and development sessions.',
      recommended: false,
    },
    {
      id: 'Standard_B2s_v2',
      name: 'Standard_B2s_v2',
      label: 'Standard_B2s_v2 (2 vCPU, 4 GiB RAM)',
      cpu: 2,
      memory_gib: 4,
      architecture: 'x86_64',
      category: 'Burstable (General Purpose)',
      description: 'Economical burstable VM ideal for lightweight apps, dev environments, and dashboards.',
      recommended: false,
    },
    {
      id: 'Standard_B2als_v2',
      name: 'Standard_B2als_v2',
      label: 'Standard_B2als_v2 (2 vCPU, 4 GiB RAM - ARM64)',
      cpu: 2,
      memory_gib: 4,
      architecture: 'arm64',
      category: 'ARM64 Ampere',
      description: 'Energy-efficient ARM64 architecture with high cost performance.',
      recommended: false,
    },
    {
      id: 'Standard_B4ms',
      name: 'Standard_B4ms',
      label: 'Standard_B4ms (4 vCPU, 16 GiB RAM)',
      cpu: 4,
      memory_gib: 16,
      architecture: 'x86_64',
      category: 'Burstable Memory-Optimized',
      description: 'High memory-to-core ratio with burstable CPU for memory-heavy applications.',
      recommended: false,
    },
    {
      id: 'Standard_D2s_v5',
      name: 'Standard_D2s_v5',
      label: 'Standard_D2s_v5 (2 vCPU, 8 GiB RAM)',
      cpu: 2,
      memory_gib: 8,
      architecture: 'x86_64',
      category: 'General Purpose (Dedicated)',
      description: 'Consistent performance on Intel Xeon processors for production web apps.',
      recommended: false,
    },
    {
      id: 'Standard_D4s_v5',
      name: 'Standard_D4s_v5',
      label: 'Standard_D4s_v5 (4 vCPU, 16 GiB RAM)',
      cpu: 4,
      memory_gib: 16,
      architecture: 'x86_64',
      category: 'High Performance Compute',
      description: 'Production compute tier for high concurrency and heavy processing.',
      recommended: false,
    },
    {
      id: 'Standard_D8s_v5',
      name: 'Standard_D8s_v5',
      label: 'Standard_D8s_v5 (8 vCPU, 32 GiB RAM)',
      cpu: 8,
      memory_gib: 32,
      architecture: 'x86_64',
      category: 'High Performance Intensive',
      description: 'Enterprise compute scale for high-load multi-tenant deployments.',
      recommended: false,
    },
    {
      id: 'Standard_E2s_v5',
      name: 'Standard_E2s_v5',
      label: 'Standard_E2s_v5 (2 vCPU, 16 GiB RAM)',
      cpu: 2,
      memory_gib: 16,
      architecture: 'x86_64',
      category: 'Memory Optimized',
      description: 'Optimized for in-memory caching, analytics engines, and dataset processing.',
      recommended: false,
    },
    {
      id: 'Standard_E4s_v5',
      name: 'Standard_E4s_v5',
      label: 'Standard_E4s_v5 (4 vCPU, 32 GiB RAM)',
      cpu: 4,
      memory_gib: 32,
      architecture: 'x86_64',
      category: 'Memory Optimized Enterprise',
      description: 'Large memory allocation for big data, machine learning, and cache-heavy apps.',
      recommended: false,
    },
  ];

  const selectedVmMeta = vmSizesCatalog.find((v) => v.id === selectedVmSize) || vmSizesCatalog[0];
  const computeVmMeta = vmSizesCatalog.find((v) => v.id === computeVmSize) || vmSizesCatalog[4] || vmSizesCatalog[0];
  const computeStatus = compute.status || (isComputeDedicated ? 'active' : 'disabled');

  const handleSaveComputeAutoStop = (enabled: boolean, mins: number) => {
    handleSaveComputeConfig({ autoStopEnabled: enabled, autoStopMins: mins });
  };

  const handleToggleAirflowWebserver = (newVal: boolean) => {
    updateSettingsMutation.mutate(
      {
        airflow: {
          webserver_enabled: newVal,
        },
      },
      {
        onSuccess: () => {
          if (newVal) {
            toast.success('Airflow Webserver is starting. It will become ready in a few moments.');
          } else {
            toast.success('Airflow Webserver has been stopped.');
          }
        },
        onError: (err: any) => {
          toast.error(err.response?.data?.detail || err.message || 'Failed to update Airflow Webserver state.');
        },
      }
    );
  };

  const handleSaveNodePoolConfig = (newDedicatedVal?: boolean, newVmSize?: string, newMin?: number, newMax?: number) => {
    const dedicated = newDedicatedVal !== undefined ? newDedicatedVal : isDedicatedEnabled;
    const vmSize = newVmSize !== undefined ? newVmSize : selectedVmSize;
    const minCnt = newMin !== undefined ? newMin : minCount;
    const maxCnt = newMax !== undefined ? newMax : maxCount;

    updateSettingsMutation.mutate(
      {
        app_node_pool: {
          dedicated_pool_enabled: dedicated,
          vm_size: vmSize,
          min_count: minCnt,
          max_count: maxCnt,
          auto_scale: true,
          pool_name: 'apppool',
          default_pool_name: 'userpoolv2',
        },
      },
      {
        onSuccess: (resp) => {
          if (dedicated) {
            toast.success(
              `Dedicated App Node Pool enabled with ${vmSize}. App pods are rolling over to 'apppool'.`
            );
          } else {
            toast.success(`App workloads switched back to shared user pool ('userpoolv2').`);
          }
        },
        onError: (err: any) => {
          toast.error(err.response?.data?.detail || err.message || 'Failed to update App Node Pool configuration.');
        },
      }
    );
  };

  const handleManualSwitchover = () => {
    const targetPool = isDedicatedEnabled ? 'apppool' : 'userpoolv2';
    switchoverMutation.mutate(targetPool, {
      onSuccess: (data: any) => {
        toast.success(`Workload switchover triggered: ${data.migrated_count || 0} app deployment(s) updated.`);
      },
      onError: (err: any) => {
        toast.error(err.response?.data?.detail || err.message || 'Failed to trigger switchover.');
      },
    });
  };

  const handleSaveComputeConfig = (opts?: {
    autoStopEnabled?: boolean;
    autoStopMins?: number;
    dedicatedEnabled?: boolean;
    vmSize?: string;
    minCount?: number;
    maxCount?: number;
  }) => {
    const autoStopEnabled = opts?.autoStopEnabled !== undefined ? opts.autoStopEnabled : isAutoStopEnabled;
    const autoStopMins = opts?.autoStopMins !== undefined ? opts.autoStopMins : autoStopMinutes;
    const dedicated = opts?.dedicatedEnabled !== undefined ? opts.dedicatedEnabled : isComputeDedicated;
    const vmSize = opts?.vmSize !== undefined ? opts.vmSize : computeVmSize;
    const minCnt = opts?.minCount !== undefined ? opts.minCount : computeMinCount;
    const maxCnt = opts?.maxCount !== undefined ? opts.maxCount : computeMaxCount;

    updateSettingsMutation.mutate(
      {
        compute: {
          auto_stop_enabled: autoStopEnabled,
          auto_stop_minutes: autoStopMins,
          dedicated_pool_enabled: dedicated,
          pool_name: 'computepool',
          vm_size: vmSize,
          min_count: minCnt,
          max_count: maxCnt,
          auto_scale: true,
        },
      },
      {
        onSuccess: () => {
          toast.success('Compute settings updated successfully.');
        },
        onError: (err: any) => {
          toast.error(err.response?.data?.detail || err.message || 'Failed to update compute settings.');
        },
      }
    );
  };

  const computeIsProvisioned = compute.is_provisioned !== undefined ? Boolean(compute.is_provisioned) : true;
  const computeIsProvisioning = Boolean(
    compute.is_provisioning ||
      compute.status === 'provisioning' ||
      compute.status === 'deprovisioning' ||
      provisionComputeMutation.isPending ||
      deprovisionComputeMutation.isPending
  );
  const computeAction =
    compute.provisioning_action ||
      (deprovisionComputeMutation.isPending
        ? 'deprovisioning'
        : provisionComputeMutation.isPending
        ? 'provisioning'
        : '');
  const computeWorkloads = compute.compute_workloads || { total_compute: 0, compute_pods: [] };

  const handleToggleComputeDedicated = (checked: boolean) => {
    setIsComputeDedicated(checked);
    if (!checked) {
      deprovisionComputeMutation.mutate(
        { pool_name: 'computepool', fallback_pool: compute.default_pool_name || 'userpoolv2' },
        {
          onSuccess: () => {
            toast.success(
              "Dedicated compute disabled. Active compute pods are rolling over to 'userpoolv2' and 'computepool' is being deprovisioned."
            );
          },
          onError: (err: any) => {
            toast.error(err.response?.data?.detail || err.message || 'Failed to deprovision compute pool.');
          },
        }
      );
    } else {
      handleSaveComputeConfig({ dedicatedEnabled: true });
    }
  };

  const handleTriggerProvisionCompute = () => {
    provisionComputeMutation.mutate(
      {
        pool_name: 'computepool',
        vm_size: computeVmSize,
        min_count: computeMinCount,
        max_count: computeMaxCount,
      },
      {
        onSuccess: () => {
          toast.success(
            `Compute pool 'computepool' provisioning initiated with ${computeVmSize} (Min: ${computeMinCount}, Max: ${computeMaxCount}). Live monitoring is active.`
          );
        },
        onError: (err: any) => {
          toast.error(err.response?.data?.detail || err.message || 'Failed to dispatch provisioning command.');
        },
      }
    );
  };

  const handleTriggerDeprovisionCompute = () => {
    if (
      window.confirm(
        "Are you sure you want to deprovision 'computepool'? Compute pods will gracefully roll over to the shared user pool ('userpoolv2')."
      )
    ) {
      deprovisionComputeMutation.mutate(
        { pool_name: 'computepool', fallback_pool: compute.default_pool_name || 'userpoolv2' },
        {
          onSuccess: () => {
            setIsComputeDedicated(false);
            toast.success(
              "Deprovisioning initiated: pods rolling over to 'userpoolv2' and 'computepool' being deleted."
            );
          },
          onError: (err: any) => {
            toast.error(err.response?.data?.detail || err.message || 'Failed to deprovision compute pool.');
          },
        }
      );
    }
  };

  const handleManualComputeSwitchover = () => {
    const targetPool = isComputeDedicated && computeIsProvisioned ? 'computepool' : (compute.default_pool_name || 'userpoolv2');
    switchoverComputeMutation.mutate(targetPool, {
      onSuccess: (data: any) => {
        toast.success(`Compute switchover triggered: ${data.migrated_count || 0} compute deployment(s) updated.`);
      },
      onError: (err: any) => {
        toast.error(err.response?.data?.detail || err.message || 'Failed to trigger compute switchover.');
      },
    });
  };

  if (isLoading) {
    return (
      <div className="ws-settings-page" style={{ display: 'flex', justifyContent: 'center', padding: '100px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--color-text-muted)' }}>
          <Loader2 size={24} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
          <span>Loading account settings...</span>
        </div>
      </div>
    );
  }

  if (error || !accountData) {
    return (
      <div className="ws-settings-page">
        <div
          style={{
            padding: '20px',
            background: 'var(--color-danger-bg, rgba(239, 68, 68, 0.1))',
            color: 'var(--color-danger, #ef4444)',
            borderRadius: '12px',
            border: '1px solid var(--color-danger, #ef4444)',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: '1rem', marginBottom: 4 }}>Failed to load account settings</div>
          <div style={{ fontSize: '0.85rem' }}>{(error as any)?.message || 'Account information unavailable.'}</div>
        </div>
      </div>
    );
  }

  const poolStatus = appNodePool.status || (isDedicatedEnabled ? 'active' : 'disabled');
  const appWorkloads = appNodePool.app_workloads || { total_apps: 0, apps: [] };

  return (
    <div className="ws-settings-page">
      {/* Header */}
      <div className="ws-settings-header">
        <h1 className="ws-settings-title">Account Settings</h1>
        <div className="ws-settings-subtitle">
          <span>Account: <strong>{accountData.account_name}</strong></span>
          <span className="ws-settings-badge">
            <ShieldCheck size={12} />
            ACCOUNT ADMIN
          </span>
        </div>
      </div>

      <div className="ws-settings-container">
        {/* Section 1: App Compute & Node Pool Isolation */}
        <div className="ws-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h2 className="ws-section-header" style={{ margin: 0 }}>App Compute &amp; Node Pool Isolation</h2>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                Control how application pods (production apps and dev sandboxes) are scheduled on Kubernetes node pools.
              </div>
            </div>

            {/* Status Badge */}
            <div>
              {isDedicatedEnabled && poolStatus === 'active' && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: 'var(--color-success-bg, rgba(34, 197, 94, 0.1))',
                    color: 'var(--color-success, #22c55e)',
                    border: '1px solid var(--color-success, #22c55e)',
                  }}
                >
                  <CheckCircle2 size={12} />
                  DEDICATED POOL ACTIVE ({appNodePool.app_pool?.ready_nodes || 0} Nodes)
                </span>
              )}

              {isDedicatedEnabled && (poolStatus === 'provisioning' || poolStatus === 'starting') && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: 'var(--color-primary-bg, rgba(27, 110, 243, 0.1))',
                    color: 'var(--color-primary, #1b6ef3)',
                    border: '1px solid var(--color-primary, #1b6ef3)',
                  }}
                >
                  <Loader2 size={12} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  PROVISIONING POOL...
                </span>
              )}

              {!isDedicatedEnabled && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: 'var(--color-surface-hover, #f3f4f6)',
                    color: 'var(--color-text-muted, #6b7280)',
                    border: '1px solid var(--color-border, #e5e7eb)',
                  }}
                >
                  <Server size={12} />
                  SHARED USER POOL ({appNodePool.default_pool_name || 'userpoolv2'})
                </span>
              )}
            </div>
          </div>

          {/* Row 1: Dedicated Pool Toggle */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Box size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Deploy Apps to Dedicated Node Pool
                </span>
              </div>
              <div className="ws-setting-desc">
                When enabled, all published application and developer sandbox pods are isolated onto a dedicated Kubernetes
                node pool (<code>apppool</code>), separating app traffic and compute from core platform services.
                When disabled, app pods are scheduled on the shared user node pool (<code>userpoolv2</code>).
              </div>
            </div>

            <div className="ws-setting-control">
              {/* iOS Toggle Switch */}
              <label
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  width: '46px',
                  height: '26px',
                  cursor: updateSettingsMutation.isPending ? 'not-allowed' : 'pointer',
                  opacity: updateSettingsMutation.isPending ? 0.6 : 1,
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={isDedicatedEnabled}
                  disabled={updateSettingsMutation.isPending}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setIsDedicatedEnabled(checked);
                    handleSaveNodePoolConfig(checked, selectedVmSize);
                  }}
                  style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
                />
                <span
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: isDedicatedEnabled ? 'var(--color-primary, #1b6ef3)' : 'var(--color-border, #d1d5db)',
                    borderRadius: '26px',
                    transition: 'all 0.25s ease',
                    boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)',
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      content: '""',
                      height: '20px',
                      width: '20px',
                      left: isDedicatedEnabled ? '23px' : '3px',
                      bottom: '3px',
                      backgroundColor: '#ffffff',
                      borderRadius: '50%',
                      transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    }}
                  />
                </span>
              </label>
            </div>
          </div>

          {/* Row 2: VM Size Selection */}
          <div className="ws-setting-item" style={{ alignItems: 'flex-start' }}>
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Cpu size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  App Node Pool Virtual Machine Type
                </span>
                {selectedVmMeta && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      background: 'var(--color-primary-bg, rgba(27, 110, 243, 0.1))',
                      color: 'var(--color-primary, #1b6ef3)',
                    }}
                  >
                    {selectedVmMeta.cpu} vCPU &bull; {selectedVmMeta.memory_gib} GiB RAM &bull; {selectedVmMeta.architecture}
                  </span>
                )}
              </div>
              <div className="ws-setting-desc">
                Select the virtual machine instance type for the dedicated app node pool. Higher capacity VMs provide dedicated compute
                and memory headroom for compute-intensive Python data pipelines, Streamlit dashboards, and full-stack containers.
              </div>

              {selectedVmMeta && (
                <div
                  style={{
                    marginTop: '8px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    fontSize: '0.8rem',
                    background: 'var(--color-surface-hover, rgba(0,0,0,0.02))',
                    border: '1px solid var(--color-border, #e5e7eb)',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>{selectedVmMeta.category}: </span>
                  {selectedVmMeta.description}
                </div>
              )}
            </div>

            <div className="ws-setting-control" style={{ minWidth: '280px' }}>
              <select
                value={selectedVmSize}
                disabled={updateSettingsMutation.isPending}
                onChange={(e) => {
                  const newVm = e.target.value;
                  setSelectedVmSize(newVm);
                  handleSaveNodePoolConfig(isDedicatedEnabled, newVm);
                }}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  background: 'var(--color-surface, #ffffff)',
                  border: '1px solid var(--color-border, #d1d5db)',
                  color: 'var(--color-text)',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                {vmSizesCatalog.map((vm) => (
                  <option key={vm.id} value={vm.id}>
                    {vm.label} {vm.recommended ? '★ (Recommended)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 3: App Node Pool Scaling & Node Limits (Min & Max) */}
          <div className="ws-setting-item" style={{ alignItems: 'flex-start' }}>
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Layers size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Autoscaling Node Limits (Min &amp; Max Nodes)
                </span>
              </div>
              <div className="ws-setting-desc">
                Configure minimum and maximum virtual machine nodes for <code>apppool</code>. The cluster autoscaler will dynamically scale nodes between these bounds based on deployed app containers and user workloads.
              </div>

              {/* Quick Min Count Presets */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Min Nodes:</span>
                {[
                  { label: '1 (Standard)', val: 1 },
                  { label: '2 (High Availability)', val: 2 },
                  { label: '3 (High Load)', val: 3 },
                ].map((preset) => (
                  <button
                    key={preset.val}
                    type="button"
                    disabled={updateSettingsMutation.isPending}
                    onClick={() => {
                      setMinCount(preset.val);
                      handleSaveNodePoolConfig(isDedicatedEnabled, selectedVmSize, preset.val, maxCount);
                    }}
                    style={{
                      padding: '5px 12px',
                      borderRadius: '6px',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                      cursor: 'pointer',
                      border: minCount === preset.val ? '1px solid var(--color-primary, #1b6ef3)' : '1px solid var(--color-border, #e5e7eb)',
                      background: minCount === preset.val ? 'var(--color-primary-bg, #ebf2ff)' : 'var(--color-surface, #ffffff)',
                      color: minCount === preset.val ? 'var(--color-primary, #1b6ef3)' : 'var(--color-text, #374151)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ws-setting-control" style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Min:</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={minCount}
                  disabled={updateSettingsMutation.isPending}
                  onChange={(e) => {
                    const val = Math.max(1, parseInt(e.target.value, 10) || 1);
                    setMinCount(val);
                  }}
                  onBlur={() => handleSaveNodePoolConfig(isDedicatedEnabled, selectedVmSize, minCount, maxCount)}
                  style={{
                    width: '64px',
                    padding: '6px 8px',
                    fontSize: '0.88rem',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border, #d1d5db)',
                    background: 'var(--color-surface, #ffffff)',
                    color: 'var(--color-text, #111827)',
                    textAlign: 'center',
                    fontWeight: 600,
                  }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Max:</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={maxCount}
                  disabled={updateSettingsMutation.isPending}
                  onChange={(e) => {
                    const val = Math.max(1, parseInt(e.target.value, 10) || 1);
                    setMaxCount(val);
                  }}
                  onBlur={() => handleSaveNodePoolConfig(isDedicatedEnabled, selectedVmSize, minCount, maxCount)}
                  style={{
                    width: '64px',
                    padding: '6px 8px',
                    fontSize: '0.88rem',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border, #d1d5db)',
                    background: 'var(--color-surface, #ffffff)',
                    color: 'var(--color-text, #111827)',
                    textAlign: 'center',
                    fontWeight: 600,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Row 4: Active Workloads & Switchover Summary */}
          <div
            style={{
              marginTop: '16px',
              padding: '14px 18px',
              borderRadius: '10px',
              background: 'var(--color-surface-hover, #f9fafb)',
              border: '1px solid var(--color-border, #e5e7eb)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Zap size={18} style={{ color: 'var(--color-warning, #f59e0b)' }} />
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text)' }}>
                  Active Application Workloads ({appWorkloads.total_apps} Pods)
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  Current Target Pool: <code>{isDedicatedEnabled ? 'apppool' : 'userpoolv2'}</code>
                  {appNodePool.status_message && ` &bull; ${appNodePool.status_message}`}
                </div>
              </div>
            </div>

            <button
              onClick={handleManualSwitchover}
              disabled={switchoverMutation.isPending || updateSettingsMutation.isPending}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 14px',
                borderRadius: '8px',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: 'var(--color-primary, #1b6ef3)',
                color: '#ffffff',
                border: 'none',
                cursor: switchoverMutation.isPending ? 'not-allowed' : 'pointer',
                opacity: switchoverMutation.isPending ? 0.7 : 1,
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              }}
              title="Reschedule all running application pods onto the active node pool"
            >
              <RefreshCw size={13} className={switchoverMutation.isPending ? 'spin' : ''} />
              <span>{switchoverMutation.isPending ? 'Switching over...' : 'Reschedule & Sync Pods'}</span>
            </button>
          </div>
        </div>

        {/* Section 2: Platform Services & Orchestration */}
        <div className="ws-section">
          <h2 className="ws-section-header">Platform Services &amp; Orchestration</h2>

          {/* Airflow Webserver Setting Row */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Layers size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Apache Airflow Webserver
                </span>
                {webserverStatus === 'running' && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '2px 8px',
                      borderRadius: 999,
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      background: 'var(--color-success-bg, rgba(34, 197, 94, 0.1))',
                      color: 'var(--color-success, #22c55e)',
                      border: '1px solid var(--color-success, #22c55e)',
                    }}
                  >
                    <CheckCircle2 size={11} />
                    RUNNING ({airflow.webserver_available_replicas || 1}/1)
                  </span>
                )}
                {webserverStatus === 'starting' && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '2px 8px',
                      borderRadius: 999,
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      background: 'var(--color-primary-bg, rgba(27, 110, 243, 0.1))',
                      color: 'var(--color-primary, #1b6ef3)',
                      border: '1px solid var(--color-primary, #1b6ef3)',
                    }}
                  >
                    <Loader2 size={11} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                    STARTING...
                  </span>
                )}
                {webserverStatus === 'stopped' && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '2px 8px',
                      borderRadius: 999,
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      background: 'var(--color-surface-hover, #f3f4f6)',
                      color: 'var(--color-text-muted, #6b7280)',
                      border: '1px solid var(--color-border, #e5e7eb)',
                    }}
                  >
                    STOPPED (0/0)
                  </span>
                )}
              </div>
              <div className="ws-setting-desc">
                Native Apache Airflow Web UI for direct DAG monitoring and manual trigger execution. Disabled by default
                to reduce cluster compute and memory footprint, as CompassX provides built-in Jobs and Pipeline execution management.
              </div>
            </div>

            <div className="ws-setting-control" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {webserverStatus === 'running' && (
                <a
                  href="/airflow"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ws-link-btn"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 12px',
                    borderRadius: 8,
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    textDecoration: 'none',
                    background: 'var(--color-surface-hover, #f3f4f6)',
                    color: 'var(--color-primary, #1b6ef3)',
                    border: '1px solid var(--color-border, #e5e7eb)',
                  }}
                  title="Open native Airflow Web UI in a new tab"
                >
                  <span>Open Airflow UI</span>
                  <ExternalLink size={13} />
                </a>
              )}

              <label
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  width: '46px',
                  height: '26px',
                  cursor: updateSettingsMutation.isPending ? 'not-allowed' : 'pointer',
                  opacity: updateSettingsMutation.isPending ? 0.6 : 1,
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={isWebserverEnabled}
                  disabled={updateSettingsMutation.isPending}
                  onChange={(e) => handleToggleAirflowWebserver(e.target.checked)}
                  style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
                />
                <span
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: isWebserverEnabled ? 'var(--color-primary, #1b6ef3)' : 'var(--color-border, #d1d5db)',
                    borderRadius: '26px',
                    transition: 'all 0.25s ease',
                    boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)',
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      content: '""',
                      height: '20px',
                      width: '20px',
                      left: isWebserverEnabled ? '23px' : '3px',
                      bottom: '3px',
                      backgroundColor: '#ffffff',
                      borderRadius: '50%',
                      transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    }}
                  />
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Section: Notebooks & Compute Node Pool Isolation (Scale-to-Zero) */}
        <div className="ws-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h2 className="ws-section-header" style={{ margin: 0 }}>Notebooks &amp; Compute Node Pool Isolation</h2>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                Isolate notebook sessions and serverless compute pods onto a dedicated user node pool (<code>computepool</code>) with Scale-to-Zero ($0 idle compute cost). System and platform services remain on the system node pool.
              </div>
            </div>

            {/* Status Badge */}
            <div>
              {computeIsProvisioning && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background:
                      computeAction === 'deprovisioning' || compute.status === 'deprovisioning'
                        ? 'rgba(245, 158, 11, 0.12)'
                        : 'rgba(27, 110, 243, 0.1)',
                    color:
                      computeAction === 'deprovisioning' || compute.status === 'deprovisioning'
                        ? '#d97706'
                        : '#1b6ef3',
                    border:
                      computeAction === 'deprovisioning' || compute.status === 'deprovisioning'
                        ? '1px solid #f59e0b'
                        : '1px solid #1b6ef3',
                  }}
                >
                  <Loader2 size={12} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  {computeAction === 'deprovisioning' || compute.status === 'deprovisioning'
                    ? 'DEPROVISIONING ON CLUSTER...'
                    : 'PROVISIONING ON CLUSTER...'}
                </span>
              )}

              {!computeIsProvisioning && isComputeDedicated && computeIsProvisioned && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: 'var(--color-success-bg, rgba(34, 197, 94, 0.1))',
                    color: 'var(--color-success, #22c55e)',
                    border: '1px solid var(--color-success, #22c55e)',
                  }}
                >
                  <CheckCircle2 size={12} />
                  {computeMinCount === 0
                    ? `SCALE-TO-ZERO ACTIVE (${compute.compute_pool?.ready_nodes || 0} Nodes - $0/hr Idle)`
                    : `DEDICATED POOL ACTIVE (${compute.compute_pool?.ready_nodes || 0} Nodes)`}
                </span>
              )}

              {!computeIsProvisioning && isComputeDedicated && !computeIsProvisioned && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: 'rgba(245, 158, 11, 0.12)',
                    color: '#d97706',
                    border: '1px solid rgba(245, 158, 11, 0.4)',
                  }}
                >
                  <AlertTriangle size={12} />
                  NOT PROVISIONED ON CLUSTER
                </span>
              )}

              {!computeIsProvisioning && !isComputeDedicated && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '4px 10px',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: 'var(--color-surface-hover, #f3f4f6)',
                    color: 'var(--color-text-muted, #6b7280)',
                    border: '1px solid var(--color-border, #e5e7eb)',
                  }}
                >
                  <Server size={12} />
                  SHARED USER POOL ({compute.default_pool_name || 'userpoolv2'})
                </span>
              )}
            </div>
          </div>

          {/* Row 1: Dedicated Compute Pool Toggle */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Box size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Run Compute Pods on Dedicated Pool (<code>computepool</code>)
                </span>
              </div>
              <div className="ws-setting-desc">
                When enabled, all notebook kernels and serverless compute run exclusively on a dedicated user node pool (<code>computepool</code>) with Scale-to-Zero support (<code>min_count: 0</code>).
                When disabled, compute pods are gracefully migrated to the shared node pool (<code>userpoolv2</code>) and <code>computepool</code> is deprovisioned.
              </div>
            </div>

            <div className="ws-setting-control">
              <label
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  width: '46px',
                  height: '26px',
                  cursor: updateSettingsMutation.isPending || deprovisionComputeMutation.isPending ? 'not-allowed' : 'pointer',
                  opacity: updateSettingsMutation.isPending || deprovisionComputeMutation.isPending ? 0.6 : 1,
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={isComputeDedicated}
                  disabled={updateSettingsMutation.isPending || deprovisionComputeMutation.isPending}
                  onChange={(e) => handleToggleComputeDedicated(e.target.checked)}
                  style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
                />
                <span
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: isComputeDedicated ? 'var(--color-primary, #1b6ef3)' : 'var(--color-border, #d1d5db)',
                    borderRadius: '26px',
                    transition: 'all 0.25s ease',
                    boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)',
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      content: '""',
                      height: '20px',
                      width: '20px',
                      left: isComputeDedicated ? '23px' : '3px',
                      bottom: '3px',
                      backgroundColor: '#ffffff',
                      borderRadius: '50%',
                      transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    }}
                  />
                </span>
              </label>
            </div>
          </div>

          {/* Row 2: Compute VM Size Selection */}
          <div className="ws-setting-item" style={{ alignItems: 'flex-start' }}>
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Cpu size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Compute Node Pool Virtual Machine Type
                </span>
                {computeVmMeta && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      background: 'var(--color-primary-bg, rgba(27, 110, 243, 0.1))',
                      color: 'var(--color-primary, #1b6ef3)',
                    }}
                  >
                    {computeVmMeta.cpu} vCPU &bull; {computeVmMeta.memory_gib} GiB RAM &bull; {computeVmMeta.architecture}
                  </span>
                )}
              </div>
              <div className="ws-setting-desc">
                Select the virtual machine instance type for notebook &amp; serverless compute. Notebook hardware options in the sidebar will be dynamically gated by this VM&apos;s RAM capacity ({computeVmMeta?.memory_gib || 16} GiB limit).
              </div>

              {computeVmMeta && (
                <div
                  style={{
                    marginTop: '8px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    fontSize: '0.8rem',
                    background: 'var(--color-surface-hover, rgba(0,0,0,0.02))',
                    border: '1px solid var(--color-border, #e5e7eb)',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>{computeVmMeta.category}: </span>
                  {computeVmMeta.description}
                </div>
              )}
            </div>

            <div className="ws-setting-control" style={{ minWidth: '280px' }}>
              <select
                value={computeVmSize}
                disabled={updateSettingsMutation.isPending}
                onChange={(e) => {
                  const newVm = e.target.value;
                  setComputeVmSize(newVm);
                  handleSaveComputeConfig({ vmSize: newVm });
                }}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  background: 'var(--color-surface, #ffffff)',
                  border: '1px solid var(--color-border, #d1d5db)',
                  color: 'var(--color-text)',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                {vmSizesCatalog.map((vm) => (
                  <option key={vm.id} value={vm.id}>
                    {vm.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 3: Auto-Stop Idle Compute */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Zap size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Auto-Stop Inactive Compute
                </span>
                {isAutoStopEnabled && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 999,
                      background: 'var(--color-success-bg, rgba(34, 197, 94, 0.1))',
                      color: 'var(--color-success, #22c55e)',
                      border: '1px solid var(--color-success, #22c55e)',
                    }}
                  >
                    {autoStopMinutes} min inactivity
                  </span>
                )}
              </div>
              <div className="ws-setting-desc">
                When enabled, idle compute pods and Jupyter kernels automatically shut down after no cell executions or WebSocket activity during the inactivity window.
              </div>
            </div>

            <div className="ws-setting-control">
              <label
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  width: '46px',
                  height: '26px',
                  cursor: updateSettingsMutation.isPending ? 'not-allowed' : 'pointer',
                  opacity: updateSettingsMutation.isPending ? 0.6 : 1,
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={isAutoStopEnabled}
                  disabled={updateSettingsMutation.isPending}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setIsAutoStopEnabled(checked);
                    handleSaveComputeAutoStop(checked, autoStopMinutes);
                  }}
                  style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
                />
                <span
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: isAutoStopEnabled ? 'var(--color-primary, #1b6ef3)' : 'var(--color-border, #d1d5db)',
                    borderRadius: '26px',
                    transition: 'all 0.25s ease',
                    boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)',
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      content: '""',
                      height: '20px',
                      width: '20px',
                      left: isAutoStopEnabled ? '23px' : '3px',
                      bottom: '3px',
                      backgroundColor: '#ffffff',
                      borderRadius: '50%',
                      transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    }}
                  />
                </span>
              </label>
            </div>
          </div>

          {/* Row: Compute Node Pool Scaling & Node Limits (Min & Max) */}
          <div className="ws-setting-item" style={{ alignItems: 'flex-start' }}>
            <div className="ws-setting-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <Layers size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                <span className="ws-setting-label" style={{ margin: 0 }}>
                  Autoscaling Node Limits (Min &amp; Max Nodes)
                </span>
                {computeMinCount === 0 && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 999,
                      background: 'var(--color-success-bg, rgba(34, 197, 94, 0.1))',
                      color: 'var(--color-success, #22c55e)',
                      border: '1px solid var(--color-success, #22c55e)',
                    }}
                  >
                    SCALE-TO-ZERO ENABLED ($0 Idle Cost)
                  </span>
                )}
              </div>
              <div className="ws-setting-desc">
                Configure minimum and maximum virtual machine nodes for <code>computepool</code>. Set Minimum Nodes to <strong>0</strong> to enable automatic Scale-to-Zero so idle nodes are automatically deallocated when all notebooks are inactive.
              </div>

              {/* Quick Min Count Presets */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Min Nodes:</span>
                {[
                  { label: '0 (Scale-to-Zero - $0/hr idle)', val: 0 },
                  { label: '1 (Always Warm)', val: 1 },
                  { label: '2 (High Concurrency)', val: 2 },
                ].map((preset) => (
                  <button
                    key={preset.val}
                    type="button"
                    disabled={updateSettingsMutation.isPending || computeIsProvisioning}
                    onClick={() => {
                      setComputeMinCount(preset.val);
                      handleSaveComputeConfig({ minCount: preset.val });
                    }}
                    style={{
                      padding: '5px 12px',
                      borderRadius: '6px',
                      fontSize: '0.8rem',
                      fontWeight: 500,
                      cursor: computeIsProvisioning ? 'not-allowed' : 'pointer',
                      border: computeMinCount === preset.val ? '1px solid var(--color-primary, #1b6ef3)' : '1px solid var(--color-border, #e5e7eb)',
                      background: computeMinCount === preset.val ? 'var(--color-primary-bg, #ebf2ff)' : 'var(--color-surface, #ffffff)',
                      color: computeMinCount === preset.val ? 'var(--color-primary, #1b6ef3)' : 'var(--color-text, #374151)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ws-setting-control" style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Min:</label>
                <input
                  type="number"
                  min={0}
                  max={50}
                  value={computeMinCount}
                  disabled={updateSettingsMutation.isPending || computeIsProvisioning}
                  onChange={(e) => {
                    const val = Math.max(0, parseInt(e.target.value, 10) || 0);
                    setComputeMinCount(val);
                  }}
                  onBlur={() => handleSaveComputeConfig({ minCount: computeMinCount })}
                  style={{
                    width: '64px',
                    padding: '6px 8px',
                    fontSize: '0.88rem',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border, #d1d5db)',
                    background: 'var(--color-surface, #ffffff)',
                    color: 'var(--color-text, #111827)',
                    textAlign: 'center',
                    fontWeight: 600,
                  }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Max:</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={computeMaxCount}
                  disabled={updateSettingsMutation.isPending || computeIsProvisioning}
                  onChange={(e) => {
                    const val = Math.max(1, parseInt(e.target.value, 10) || 1);
                    setComputeMaxCount(val);
                  }}
                  onBlur={() => handleSaveComputeConfig({ maxCount: computeMaxCount })}
                  style={{
                    width: '64px',
                    padding: '6px 8px',
                    fontSize: '0.88rem',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border, #d1d5db)',
                    background: 'var(--color-surface, #ffffff)',
                    color: 'var(--color-text, #111827)',
                    textAlign: 'center',
                    fontWeight: 600,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Row 4: Inactivity Duration Selection */}
          {isAutoStopEnabled && (
            <div className="ws-setting-item" style={{ alignItems: 'flex-start' }}>
              <div className="ws-setting-info">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <Clock size={17} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
                  <span className="ws-setting-label" style={{ margin: 0 }}>
                    Inactivity Timeout Duration
                  </span>
                </div>
                <div className="ws-setting-desc">
                  Specify how long compute should remain idle before automatic suspension. Default is 5 minutes.
                </div>

                {/* Quick Presets */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
                  {[
                    { label: '5 min (Default)', val: 5 },
                    { label: '10 min', val: 10 },
                    { label: '15 min', val: 15 },
                    { label: '30 min', val: 30 },
                    { label: '60 min', val: 60 },
                  ].map((preset) => (
                    <button
                      key={preset.val}
                      type="button"
                      disabled={updateSettingsMutation.isPending}
                      onClick={() => {
                        setAutoStopMinutes(preset.val);
                        handleSaveComputeAutoStop(isAutoStopEnabled, preset.val);
                      }}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '6px',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                        border: autoStopMinutes === preset.val ? '1px solid var(--color-primary, #1b6ef3)' : '1px solid var(--color-border, #e5e7eb)',
                        background: autoStopMinutes === preset.val ? 'var(--color-primary-bg, #ebf2ff)' : 'var(--color-surface, #ffffff)',
                        color: autoStopMinutes === preset.val ? 'var(--color-primary, #1b6ef3)' : 'var(--color-text, #374151)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="ws-setting-control" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="number"
                  min={1}
                  max={720}
                  value={autoStopMinutes}
                  disabled={updateSettingsMutation.isPending}
                  onChange={(e) => {
                    const val = Math.max(1, parseInt(e.target.value, 10) || 1);
                    setAutoStopMinutes(val);
                  }}
                  onBlur={() => handleSaveComputeAutoStop(isAutoStopEnabled, autoStopMinutes)}
                  style={{
                    width: '72px',
                    padding: '6px 10px',
                    fontSize: '0.88rem',
                    borderRadius: '6px',
                    border: '1px solid var(--color-border, #d1d5db)',
                    background: 'var(--color-surface, #ffffff)',
                    color: 'var(--color-text, #111827)',
                    textAlign: 'center',
                    fontWeight: 600,
                  }}
                />
                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>min</span>
              </div>
            </div>
          )}

          {/* Row 5: Active Compute Workloads & Switchover Summary */}
          <div
            style={{
              marginTop: '16px',
              padding: '14px 18px',
              borderRadius: '10px',
              background: 'var(--color-surface-hover, #f9fafb)',
              border: '1px solid var(--color-border, #e5e7eb)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Cpu size={18} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text)' }}>
                  Active Notebook &amp; Compute Workloads ({computeWorkloads.total_compute} Pods)
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  Target Pool: <code>{isComputeDedicated && computeIsProvisioned ? 'computepool' : (compute.default_pool_name || 'userpoolv2')}</code>
                  {compute.status_message && ` • ${compute.status_message}`}
                </div>
              </div>
            </div>

            <button
              onClick={handleManualComputeSwitchover}
              disabled={switchoverComputeMutation.isPending || updateSettingsMutation.isPending || computeIsProvisioning}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 14px',
                borderRadius: '8px',
                fontSize: '0.82rem',
                fontWeight: 600,
                background: 'var(--color-primary, #1b6ef3)',
                color: '#ffffff',
                border: 'none',
                cursor: switchoverComputeMutation.isPending || computeIsProvisioning ? 'not-allowed' : 'pointer',
                opacity: switchoverComputeMutation.isPending || computeIsProvisioning ? 0.7 : 1,
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              }}
              title="Reschedule all running compute and notebook pods onto the target node pool"
            >
              <RefreshCw size={13} className={switchoverComputeMutation.isPending ? 'spin' : ''} />
              <span>{switchoverComputeMutation.isPending ? 'Syncing Compute...' : 'Reschedule & Sync Compute Pods'}</span>
            </button>
          </div>

          {/* Row 6: Provision, Update & Deprovision Compute Pool Action Card */}
          <div
            style={{
              marginTop: '16px',
              padding: '16px 20px',
              borderRadius: '10px',
              background: computeIsProvisioning
                ? 'rgba(27, 110, 243, 0.04)'
                : !computeIsProvisioned
                ? 'rgba(245, 158, 11, 0.04)'
                : 'var(--color-surface-hover, #f9fafb)',
              border: computeIsProvisioning
                ? '1px solid rgba(27, 110, 243, 0.3)'
                : !computeIsProvisioned
                ? '1px solid rgba(245, 158, 11, 0.35)'
                : '1px solid var(--color-border, #e5e7eb)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flex: 1, minWidth: '260px' }}>
              <div
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: computeIsProvisioning
                    ? 'rgba(27, 110, 243, 0.1)'
                    : !computeIsProvisioned
                    ? 'rgba(245, 158, 11, 0.1)'
                    : 'rgba(34, 197, 94, 0.1)',
                  color: computeIsProvisioning
                    ? '#1b6ef3'
                    : !computeIsProvisioned
                    ? '#d97706'
                    : '#22c55e',
                }}
              >
                {computeIsProvisioning ? (
                  <Loader2 size={20} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                ) : !computeIsProvisioned ? (
                  <AlertTriangle size={20} />
                ) : (
                  <Server size={20} />
                )}
              </div>

              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--color-text)' }}>
                  Dedicated Compute Node Pool (<code>computepool</code>)
                  {!computeIsProvisioned && (
                    <span style={{ marginLeft: '8px', fontSize: '0.75rem', fontWeight: 500, color: '#d97706' }}>
                      (Not Provisioned on Cluster)
                    </span>
                  )}
                  {computeIsProvisioned && (
                    <span style={{ marginLeft: '8px', fontSize: '0.75rem', fontWeight: 500, color: '#22c55e' }}>
                      (Provisioned on Cluster)
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                  {compute.status_message ||
                    (!computeIsProvisioned
                      ? `Target VM: ${computeVmSize} • Bounds: ${computeMinCount} to ${computeMaxCount} nodes. Click 'Provision Compute Pool' to create it.`
                      : `Target VM: ${computeVmSize} • Bounds: ${computeMinCount} to ${computeMaxCount} nodes • Ready Nodes: ${compute.compute_pool?.ready_nodes || 0}`)}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              {/* If NOT provisioned, show prominent "Provision Compute Pool" button */}
              {!computeIsProvisioned && (
                <button
                  onClick={handleTriggerProvisionCompute}
                  disabled={computeIsProvisioning}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    background: 'var(--color-primary, #1b6ef3)',
                    color: '#ffffff',
                    border: 'none',
                    cursor: computeIsProvisioning ? 'not-allowed' : 'pointer',
                    opacity: computeIsProvisioning ? 0.7 : 1,
                    boxShadow: '0 1px 3px rgba(27, 110, 243, 0.25)',
                  }}
                  title="Provision dedicated compute pool on cluster"
                >
                  {computeIsProvisioning ? (
                    <Loader2 size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  ) : (
                    <Zap size={14} />
                  )}
                  <span>{computeIsProvisioning ? 'Provisioning Pool...' : 'Provision Compute Pool'}</span>
                </button>
              )}

              {/* If ALREADY provisioned, show Update button & Deprovision button */}
              {computeIsProvisioned && (
                <>
                  <button
                    onClick={handleTriggerProvisionCompute}
                    disabled={computeIsProvisioning}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '7px 14px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      background: 'var(--color-surface, #ffffff)',
                      color: 'var(--color-primary, #1b6ef3)',
                      border: '1px solid var(--color-primary, #1b6ef3)',
                      cursor: computeIsProvisioning ? 'not-allowed' : 'pointer',
                      opacity: computeIsProvisioning ? 0.7 : 1,
                    }}
                    title="Update cluster autoscaler min/max nodes and configuration"
                  >
                    {computeIsProvisioning ? (
                      <Loader2 size={13} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                    ) : (
                      <RefreshCw size={13} />
                    )}
                    <span>{computeIsProvisioning ? 'Updating Autoscaler...' : 'Update Autoscaler'}</span>
                  </button>

                  <button
                    onClick={handleTriggerDeprovisionCompute}
                    disabled={computeIsProvisioning}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '7px 14px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      background: 'transparent',
                      color: 'var(--color-danger, #ef4444)',
                      border: '1px solid var(--color-danger, #ef4444)',
                      cursor: computeIsProvisioning ? 'not-allowed' : 'pointer',
                      opacity: computeIsProvisioning ? 0.6 : 1,
                    }}
                    title="Gracefully migrate compute pods to shared user pool and delete this node pool"
                  >
                    <Trash2 size={13} />
                    <span>Deprovision Compute Pool</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Section 3: Account & System Information */}
        <div className="ws-section">
          <h2 className="ws-section-header">Account &amp; System Information</h2>
          
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Account Name</div>
              <div className="ws-setting-desc">The primary organization name associated with this deployment.</div>
            </div>
            <div className="ws-setting-control">
              <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text)' }}>
                {accountData?.account_name || 'CompassX'}
              </span>
            </div>
          </div>

          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Account Slug &amp; ID</div>
              <div className="ws-setting-desc">Unique identifier used for control plane routing and scoping.</div>
            </div>
            <div className="ws-setting-control">
              <code style={{ fontSize: '0.8rem', padding: '3px 8px', background: 'var(--color-surface-hover)', borderRadius: '6px' }}>
                {accountData?.account_slug || 'default'} ({accountData?.account_id || 'default-account'})
              </code>
            </div>
          </div>

          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Control Plane Engine</div>
              <div className="ws-setting-desc">Multi-tenant Kubernetes runtime engine status.</div>
            </div>
            <div className="ws-setting-control">
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: '0.82rem',
                  fontWeight: 500,
                  color: 'var(--color-text-muted)',
                }}
              >
                <Server size={14} />
                Kubernetes Cloud
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
