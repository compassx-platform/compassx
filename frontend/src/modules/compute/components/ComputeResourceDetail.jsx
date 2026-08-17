import { useState } from 'react';
import JobLogViewer from './JobLogViewer';

/**
 * Detail view for a compute resource with Configuration and Logs tabs.
 * @param {{ resource: any, onClose: () => void }} props
 */
export default function ComputeResourceDetail({ resource, onClose }) {
  const [tab, setTab] = useState('configuration');

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
                <section>
                  <h2 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>Description</h2>
                  <div style={{ padding: '12px 16px', background: 'var(--color-surface-secondary)', borderRadius: '6px', fontSize: '13px', lineHeight: '1.5' }}>
                    {resource.description}
                  </div>
                </section>
              )}
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
              <JobLogViewer resourceId={resource.id} userId={resource.user_id} />
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
