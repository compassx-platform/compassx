import { useState, useEffect } from 'react';
import JobLogViewer from './JobLogViewer';
import { computeApi } from '@/modules/compute/computeApi';

/**
 * Detail view for a compute resource with Configuration and Logs tabs.
 * @param {{ resource: any, onClose: () => void }} props
 */
export default function ComputeResourceDetail({ resource, onClose }) {
  const [tab, setTab] = useState('configuration');
  const [autoSuspend, setAutoSuspend] = useState(true);
  const [idleTimeout, setIdleTimeout] = useState(60);
  const [savingLifecycle, setSavingLifecycle] = useState(false);
  const [lifecycleMsg, setLifecycleMsg] = useState(null);

  useEffect(() => {
    if (resource?.id) {
      computeApi.getResourceLifecycle(resource.id)
        .then((data) => {
          if (data) {
            setAutoSuspend(data.auto_suspend_enabled ?? true);
            setIdleTimeout(data.idle_timeout_minutes ?? 60);
          }
        })
        .catch(() => {});
    }
  }, [resource?.id]);

  const handleSaveLifecycle = async (newAutoSuspend, newTimeout) => {
    setSavingLifecycle(true);
    setLifecycleMsg(null);
    try {
      await computeApi.updateResourceLifecycle(resource.id, {
        auto_suspend_enabled: newAutoSuspend,
        idle_timeout_minutes: Number(newTimeout),
      });
      setLifecycleMsg('Lifecycle settings updated successfully.');
      setTimeout(() => setLifecycleMsg(null), 3000);
    } catch (e) {
      setLifecycleMsg('Failed to update lifecycle settings.');
    } finally {
      setSavingLifecycle(false);
    }
  };

  const statusColor = {
    Running: '#10b981',
    Pending: '#f59e0b',
    Succeeded: '#6366f1',
    Failed: '#ef4444',
    Unknown: '#6b7280',
    Stopped: '#6b7280',
    Missing: '#f97316',
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'var(--color-surface)',
      zIndex: 500,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '24px',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            background: statusColor[resource.phase] || '#6b7280',
          }} />
          <div>
            <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>{resource.name}</h1>
            <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--color-text-muted)' }}>
              {resource.runtime} | {resource.profile}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: 'var(--color-text-muted)', padding: '8px' }}
        >
          x
        </button>
      </div>

      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', paddingLeft: '24px', background: 'var(--color-surface-secondary)' }}>
        {['configuration', 'logs'].map((tabName) => (
          <button
            key={tabName}
            onClick={() => setTab(tabName)}
            style={{
              padding: '12px 20px',
              background: tab === tabName ? 'var(--color-surface)' : 'transparent',
              color: tab === tabName ? 'var(--color-accent, #6366f1)' : 'var(--color-text)',
              border: 'none',
              fontSize: '14px',
              fontWeight: tab === tabName ? 600 : 500,
              cursor: 'pointer',
              textTransform: 'capitalize',
            }}
          >
            {tabName}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {tab === 'configuration' && (
          <div style={{ padding: '24px', display: 'flex', gap: '24px' }}>
            <div style={{ flex: 1 }}>
              <section style={{ marginBottom: '32px' }}>
                <h2 style={{ margin: '0 0 16px', fontSize: '15px', fontWeight: 600 }}>Resource Configuration</h2>
                <div style={{ border: '1px solid var(--color-border)', borderRadius: '8px', overflow: 'hidden' }}>
                  {[
                    ['Name', resource.name],
                    ['Runtime', resource.runtime],
                    ['Profile', resource.profile],
                    ['Created By', resource.created_by],
                    ['Deployment', resource.deployment_name || '-'],
                    ['Desired Status', resource.desired_status || '-'],
                    ['Created', new Date(resource.created_at).toLocaleString()],
                  ].map(([label, value], index, rows) => (
                    <div
                      key={label}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        borderBottom: index === rows.length - 1 ? 'none' : '1px solid var(--color-border)',
                      }}
                    >
                      <div style={{ padding: '12px 16px', background: 'var(--color-surface-secondary)', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                        {label}
                      </div>
                      <div style={{ padding: '12px 16px', fontSize: '13px', wordBreak: 'break-all' }}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {resource.description && (
                <section style={{ marginBottom: '24px' }}>
                  <h2 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>Description</h2>
                  <div style={{ padding: '12px 16px', background: 'var(--color-surface-secondary)', borderRadius: '6px', fontSize: '13px', lineHeight: '1.5' }}>
                    {resource.description}
                  </div>
                </section>
              )}

              {/* Lifecycle & Auto-Shutdown Section */}
              <section>
                <h2 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>Inactivity & Auto-Shutdown (Reaper)</h2>
                <div style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '16px 20px', background: 'var(--color-surface)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: 600 }}>Auto-Suspend Idle Runtime</span>
                      <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                        Automatically stop runtime pod when no notebooks or queries execute within timeout.
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={autoSuspend}
                      onChange={(e) => {
                        const val = e.target.checked;
                        setAutoSuspend(val);
                        handleSaveLifecycle(val, idleTimeout);
                      }}
                      disabled={savingLifecycle}
                      style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                    />
                  </div>

                  {autoSuspend && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--color-border)', paddingTop: '12px' }}>
                      <div>
                        <span style={{ fontSize: '13px', fontWeight: 500 }}>Idle Timeout Duration</span>
                        <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                          Time of zero active kernel executions before suspending compute.
                        </p>
                      </div>
                      <select
                        value={idleTimeout}
                        onChange={(e) => {
                          const val = Number(e.target.value);
                          setIdleTimeout(val);
                          handleSaveLifecycle(autoSuspend, val);
                        }}
                        disabled={savingLifecycle}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid var(--color-border)',
                          background: 'var(--color-surface-secondary)',
                          fontSize: '13px',
                        }}
                      >
                        <option value={15}>15 Minutes</option>
                        <option value={30}>30 Minutes</option>
                        <option value={60}>1 Hour (60 mins) — Default</option>
                        <option value={120}>2 Hours (120 mins)</option>
                        <option value={240}>4 Hours (240 mins)</option>
                      </select>
                    </div>
                  )}

                  {lifecycleMsg && (
                    <div style={{ fontSize: '12px', color: lifecycleMsg.includes('Failed') ? '#ef4444' : '#10b981' }}>
                      {lifecycleMsg}
                    </div>
                  )}
                </div>
              </section>
            </div>

            <div style={{ width: '300px', borderLeft: '1px solid var(--color-border)', paddingLeft: '24px', flexShrink: 0 }}>
              <h3 style={{ margin: '0 0 16px', fontSize: '14px', fontWeight: 600 }}>Summary</h3>
              {[
                ['Status', resource.phase || 'Unknown'],
                ['Runtime ID', resource.runtime_id ?? resource.pod_name],
                ['Started At', resource.started_at ? new Date(resource.started_at).toLocaleString() : null],
                ['Finished At', resource.finished_at ? new Date(resource.finished_at).toLocaleString() : null],
                ['Message', resource.message],
              ].filter(([, value]) => value).map(([label, value]) => (
                <div key={label} style={{ marginBottom: '20px' }}>
                  <p style={{ margin: '0 0 6px', fontSize: '12px', color: 'var(--color-text-muted)' }}>{label}</p>
                  <p style={{ margin: 0, fontSize: '13px', wordBreak: 'break-all' }}>{value}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'logs' && (resource.runtime_id ?? resource.pod_name) ? (
          <div style={{ padding: '24px', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <h2 style={{ margin: '0 0 16px', fontSize: '15px', fontWeight: 600 }}>Pod Logs</h2>
            <div style={{ flex: 1, minHeight: 0 }}>
              <JobLogViewer resourceId={resource.id} />
            </div>
          </div>
        ) : tab === 'logs' ? (
          <div style={{ padding: '24px', color: 'var(--color-text-muted)', fontSize: '13px' }}>
            No pod running. Start this resource to view logs.
          </div>
        ) : null}
      </div>
    </div>
  );
}
