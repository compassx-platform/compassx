import { useCallback, useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import type { Data } from 'plotly.js';
import { Activity, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react';
import api from '@/lib/api';
import './monitoring.css';
import './monitoring-state.css';

type ResourceKind = 'platform' | 'service' | 'node';
type Resource = {
  id: string; name: string; status: string; health: string; runtime: string; uptime: string;
  cpu_percent: number; memory_percent: number; memory_mb: number;
  network_in_kbps: number; network_out_kbps: number;
};
type Overview = {
  total_nodes: number; total_services: number; cpu_utilization: number;
  memory_utilization: number; network_throughput_kbps: number;
  runtime: string; prometheus_connected: boolean; collected_at: string;
};
type Series = { unit: string; points: { timestamp: string; value: number }[] };
type GroupedSeries = {
  unit: string;
  series: { resource_id: string; name: string; status: string; points: { timestamp: string; value: number }[] }[];
};

const stackColors = ['#087ca1', '#028c74', '#e38b16', '#7057b8', '#c94f7c', '#5278b8', '#76933c', '#b85c38'];

const charts = [
  { key: 'cpu', title: 'CPU utilization', color: '#087ca1' },
  { key: 'memory', title: 'Memory usage', color: '#028c74' },
  { key: 'network_in', title: 'Network receive rate', color: '#e38b16' },
  { key: 'disk_read', title: 'Disk read rate', color: '#7057b8' },
];

const endpointFor = (kind: ResourceKind) => `/monitoring/${kind === 'service' ? 'services' : kind}`;

export default function MonitoringPage() {
  const [overview, setOverview] = useState<Overview>();
  const [kind, setKind] = useState<ResourceKind>('platform');
  const [resources, setResources] = useState<Resource[]>([]);
  const [services, setServices] = useState<Resource[]>([]);
  const [selected, setSelected] = useState('');
  const [series, setSeries] = useState<Record<string, Series>>({});
  const [groupedSeries, setGroupedSeries] = useState<Record<string, GroupedSeries>>({});
  const [stackServices, setStackServices] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [summary, list, serviceList] = await Promise.all([
        api.get<Overview>('/monitoring/overview'),
        api.get<Resource[]>(endpointFor(kind)),
        api.get<Resource[]>('/monitoring/services'),
      ]);
      setOverview(summary.data);
      setResources(list.data);
      setServices(serviceList.data);
      setSelected(current => list.data.some(item => item.id === current) ? current : (list.data[0]?.id ?? ''));
      setError('');
    } catch {
      setError('Unable to read resource metrics from the active profile.');
    } finally {
      setBusy(false);
    }
  }, [kind]);

  const loadSeries = useCallback(async () => {
    if (!selected) {
      setSeries({});
      return;
    }
    const end = Math.floor(Date.now() / 1000);
    if (kind === 'platform' && stackServices) {
      const items = await Promise.all(charts.map(chart =>
        api.get<GroupedSeries>('/monitoring/timeseries/services', {
          params: { metric: chart.key, start: end - 28800, end, resolution: 300 },
        }).then(response => [chart.key, response.data] as const)
      ));
      setGroupedSeries(Object.fromEntries(items));
      return;
    }
    const items = await Promise.all(charts.map(chart =>
      api.get<Series>('/monitoring/timeseries', {
        params: {
          resource_type: kind, resource_id: selected, metric: chart.key,
          start: end - 28800, end, resolution: 300,
        },
      }).then(response => [chart.key, response.data] as const)
    ));
    setSeries(Object.fromEntries(items));
  }, [kind, selected, stackServices]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    void loadSeries().catch(() => setError('Unable to read metric history.'));
  }, [loadSeries, overview?.collected_at]);

  const current = resources.find(item => item.id === selected);
  const serviceRanking = [...services].sort((left, right) => {
    const leftHealthy = ['healthy', 'running'].includes(left.health.toLowerCase());
    const rightHealthy = ['healthy', 'running'].includes(right.health.toLowerCase());
    return Number(leftHealthy) - Number(rightHealthy) || right.cpu_percent - left.cpu_percent;
  });
  const tableResources = kind === 'platform' ? serviceRanking : resources;
  const topCpu = [...services].sort((a, b) => b.cpu_percent - a.cpu_percent)[0];
  const topMemory = [...services].sort((a, b) => b.memory_mb - a.memory_mb)[0];

  return (
    <div className="monitoring-page">
      <header className="monitoring-header">
        <div>
          <p className="eyebrow">Infrastructure</p>
          <h1>Monitoring</h1>
          <p className="monitoring-subtitle">Start with platform health, identify the affected service, then drill into its metrics.</p>
        </div>
        <div className="header-actions">
          <span className="live-dot" />
          {overview?.prometheus_connected ? 'Prometheus metrics' : 'Local history fallback'}
          <button className="outline-button" onClick={() => void load()}>
            <RefreshCw size={14} className={busy ? 'spin' : ''} /> Refresh
          </button>
        </div>
      </header>

      {error && <div className="monitoring-error">{error}</div>}

      <section className="summary-grid">
        {[
          ['Total nodes', overview?.total_nodes ?? '-'],
          ['Total services', overview?.total_services ?? '-'],
          ['CPU utilization', overview ? overview.cpu_utilization + '%' : '-'],
          ['Memory utilization', overview ? overview.memory_utilization + '%' : '-'],
          ['Network throughput', overview ? overview.network_throughput_kbps + ' KB/s' : '-'],
        ].map(([label, value]) => (
          <div className="summary-card" key={label}>
            <Activity size={17} /><div><span>{label}</span><strong>{value}</strong></div>
          </div>
        ))}
      </section>

      <section className="control-bar">
        <div className="segmented">
          <button className={kind === 'platform' ? 'active' : ''} onClick={() => setKind('platform')}>Platform</button>
          <button className={kind === 'service' ? 'active' : ''} onClick={() => setKind('service')}>Services</button>
          <button className={kind === 'node' ? 'active' : ''} onClick={() => setKind('node')}>Nodes</button>
        </div>
        <label>
          Resource
          <select value={selected} onChange={event => setSelected(event.target.value)}>
            {resources.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        {kind === 'platform' && (
          <label className="stack-toggle">
            <input
              type="checkbox"
              checked={stackServices}
              onChange={event => setStackServices(event.target.checked)}
            />
            Stack bars by service
          </label>
        )}
        <span className="refresh-meta">
          Updated {overview ? new Date(overview.collected_at).toLocaleTimeString() : '-'}
        </span>
      </section>

      <div className="dashboard-layout">
        <main className="charts-grid">
          {charts.map(chart => {
            const data = series[chart.key];
            const grouped = groupedSeries[chart.key];
            const isStacked = kind === 'platform' && stackServices;
            const unit = isStacked ? grouped?.unit : data?.unit;
            const plotData: Data[] = isStacked
              ? (grouped?.series ?? []).map((item, index) => ({
                  x: item.points.map(point => point.timestamp),
                  y: item.points.map(point => point.value),
                  type: 'bar',
                  name: item.name,
                  marker: { color: stackColors[index % stackColors.length] },
                  hovertemplate: `%{y:.2f} ${grouped?.unit ?? ''}<extra>${item.name}</extra>`,
                }))
              : [{
                  x: data?.points.map(point => point.timestamp) || [],
                  y: data?.points.map(point => point.value) || [],
                  type: 'bar',
                  name: current?.name,
                  marker: { color: chart.color },
                  hovertemplate: `%{y:.2f} ${data?.unit ?? ''}<extra></extra>`,
                }];
            return (
              <article className="chart-card" key={chart.key}>
                <div className="chart-title">
                  <h2>{chart.title}{unit ? ` (${unit})` : ''}</h2>
                  <span>5-minute average - {isStacked ? 'services stacked' : current?.name || 'Select a resource'}</span>
                </div>
                <Plot
                  data={plotData}
                  layout={{
                    autosize: true, height: 220, margin: { l: 42, r: 12, t: 12, b: 34 },
                    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                    xaxis: { showgrid: true, gridcolor: '#e7edf1' },
                    yaxis: { showgrid: true, gridcolor: '#e7edf1', rangemode: 'tozero' },
                    barmode: isStacked ? 'stack' : 'group',
                    showlegend: isStacked,
                    legend: { orientation: 'h', y: -0.28 },
                    hovermode: 'x unified', dragmode: 'zoom',
                  }}
                  config={{ displaylogo: false, responsive: true }}
                  style={{ width: '100%' }}
                  useResizeHandler
                />
              </article>
            );
          })}
        </main>

        <aside className="details-card">
          <p className="eyebrow">Selected resource</p>
          <h2>{current?.name || 'No resource selected'}</h2>
          {current && (
            <>
              <span className={`status-badge ${current.health.toLowerCase() !== 'healthy' ? 'status-badge--warning' : ''}`}>
                {current.health.toLowerCase() === 'healthy' ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
                {current.health}
              </span>
              <dl>
                {[
                  ['CPU usage', current.cpu_percent + '%'],
                  ['Memory usage', `${current.memory_mb} MB (${current.memory_percent}%)`],
                  ['Runtime', current.runtime],
                  ['Uptime', current.uptime],
                  ...(kind === 'platform' && topCpu ? [['Highest CPU', `${topCpu.name} (${topCpu.cpu_percent}%)`]] : []),
                  ...(kind === 'platform' && topMemory ? [['Highest memory', `${topMemory.name} (${topMemory.memory_mb} MB)`]] : []),
                ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
              </dl>
            </>
          )}
        </aside>
      </div>

      <section className="resource-table-card">
        <div className="table-heading">
          <h2>{kind === 'platform' ? 'Service investigation' : kind === 'service' ? 'Services' : 'Nodes'}</h2>
          <span>{tableResources.length} resources{kind === 'platform' ? ' - unhealthy first, then CPU' : ''}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Status</th><th>CPU</th><th>Memory</th><th>Network</th><th>Uptime</th></tr></thead>
            <tbody>
              {tableResources.map(item => (
                <tr key={item.id} onClick={() => {
                  if (kind === 'platform') {
                    setKind('service');
                    setSelected(item.id);
                  } else {
                    setSelected(item.id);
                  }
                }}>
                  <td><strong>{item.name}</strong><small>{item.runtime}</small></td>
                  <td><span className={`table-status ${!['healthy', 'running'].includes(item.health.toLowerCase()) ? 'table-status--warning' : ''}`}><i />{item.status}</span></td>
                  <td>{item.cpu_percent}%</td>
                  <td>{item.memory_mb} MB ({item.memory_percent}%)</td>
                  <td>{item.network_in_kbps} / {item.network_out_kbps} KB/s</td>
                  <td>{item.uptime}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!tableResources.length && !busy && <div className="monitoring-empty">No {kind} resources were discovered for this profile.</div>}
        </div>
      </section>
    </div>
  );
}
