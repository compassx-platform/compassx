import { Play, PlugZap, RefreshCw, RotateCcw, Square } from 'lucide-react';
import { AppTable } from '@/components/common/AppTable';

const phaseColorMap = {
  Running: '#10b981',
  Starting: '#f59e0b',
  Stopped: '#6b7280',
  Error: '#ef4444',
};

/**
 * Table showing shared compute dependencies.
 * @param {{ services: any[], loadingKey?: string | null, onAction: (serviceId: string, action: string) => void, portForwardStatus?: any, portForwardLoading?: string | null, onCheckPortForwards?: () => void, onRecoverPortForwards?: () => void }} props
 */
export default function ComputeServicesPanel({
  services,
  loadingKey,
  onAction,
  portForwardStatus,
  portForwardLoading,
  onCheckPortForwards,
  onRecoverPortForwards,
}) {
  const forwards = portForwardStatus?.forwards ?? [];
  const healthyCount = forwards.filter((item) => item.healthy).length;
  const summary = forwards.length
    ? `${healthyCount}/${forwards.length} healthy`
    : 'Not checked';
  const summaryState = !forwards.length
    ? 'unknown'
    : portForwardStatus?.healthy
      ? 'healthy'
      : healthyCount > 0
        ? 'partial'
        : 'down';

  const columns = [
    {
      key: 'status',
      header: 'Status',
      render: (service) => {
        const color = phaseColorMap[service.phase] || '#6b7280';
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color, fontWeight: 600 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
            {service.phase || '-'}
          </span>
        );
      },
    },
    {
      key: 'name',
      header: 'Name',
      render: (service) => <span style={{ fontWeight: 500 }}>{service.label || service.id}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      className: 'app-table-muted',
      render: (service) => service.details?.namespace || '-',
    },
    {
      key: 'service',
      header: 'Service',
      render: (service) => service.details?.service_name || '-',
    },
    {
      key: 'ui',
      header: 'UI',
      render: (service) => service.details?.ui_url ? (
        <a href={service.details.ui_url} target="_blank" rel="noreferrer">Open UI</a>
      ) : '-',
    },
    {
      key: 'message',
      header: 'Message',
      className: 'app-table-muted',
      render: (service) => service.message || 'No status message',
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (service) => {
        const keyPrefix = `${service.id}:`;
        const isBusy = loadingKey?.startsWith(keyPrefix);

        return (
          <>
            <button
              className="ghost-icon-btn"
              title="Start"
              aria-label={`Start ${service.label || service.id}`}
              onClick={() => onAction(service.id, 'start')}
              disabled={isBusy || service.phase === 'Running' || service.phase === 'Starting'}
            >
              {loadingKey === `${service.id}:start` ? '...' : <Play size={13} fill="#5A5A5A" strokeWidth={0} />}
            </button>
            <button
              className="ghost-icon-btn"
              title="Restart"
              aria-label={`Restart ${service.label || service.id}`}
              onClick={() => onAction(service.id, 'restart')}
              disabled={isBusy || service.phase === 'Stopped'}
            >
              {loadingKey === `${service.id}:restart` ? '...' : <RotateCcw size={13} color="#5A5A5A" />}
            </button>
            <button
              className="ghost-icon-btn"
              title="Stop"
              aria-label={`Stop ${service.label || service.id}`}
              onClick={() => onAction(service.id, 'stop')}
              disabled={isBusy || service.phase === 'Stopped'}
            >
              {loadingKey === `${service.id}:stop` ? '...' : <Square size={13} fill="#5A5A5A" strokeWidth={0} />}
            </button>
          </>
        );
      },
    },
  ];

  return (
    <>
      <div className="port-forward-panel">
        <div className="port-forward-summary">
          <span className={`port-forward-dot port-forward-dot-${summaryState}`} />
          <div>
            <div className="port-forward-title">Local port-forwards</div>
            <div className="port-forward-subtitle">{summary}</div>
          </div>
        </div>
        <div className="port-forward-chips">
          {forwards.map((item) => (
            <span key={item.id} className={`port-forward-chip port-forward-chip-${item.state}`}>
              {item.label}
              {item.local_port ? ` :${item.local_port}` : ''}
              <strong>{item.state}</strong>
            </span>
          ))}
        </div>
        <div className="port-forward-actions">
          <button
            className="ghost-icon-btn"
            title="Check port-forward status"
            aria-label="Check port-forward status"
            onClick={onCheckPortForwards}
            disabled={!!portForwardLoading}
          >
            {portForwardLoading === 'check' ? '...' : <RefreshCw size={14} color="#5A5A5A" />}
          </button>
          <button
            className="compute-secondary-btn"
            onClick={onRecoverPortForwards}
            disabled={!!portForwardLoading}
          >
            {portForwardLoading === 'recover' ? 'Recovering' : (
              <>
                <PlugZap size={14} />
                Recover
              </>
            )}
          </button>
        </div>
      </div>
      <AppTable
        columns={columns}
        rows={services}
        rowKey={(service) => service.id}
        emptyText="No compute services found."
      />
    </>
  );
}
