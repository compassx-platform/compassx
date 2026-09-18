import React, { useState, useEffect } from 'react';
import {
  Layers,
  ExternalLink,
  ShieldCheck,
  Server,
  Info,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  Cpu,
  HardDrive,
  RefreshCw,
  Box,
  Sliders,
  Sparkles,
  Zap,
} from 'lucide-react';
import {
  useAccountSettings,
  useUpdateAccountSettings,
  useSwitchoverAppNodePool,
  VmSizeOption,
} from '@/lib/accountSettingsApi';
import { useToast } from '@/lib/toast';
import '../workspace/workspace-settings.css';

export default function AccountSettingsPage() {
  const toast = useToast();
  const { data: accountData, isLoading, error } = useAccountSettings();
  const updateSettingsMutation = useUpdateAccountSettings();
  const switchoverMutation = useSwitchoverAppNodePool();

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

  // Sync state when data arrives
  useEffect(() => {
    if (appNodePool) {
      setIsDedicatedEnabled(Boolean(appNodePool.dedicated_pool_enabled));
      if (appNodePool.vm_size) setSelectedVmSize(appNodePool.vm_size);
      if (appNodePool.min_count !== undefined) setMinCount(Number(appNodePool.min_count));
      if (appNodePool.max_count !== undefined) setMaxCount(Number(appNodePool.max_count));
    }
  }, [appNodePool.dedicated_pool_enabled, appNodePool.vm_size, appNodePool.min_count, appNodePool.max_count]);

  const vmSizesCatalog: VmSizeOption[] = appNodePool.vm_sizes_catalog || [
    {
      id: 'Standard_B2s_v2',
      name: 'Standard_B2s_v2',
      label: 'Standard_B2s_v2 (2 vCPU, 4 GiB RAM)',
      cpu: 2,
      memory_gib: 4,
      architecture: 'x86_64',
      category: 'Burstable (General Purpose)',
      description: 'Economical burstable VM ideal for lightweight apps, dev environments, and dashboards.',
      recommended: true,
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

  const handleSaveNodePoolConfig = (newDedicatedVal?: boolean, newVmSize?: string) => {
    const dedicated = newDedicatedVal !== undefined ? newDedicatedVal : isDedicatedEnabled;
    const vmSize = newVmSize !== undefined ? newVmSize : selectedVmSize;

    updateSettingsMutation.mutate(
      {
        app_node_pool: {
          dedicated_pool_enabled: dedicated,
          vm_size: vmSize,
          min_count: minCount,
          max_count: maxCount,
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
                Select the Azure VM instance size for the dedicated app node pool. Higher capacity VMs provide dedicated compute
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

          {/* Row 3: Active Workloads & Switchover Summary */}
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
                {accountData.account_name}
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
                {accountData.account_slug} ({accountData.account_id})
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
                Kubernetes Cloud (AKS)
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
