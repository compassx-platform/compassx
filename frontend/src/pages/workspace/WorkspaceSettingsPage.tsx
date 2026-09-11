import React, { useState, useEffect } from 'react';
import {
  ChevronDown,
  ExternalLink,
  Pencil,
  Check,
  X,
  Plus,
  Trash2,
  Sliders,
  Sparkles,
  Server,
  Package,
  Layers,
  ShieldCheck,
  Clock,
  Cpu,
} from 'lucide-react';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useCurrentWorkspaceSlug } from '@/lib/appNavigation';
import {
  useWorkspaceSettings,
  useUpdateWorkspaceSettings,
  type WorkspaceSettings,
  type PackageRepositoriesConfig,
  type BaseEnvironmentsConfig,
  type ServerlessUsagePoliciesConfig,
  type ClassicComputePoliciesConfig,
} from '@/lib/workspaceSettingsApi';
import { useToast } from '@/lib/toast';
import './workspace-settings.css';

export default function WorkspaceSettingsPage() {
  const workspaceCtx = useWorkspaceContext();
  const workspaceSlug = useCurrentWorkspaceSlug() || workspaceCtx?.slug || 'default';
  const toast = useToast();

  const { data: settings, isLoading } = useWorkspaceSettings(workspaceSlug);
  const updateSettingsMutation = useUpdateWorkspaceSettings(workspaceSlug);

  // Timeout inline editing state
  const [isEditingTimeout, setIsEditingTimeout] = useState(false);
  const [timeoutValue, setTimeoutValue] = useState<number>(9000);

  // Modals state
  const [activeModal, setActiveModal] = useState<
    'package_repos' | 'base_envs' | 'serverless_policies' | 'classic_compute' | 'sql_warehouses' | null
  >(null);

  // Form states for modals
  const [pkgConfig, setPkgConfig] = useState<PackageRepositoriesConfig>({
    pypi_index_url: 'https://pypi.org/simple',
    pypi_extra_index_urls: [],
    npm_registry: 'https://registry.npmjs.org/',
    maven_central: 'https://repo1.maven.org/maven2/',
  });
  const [newExtraIndexUrl, setNewExtraIndexUrl] = useState('');

  const [baseEnvConfig, setBaseEnvConfig] = useState<BaseEnvironmentsConfig>({
    python_version: '3.11',
    spark_version: '3.5.0',
    preinstalled_packages: ['pandas>=2.0.0', 'numpy>=1.24.0', 'scikit-learn>=1.3.0', 'plotly>=5.15.0'],
    environment_variables: { PYTHONUNBUFFERED: '1' },
  });
  const [packagesText, setPackagesText] = useState('');

  const [policyConfig, setPolicyConfig] = useState<ServerlessUsagePoliciesConfig>({
    enforce_cost_tags: true,
    required_tags: ['Environment', 'CostCenter', 'Project'],
    max_runtime_hours_per_day: 24,
    max_concurrent_queries: 10,
    cost_alert_threshold: 1000,
  });
  const [newTagKey, setNewTagKey] = useState('');

  const [classicConfig, setClassicConfig] = useState<ClassicComputePoliciesConfig>({
    allow_unrestricted_cluster_creation: false,
    default_node_type: 'standard_d4s_v5',
    max_nodes: 8,
    auto_termination_minutes: 60,
    cluster_tags: { ManagedBy: 'CompassX', Tier: 'Workspace' },
  });

  useEffect(() => {
    if (settings) {
      setTimeoutValue(settings.serverless_interactive_timeout || 9000);
      if (settings.package_repositories) {
        setPkgConfig(settings.package_repositories);
      }
      if (settings.base_environments) {
        setBaseEnvConfig(settings.base_environments);
        setPackagesText((settings.base_environments.preinstalled_packages || []).join('\n'));
      }
      if (settings.serverless_usage_policies) {
        setPolicyConfig(settings.serverless_usage_policies);
      }
      if (settings.classic_compute_policies) {
        setClassicConfig(settings.classic_compute_policies);
      }
    }
  }, [settings]);

  const handleWarehouseChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    updateSettingsMutation.mutate(
      { default_warehouse: val },
      {
        onSuccess: () => {
          toast.success('Default warehouse updated successfully.');
        },
        onError: () => {
          toast.error('Failed to update default warehouse.');
        },
      }
    );
  };

  const handleSaveTimeout = () => {
    const parsed = Number(timeoutValue);
    if (isNaN(parsed) || parsed <= 0) {
      toast.error('Please enter a valid positive timeout in seconds.');
      return;
    }
    updateSettingsMutation.mutate(
      { serverless_interactive_timeout: parsed },
      {
        onSuccess: () => {
          setIsEditingTimeout(false);
          toast.success('Execution timeout updated successfully.');
        },
        onError: () => {
          toast.error('Failed to update timeout.');
        },
      }
    );
  };

  const handleSavePackageRepos = () => {
    updateSettingsMutation.mutate(
      { package_repositories: pkgConfig },
      {
        onSuccess: () => {
          setActiveModal(null);
          toast.success('Package repositories settings updated.');
        },
        onError: () => {
          toast.error('Failed to update package repositories.');
        },
      }
    );
  };

  const handleSaveBaseEnvs = () => {
    const pkgs = packagesText
      .split('\n')
      .map((p) => p.trim())
      .filter(Boolean);
    const updated = { ...baseEnvConfig, preinstalled_packages: pkgs };
    updateSettingsMutation.mutate(
      { base_environments: updated },
      {
        onSuccess: () => {
          setActiveModal(null);
          toast.success('Base environments configuration updated.');
        },
        onError: () => {
          toast.error('Failed to update base environments.');
        },
      }
    );
  };

  const handleSavePolicies = () => {
    updateSettingsMutation.mutate(
      { serverless_usage_policies: policyConfig },
      {
        onSuccess: () => {
          setActiveModal(null);
          toast.success('Serverless usage policies updated.');
        },
        onError: () => {
          toast.error('Failed to update policies.');
        },
      }
    );
  };

  const handleSaveClassicCompute = () => {
    updateSettingsMutation.mutate(
      { classic_compute_policies: classicConfig },
      {
        onSuccess: () => {
          setActiveModal(null);
          toast.success('Classic compute configuration updated.');
        },
        onError: () => {
          toast.error('Failed to update classic compute.');
        },
      }
    );
  };

  return (
    <div className="ws-settings-page animate-fade-in">
      {/* Page Header */}
      <div className="ws-settings-header">
        <h1 className="ws-settings-title">Workspace Settings</h1>
        <div className="ws-settings-subtitle">
          <span>{workspaceCtx?.name || workspaceSlug}</span>
          <span className="ws-settings-badge">Active</span>
          {workspaceCtx?.current_user_role && (
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              Role: <strong>{workspaceCtx.current_user_role.replace(/_/g, ' ')}</strong>
            </span>
          )}
        </div>
      </div>

      <div className="ws-settings-container">
        {/* ── 1. Compute Section ── */}
        <section className="ws-section">
          <h2 className="ws-section-header">Compute</h2>

          {/* Default Warehouse */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Default warehouse</div>
              <p className="ws-setting-desc">
                Choose a warehouse to be selected by default for users in this workspace. Covers SQL workloads only and can
                be overridden by users.
              </p>
            </div>
            <div className="ws-setting-control">
              <div className="ws-select-wrap">
                <select
                  className="ws-select"
                  value={settings?.default_warehouse || 'last_selected'}
                  onChange={handleWarehouseChange}
                  disabled={isLoading || updateSettingsMutation.isPending}
                >
                  <option value="last_selected">Last selected</option>
                  <option value="default">Default DuckDB Warehouse</option>
                  <option value="serverless_starter">Serverless SQL Starter</option>
                  <option value="analytics_large">Analytics Large Warehouse</option>
                </select>
                <ChevronDown size={14} className="ws-select-arrow" />
              </div>
            </div>
          </div>

          {/* SQL warehouses and serverless compute */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">SQL warehouses and serverless compute</div>
              <p className="ws-setting-desc">
                Manage shared SQL warehouses, auto-stop parameters, cluster sizing, and serverless compute pools.
              </p>
            </div>
            <div className="ws-setting-control">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal('sql_warehouses')}
              >
                Manage
              </button>
            </div>
          </div>
        </section>

        {/* ── 2. Environments Section ── */}
        <section className="ws-section">
          <h2 className="ws-section-header">Environments</h2>

          {/* Default package repositories */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Default package repositories</div>
              <p className="ws-setting-desc">
                Set the default Python, npm, and Maven package repositories that workloads in this workspace install
                libraries from.
              </p>
            </div>
            <div className="ws-setting-control">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal('package_repos')}
              >
                Manage
              </button>
            </div>
          </div>

          {/* Workspace base environments for serverless compute */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Workspace base environments for serverless compute</div>
              <p className="ws-setting-desc">
                Workspace base environments ensure workspace users automatically have a predefined environment version
                and set of Python packages available in their notebooks.
              </p>
            </div>
            <div className="ws-setting-control">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal('base_envs')}
              >
                Manage
              </button>
            </div>
          </div>
        </section>

        {/* ── 3. Policies Section ── */}
        <section className="ws-section">
          <h2 className="ws-section-header">Policies</h2>

          {/* Serverless usage policies */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Serverless usage policies</div>
              <p className="ws-setting-desc">
                Serverless usage policies allow administrators to enforce certain cost attribution tags for serverless
                compute in notebooks, jobs, and DLT pipelines. Each policy can be assigned to users, groups, or service
                principals in order to enforce tagging requirements.{' '}
                <a
                  href="#learn-more"
                  onClick={(e) => {
                    e.preventDefault();
                    setActiveModal('serverless_policies');
                  }}
                  className="ws-link"
                >
                  Learn more <ExternalLink size={12} />
                </a>
              </p>
            </div>
            <div className="ws-setting-control">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal('serverless_policies')}
              >
                Manage
              </button>
            </div>
          </div>
        </section>

        {/* ── 4. Serverless Interactive Section ── */}
        <section className="ws-section">
          <h2 className="ws-section-header">Serverless interactive</h2>

          {/* Serverless interactive execution timeout */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Serverless interactive execution timeout</div>
              <p className="ws-setting-desc">
                Default timeout in seconds for interactive serverless queries.{' '}
                <a
                  href="#learn-more"
                  onClick={(e) => {
                    e.preventDefault();
                    setIsEditingTimeout(true);
                  }}
                  className="ws-link"
                >
                  Learn more
                </a>
              </p>
            </div>
            <div className="ws-setting-control">
              {isEditingTimeout ? (
                <div className="ws-inline-edit">
                  <input
                    type="number"
                    className="ws-inline-input"
                    value={timeoutValue}
                    onChange={(e) => setTimeoutValue(Number(e.target.value))}
                    min={1}
                    autoFocus
                  />
                  <button
                    type="button"
                    className="ws-btn-icon-action ws-btn-icon-save"
                    onClick={handleSaveTimeout}
                    title="Save"
                  >
                    <Check size={14} />
                  </button>
                  <button
                    type="button"
                    className="ws-btn-icon-action ws-btn-icon-cancel"
                    onClick={() => {
                      setTimeoutValue(settings?.serverless_interactive_timeout || 9000);
                      setIsEditingTimeout(false);
                    }}
                    title="Cancel"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="ws-inline-edit">
                  <span className="ws-inline-value">
                    {settings?.serverless_interactive_timeout ?? timeoutValue}
                  </span>
                  <button
                    type="button"
                    className="ws-btn-icon-edit"
                    onClick={() => setIsEditingTimeout(true)}
                    title="Edit execution timeout"
                    aria-label="Edit execution timeout"
                  >
                    <Pencil size={14} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ── 5. Classic Compute Section ── */}
        <section className="ws-section">
          <h2 className="ws-section-header">Classic compute</h2>

          {/* Cluster policies & sizing */}
          <div className="ws-setting-item">
            <div className="ws-setting-info">
              <div className="ws-setting-label">Classic cluster policies and auto-termination</div>
              <p className="ws-setting-desc">
                Configure cluster instance types, worker scaling limits, and idle auto-termination presets for classic
                compute.
              </p>
            </div>
            <div className="ws-setting-control">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal('classic_compute')}
              >
                Manage
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* ── MODALS ── */}

      {/* 1. Package Repositories Modal */}
      {activeModal === 'package_repos' && (
        <div className="ws-modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="ws-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ws-modal-header">
              <h3 className="ws-modal-title">Default Package Repositories</h3>
              <button
                type="button"
                className="ws-modal-close"
                onClick={() => setActiveModal(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="ws-modal-body">
              <div className="ws-form-group">
                <label className="ws-form-label">PyPI Primary Index URL</label>
                <input
                  type="text"
                  className="ws-form-input"
                  value={pkgConfig.pypi_index_url}
                  onChange={(e) =>
                    setPkgConfig({ ...pkgConfig, pypi_index_url: e.target.value })
                  }
                  placeholder="https://pypi.org/simple"
                />
                <p className="ws-form-helper">
                  Default repository index for pip installations in notebooks and jobs.
                </p>
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">PyPI Extra Index URLs</label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input
                    type="text"
                    className="ws-form-input"
                    value={newExtraIndexUrl}
                    onChange={(e) => setNewExtraIndexUrl(e.target.value)}
                    placeholder="https://nexus.internal.org/repository/pypi/simple"
                  />
                  <button
                    type="button"
                    className="ws-btn-manage"
                    onClick={() => {
                      if (newExtraIndexUrl.trim()) {
                        setPkgConfig({
                          ...pkgConfig,
                          pypi_extra_index_urls: [
                            ...(pkgConfig.pypi_extra_index_urls || []),
                            newExtraIndexUrl.trim(),
                          ],
                        });
                        setNewExtraIndexUrl('');
                      }
                    }}
                  >
                    <Plus size={14} /> Add
                  </button>
                </div>
                {pkgConfig.pypi_extra_index_urls && pkgConfig.pypi_extra_index_urls.length > 0 && (
                  <div className="ws-tags-list">
                    {pkgConfig.pypi_extra_index_urls.map((url, idx) => (
                      <div key={idx} className="ws-tag-pill">
                        <span>{url}</span>
                        <button
                          type="button"
                          className="ws-tag-remove"
                          onClick={() => {
                            const filtered = pkgConfig.pypi_extra_index_urls.filter(
                              (_, i) => i !== idx
                            );
                            setPkgConfig({ ...pkgConfig, pypi_extra_index_urls: filtered });
                          }}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">NPM Registry URL</label>
                <input
                  type="text"
                  className="ws-form-input"
                  value={pkgConfig.npm_registry}
                  onChange={(e) =>
                    setPkgConfig({ ...pkgConfig, npm_registry: e.target.value })
                  }
                  placeholder="https://registry.npmjs.org/"
                />
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Maven Central URL</label>
                <input
                  type="text"
                  className="ws-form-input"
                  value={pkgConfig.maven_central}
                  onChange={(e) =>
                    setPkgConfig({ ...pkgConfig, maven_central: e.target.value })
                  }
                  placeholder="https://repo1.maven.org/maven2/"
                />
              </div>
            </div>
            <div className="ws-modal-footer">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                style={{ padding: '6px 18px', borderRadius: 6, fontSize: '0.84rem' }}
                onClick={handleSavePackageRepos}
                disabled={updateSettingsMutation.isPending}
              >
                {updateSettingsMutation.isPending ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Workspace Base Environments Modal */}
      {activeModal === 'base_envs' && (
        <div className="ws-modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="ws-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ws-modal-header">
              <h3 className="ws-modal-title">Workspace Base Environments</h3>
              <button
                type="button"
                className="ws-modal-close"
                onClick={() => setActiveModal(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="ws-modal-body">
              <div className="ws-form-group">
                <label className="ws-form-label">Default Python Version</label>
                <select
                  className="ws-form-input"
                  value={baseEnvConfig.python_version}
                  onChange={(e) =>
                    setBaseEnvConfig({ ...baseEnvConfig, python_version: e.target.value })
                  }
                >
                  <option value="3.11">Python 3.11 (Recommended - LTS)</option>
                  <option value="3.10">Python 3.10</option>
                  <option value="3.12">Python 3.12 (Latest)</option>
                </select>
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Apache Spark Runtime Version</label>
                <select
                  className="ws-form-input"
                  value={baseEnvConfig.spark_version}
                  onChange={(e) =>
                    setBaseEnvConfig({ ...baseEnvConfig, spark_version: e.target.value })
                  }
                >
                  <option value="3.5.0">Spark 3.5.0 (Scala 2.12)</option>
                  <option value="3.4.2">Spark 3.4.2</option>
                  <option value="3.3.4">Spark 3.3.4</option>
                </select>
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Pre-installed Python Packages (one per line)</label>
                <textarea
                  className="ws-form-textarea"
                  value={packagesText}
                  onChange={(e) => setPackagesText(e.target.value)}
                  placeholder="pandas>=2.0.0&#10;numpy>=1.24.0&#10;scikit-learn>=1.3.0&#10;plotly>=5.15.0"
                />
                <p className="ws-form-helper">
                  These packages are pre-warmed on serverless compute containers for immediate imports.
                </p>
              </div>
            </div>
            <div className="ws-modal-footer">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                style={{ padding: '6px 18px', borderRadius: 6, fontSize: '0.84rem' }}
                onClick={handleSaveBaseEnvs}
                disabled={updateSettingsMutation.isPending}
              >
                {updateSettingsMutation.isPending ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Serverless Usage Policies Modal */}
      {activeModal === 'serverless_policies' && (
        <div className="ws-modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="ws-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ws-modal-header">
              <h3 className="ws-modal-title">Serverless Usage Policies</h3>
              <button
                type="button"
                className="ws-modal-close"
                onClick={() => setActiveModal(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="ws-modal-body">
              <div className="ws-form-group">
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                    fontSize: '0.86rem',
                    fontWeight: 600,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={policyConfig.enforce_cost_tags}
                    onChange={(e) =>
                      setPolicyConfig({ ...policyConfig, enforce_cost_tags: e.target.checked })
                    }
                  />
                  <span>Enforce mandatory cost attribution tags</span>
                </label>
                <p className="ws-form-helper" style={{ marginLeft: 24 }}>
                  Blocks serverless execution if required tags are missing from notebooks or jobs.
                </p>
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Mandatory Cost Attribution Tags</label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input
                    type="text"
                    className="ws-form-input"
                    value={newTagKey}
                    onChange={(e) => setNewTagKey(e.target.value)}
                    placeholder="e.g. CostCenter, Environment, Team"
                  />
                  <button
                    type="button"
                    className="ws-btn-manage"
                    onClick={() => {
                      if (newTagKey.trim() && !policyConfig.required_tags.includes(newTagKey.trim())) {
                        setPolicyConfig({
                          ...policyConfig,
                          required_tags: [...policyConfig.required_tags, newTagKey.trim()],
                        });
                        setNewTagKey('');
                      }
                    }}
                  >
                    <Plus size={14} /> Add
                  </button>
                </div>
                <div className="ws-tags-list">
                  {policyConfig.required_tags.map((tag, idx) => (
                    <div key={idx} className="ws-tag-pill">
                      <span>{tag}</span>
                      <button
                        type="button"
                        className="ws-tag-remove"
                        onClick={() => {
                          const filtered = policyConfig.required_tags.filter((_, i) => i !== idx);
                          setPolicyConfig({ ...policyConfig, required_tags: filtered });
                        }}
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Max Concurrent Serverless Queries per User</label>
                <input
                  type="number"
                  className="ws-form-input"
                  value={policyConfig.max_concurrent_queries}
                  onChange={(e) =>
                    setPolicyConfig({
                      ...policyConfig,
                      max_concurrent_queries: Number(e.target.value),
                    })
                  }
                  min={1}
                />
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Monthly Cost Alert Threshold ($ USD)</label>
                <input
                  type="number"
                  className="ws-form-input"
                  value={policyConfig.cost_alert_threshold}
                  onChange={(e) =>
                    setPolicyConfig({
                      ...policyConfig,
                      cost_alert_threshold: Number(e.target.value),
                    })
                  }
                  min={0}
                />
              </div>
            </div>
            <div className="ws-modal-footer">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                style={{ padding: '6px 18px', borderRadius: 6, fontSize: '0.84rem' }}
                onClick={handleSavePolicies}
                disabled={updateSettingsMutation.isPending}
              >
                {updateSettingsMutation.isPending ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Classic Compute Modal */}
      {activeModal === 'classic_compute' && (
        <div className="ws-modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="ws-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ws-modal-header">
              <h3 className="ws-modal-title">Classic Compute Settings</h3>
              <button
                type="button"
                className="ws-modal-close"
                onClick={() => setActiveModal(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="ws-modal-body">
              <div className="ws-form-group">
                <label className="ws-form-label">Default Node Type</label>
                <select
                  className="ws-form-input"
                  value={classicConfig.default_node_type}
                  onChange={(e) =>
                    setClassicConfig({ ...classicConfig, default_node_type: e.target.value })
                  }
                >
                  <option value="standard_d4s_v5">Standard D4s v5 (4 vCPU, 16 GB RAM)</option>
                  <option value="standard_d8s_v5">Standard D8s v5 (8 vCPU, 32 GB RAM)</option>
                  <option value="standard_d16s_v5">Standard D16s v5 (16 vCPU, 64 GB RAM)</option>
                  <option value="local_duckdb">Local In-Process (DuckDB Runtime)</option>
                </select>
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Maximum Allowed Worker Nodes</label>
                <input
                  type="number"
                  className="ws-form-input"
                  value={classicConfig.max_nodes}
                  onChange={(e) =>
                    setClassicConfig({ ...classicConfig, max_nodes: Number(e.target.value) })
                  }
                  min={1}
                />
              </div>

              <div className="ws-form-group">
                <label className="ws-form-label">Auto-termination Threshold (Minutes of Inactivity)</label>
                <input
                  type="number"
                  className="ws-form-input"
                  value={classicConfig.auto_termination_minutes}
                  onChange={(e) =>
                    setClassicConfig({
                      ...classicConfig,
                      auto_termination_minutes: Number(e.target.value),
                    })
                  }
                  min={5}
                />
                <p className="ws-form-helper">
                  Clusters will automatically shut down when idle to reduce cloud infrastructure spend.
                </p>
              </div>
            </div>
            <div className="ws-modal-footer">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                style={{ padding: '6px 18px', borderRadius: 6, fontSize: '0.84rem' }}
                onClick={handleSaveClassicCompute}
                disabled={updateSettingsMutation.isPending}
              >
                {updateSettingsMutation.isPending ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. SQL Warehouses Management Modal */}
      {activeModal === 'sql_warehouses' && (
        <div className="ws-modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="ws-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ws-modal-header">
              <h3 className="ws-modal-title">SQL Warehouses & Serverless Compute</h3>
              <button
                type="button"
                className="ws-modal-close"
                onClick={() => setActiveModal(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="ws-modal-body">
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: '0.86rem', color: 'var(--color-text)', margin: '0 0 12px' }}>
                  Manage SQL warehouses and serverless compute clusters allocated to this workspace:
                </p>
                <div
                  style={{
                    border: '1px solid var(--color-border)',
                    borderRadius: 8,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 14px',
                      borderBottom: '1px solid var(--color-border)',
                      background: 'var(--color-surface-hover)',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.86rem' }}>Default DuckDB Warehouse</div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                        Engine: duckdb • Auto-created
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 999,
                        background: 'rgba(40,167,69,0.1)',
                        color: 'var(--color-success)',
                        border: '1px solid var(--color-success)',
                      }}
                    >
                      RUNNING
                    </span>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 14px',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.86rem' }}>Serverless SQL Starter</div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                        Engine: serverless • 2X-Small
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        padding: '2px 8px',
                        borderRadius: 999,
                        background: 'rgba(27,110,243,0.1)',
                        color: 'var(--color-primary)',
                        border: '1px solid var(--color-primary)',
                      }}
                    >
                      READY
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div className="ws-modal-footer">
              <button
                type="button"
                className="ws-btn-manage"
                onClick={() => setActiveModal(null)}
              >
                Close
              </button>
              <button
                type="button"
                className="btn-primary"
                style={{ padding: '6px 18px', borderRadius: 6, fontSize: '0.84rem' }}
                onClick={() => {
                  setActiveModal(null);
                  window.location.href = `/w/${workspaceSlug}/platform/sql-warehouse/warehouses`;
                }}
              >
                Go to Warehouses Console
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
