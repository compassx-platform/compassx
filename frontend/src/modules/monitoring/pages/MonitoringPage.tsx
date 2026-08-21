import { useCallback, useEffect, useMemo, useState } from 'react';
import Plot from 'react-plotly.js';
import type { Data } from 'plotly.js';
import {
  Activity,
  AlertTriangle,
  ArrowDownUp,
  BarChart3,
  CheckCircle2,
  Cpu,
  Database,
  HardDrive,
  Layers,
  RefreshCw,
  Search,
  Server,
  X,
  XCircle,
} from 'lucide-react';
import { PageTabs } from '@/components/common/PageTabs';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import api from '@/lib/api';
import './monitoring.css';

type Resource = {
  id: string;
  name: string;
  kind: 'platform' | 'service' | 'node';
  status: string;
  runtime: string;
  uptime: string;
  cpu_percent: number;
  memory_percent: number;
  memory_mb: number;
  memory_limit_mb?: number;
  disk_percent: number;
  network_in_kbps: number;
  network_out_kbps: number;
  restarts: number;
  health: string;
  container_name?: string;
  image?: string;
  ports?: string[];
};

type Overview = {
  platform_status: string;
  running_services: number;
  total_services: number;
  cpu_utilization: number;
  memory_utilization: number;
  network_throughput_kbps: number;
  runtime: string;
  prometheus_connected: boolean;
  collected_at: string;
};

type SeriesPoint = {
  timestamp: string;
  value: number;
};

type SingleSeries = {
  metric: string;
  unit: string;
  points: SeriesPoint[];
};

type GroupedSeries = {
  metric: string;
  unit: string;
  series: { resource_id: string; name: string; status: string; points: SeriesPoint[] }[];
};

type ActiveTab = 'charts' | 'services';

const MONITORING_PAGE_TABS = [
  { value: 'charts', label: 'Metrics' },
  { value: 'services', label: 'Services' },
] as const;

const CHART_CONFIGS = [
  { key: 'cpu', title: 'CPU Utilization', unit: '%', color: '#077A9D' },
  { key: 'memory', title: 'Memory Usage', unit: 'MB', color: '#FFAB00' },
  { key: 'network_in', title: 'Network Receive Rate', unit: 'KB/s', color: '#00A972' },
  { key: 'disk_read', title: 'Disk Read Rate', unit: 'KB/s', color: '#FF3621' },
];

const TIME_RANGES = [
  { label: '1h', seconds: 3600, resolution: 60 },
  { label: '6h', seconds: 21600, resolution: 300 },
  { label: '24h', seconds: 86400, resolution: 900 },
  { label: '7d', seconds: 604800, resolution: 3600 },
];

const PALETTE = [
  '#077A9D',
  '#FFAB00',
  '#00A972',
  '#FF3621',
  '#8BCAE7',
  '#AB4057',
  '#99DDB4',
  '#FCA4A1',
  '#919191',
  '#BF7080',
];

// Format ISO timestamps for Plotly charts (Local Time vs UTC)
const formatPlotlyTimestamp = (isoStr: string, isLocal: boolean): string => {
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return isoStr;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (!isLocal) {
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  }
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

export default function MonitoringPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('charts');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [services, setServices] = useState<Resource[]>([]);
  const [nodes, setNodes] = useState<Resource[]>([]);
  const [selectedService, setSelectedService] = useState<Resource | null>(null);

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Chart States
  const [timeRange, setTimeRange] = useState(TIME_RANGES[0]);
  const [chartResource, setChartResource] = useState('ALL');
  const [useLocalTime, setUseLocalTime] = useState(true);
  const [singleSeries, setSingleSeries] = useState<Record<string, SingleSeries>>({});
  const [groupedSeries, setGroupedSeries] = useState<Record<string, GroupedSeries>>({});

  const localTz = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local';
    } catch {
      return 'Local';
    }
  }, []);

  // Auto-refresh interval (default: 30s)
  const [refreshInterval, setRefreshInterval] = useState(30000);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [errorMessage, setErrorMessage] = useState('');

  // ── Fetch Live Overview & Services ──────────────────────────────────────────
  const fetchLiveData = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    try {
      const [overviewRes, servicesRes, nodesRes] = await Promise.all([
        api.get<Overview>('/monitoring/overview'),
        api.get<Resource[]>('/monitoring/services'),
        api.get<Resource[]>('/monitoring/nodes').catch(() => ({ data: [] })),
      ]);

      setOverview(overviewRes.data);
      setServices(servicesRes.data);
      setNodes(nodesRes.data);
      setLastRefreshedAt(new Date());
      setErrorMessage('');

      // Keep selectedService in sync without circular dependency
      setSelectedService((prev) => {
        if (!prev) return null;
        return servicesRes.data.find((s) => s.id === prev.id) || prev;
      });
    } catch {
      setErrorMessage('Unable to connect to monitoring service.');
    } finally {
      if (isManual) setIsRefreshing(false);
    }
  }, []);

  // ── Fetch Timeseries Metric History from Prometheus ────────────────────────
  const fetchChartHistory = useCallback(async () => {
    const end = Math.floor(Date.now() / 1000);
    const start = end - timeRange.seconds;
    const resolution = timeRange.resolution;

    try {
      if (chartResource === 'ALL') {
        const results = await Promise.all(
          CHART_CONFIGS.map((c) =>
            api
              .get<GroupedSeries>('/monitoring/timeseries/services', {
                params: { metric: c.key, start, end, resolution },
              })
              .then((res) => [c.key, res.data] as const)
              .catch(() => [c.key, { unit: c.unit, series: [] }] as const)
          )
        );
        setGroupedSeries(Object.fromEntries(results));
      } else {
        const results = await Promise.all(
          CHART_CONFIGS.map((c) =>
            api
              .get<SingleSeries>('/monitoring/timeseries', {
                params: {
                  resource_type: 'service',
                  resource_id: chartResource,
                  metric: c.key,
                  start,
                  end,
                  resolution,
                },
              })
              .then((res) => [c.key, res.data] as const)
              .catch(() => [c.key, { unit: c.unit, points: [] }] as const)
          )
        );
        setSingleSeries(Object.fromEntries(results));
      }
    } catch {
      console.warn('Failed to load metric history from Prometheus');
    }
  }, [chartResource, timeRange]);

  // Polling effect
  useEffect(() => {
    void fetchLiveData();
    if (refreshInterval <= 0) return;
    const timer = setInterval(() => {
      void fetchLiveData();
    }, refreshInterval);
    return () => clearInterval(timer);
  }, [fetchLiveData, refreshInterval]);

  // Fetch charts when entering charts tab or changing parameters
  useEffect(() => {
    if (activeTab === 'charts') {
      void fetchChartHistory();
    }
  }, [activeTab, fetchChartHistory]);

  // ── Filtered Services List ──────────────────────────────────────────────────
  const filteredServices = useMemo(() => {
    return services.filter((s) => {
      const matchesSearch =
        searchQuery === '' ||
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (s.container_name && s.container_name.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'RUNNING' && s.status.toLowerCase() === 'running') ||
        (statusFilter === 'STOPPED' && s.status.toLowerCase() !== 'running') ||
        (statusFilter === 'HEALTHY' && s.health.toLowerCase() === 'healthy') ||
        (statusFilter === 'DEGRADED' && s.health.toLowerCase() !== 'healthy');

      return matchesSearch && matchesStatus;
    });
  }, [services, searchQuery, statusFilter]);

  // Helper for health badge style
  const getHealthBadgeClass = (health: string, status: string) => {
    const h = health.toLowerCase();
    const s = status.toLowerCase();
    if (h === 'healthy' || s === 'running') return 'healthy';
    if (h === 'stopped' || s === 'exited') return 'stopped';
    return 'warning';
  };

  // Standard AppTable columns for Services
  const serviceColumns = useMemo<AppTableColumn<Resource>[]>(
    () => [
      {
        key: 'name',
        header: 'Service / Container',
        width: '24%',
        render: (service) => (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Server size={14} color="var(--color-primary)" style={{ flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{service.name}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 1 }}>
                {service.container_name || service.id}
              </div>
            </div>
          </div>
        ),
      },
      {
        key: 'runtime',
        header: 'Runtime',
        width: '10%',
        render: (service) => (
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 600,
              color: '#475569',
              background: '#f1f5f9',
              padding: '2px 6px',
              borderRadius: '4px',
            }}
          >
            {service.runtime}
          </span>
        ),
      },
      {
        key: 'status',
        header: 'Health Status',
        width: '13%',
        render: (service) => {
          const badgeClass = getHealthBadgeClass(service.health, service.status);
          return (
            <span className={`service-health-badge ${badgeClass}`}>
              {badgeClass === 'healthy' ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
              {service.health}
            </span>
          );
        },
      },
      {
        key: 'cpu',
        header: 'CPU Usage',
        width: '14%',
        render: (service) => (
          <div className="usage-bar-cell">
            <div className="usage-text">
              <strong>{service.cpu_percent}%</strong>
            </div>
            <div className="usage-bar-bg">
              <div
                className={`usage-bar-fill ${
                  service.cpu_percent > 80 ? 'high' : service.cpu_percent > 40 ? 'medium' : ''
                }`}
                style={{ width: `${Math.min(100, service.cpu_percent)}%` }}
              />
            </div>
          </div>
        ),
      },
      {
        key: 'memory',
        header: 'Memory Usage',
        width: '15%',
        render: (service) => (
          <div className="usage-bar-cell">
            <div className="usage-text">
              <span>{service.memory_mb} MB</span>
              <span style={{ color: '#94a3b8' }}>{service.memory_percent}%</span>
            </div>
            <div className="usage-bar-bg">
              <div
                className={`usage-bar-fill ${
                  service.memory_percent > 80 ? 'high' : service.memory_percent > 50 ? 'medium' : ''
                }`}
                style={{ width: `${Math.min(100, service.memory_percent)}%` }}
              />
            </div>
          </div>
        ),
      },
      {
        key: 'network',
        header: 'Network (RX / TX)',
        width: '12%',
        render: (service) => (
          <div style={{ fontSize: '11px', color: '#475569' }}>
            <div>↓ {service.network_in_kbps} KB/s</div>
            <div style={{ color: '#94a3b8' }}>↑ {service.network_out_kbps} KB/s</div>
          </div>
        ),
      },
      {
        key: 'restarts',
        header: 'Restarts',
        width: '6%',
        render: (service) => (
          <span
            style={{
              fontWeight: (service.restarts ?? (service as any).restart_count ?? 0) > 0 ? 700 : 400,
              color: (service.restarts ?? (service as any).restart_count ?? 0) > 0 ? '#dc2626' : 'inherit',
            }}
          >
            {service.restarts ?? (service as any).restart_count ?? 0}
          </span>
        ),
      },
      {
        key: 'uptime',
        header: 'Uptime',
        width: '6%',
        render: (service) => (
          <span style={{ color: '#64748b', fontSize: '12px' }}>{service.uptime}</span>
        ),
      },
    ],
    []
  );

  return (
    <div className="monitoring-root">
      {/* ── Top Header ────────────────────────────────────────────────────────── */}
      <header className="monitoring-top-header">
        <div className="monitoring-title-area">
          <div className="monitoring-title-row">
            <h1>Infrastructure Monitoring</h1>
            <span className="monitoring-runtime-tag">{overview?.runtime || 'local-dev'}</span>
          </div>
        </div>

        <div className="monitoring-header-controls">
          {/* Auto Refresh Dropdown */}
          <div className="refresh-control-group">
            <select
              className="auto-refresh-select"
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
            >
              <option value={5000}>Auto-refresh: 5s</option>
              <option value={10000}>Auto-refresh: 10s</option>
              <option value={30000}>Auto-refresh: 30s</option>
              <option value={0}>Auto-refresh: Off</option>
            </select>

            <button
              className="monitoring-btn-refresh"
              onClick={() => {
                void fetchLiveData(true);
                if (activeTab === 'charts') void fetchChartHistory();
              }}
              disabled={isRefreshing}
            >
              <RefreshCw size={13} className={isRefreshing ? 'spin-icon' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </header>

      {/* ── Standard Page Tabs (Metrics & Services) ─────────────────────────── */}
      <PageTabs
        tabs={MONITORING_PAGE_TABS}
        value={activeTab}
        onChange={(value) => setActiveTab(value as ActiveTab)}
      />

      {/* ── Error Banner if any ───────────────────────────────────────────────── */}
      {errorMessage && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: '6px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            fontSize: '13px',
          }}
        >
          {errorMessage}
        </div>
      )}

      {/* ── TAB 1: SERVICES ───────────────────────────────────────────────────── */}
      {activeTab === 'services' && (
        <section className="monitoring-content-section">
          {/* Toolbar */}
          <div className="monitoring-toolbar">
            <div className="monitoring-search-box">
              <Search size={14} />
              <input
                type="text"
                placeholder="Search services or containers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="monitoring-filters-right">
              <select
                className="monitoring-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="ALL">All Statuses</option>
                <option value="RUNNING">Running Only</option>
                <option value="STOPPED">Stopped / Exited</option>
                <option value="HEALTHY">Healthy</option>
                <option value="DEGRADED">Degraded</option>
              </select>
            </div>
          </div>

          {/* Standard AppTable */}
          <AppTable
            columns={serviceColumns}
            rows={filteredServices}
            rowKey={(service) => service.id}
            onRowClick={(service) => setSelectedService(service)}
            emptyText="No services match your search or filter criteria."
          />
        </section>
      )}

      {/* ── TAB 2: TIME-SERIES CHARTS ─────────────────────────────────────────── */}
      {activeTab === 'charts' && (
        <section className="monitoring-content-section">
          {/* ── Realtime Metrics Summary Strip (Stacked Title & Number) ── */}
          <div className="metrics-summary-strip">
            <div className="summary-strip-item">
              <span className="strip-label">Platform Status</span>
              <div className="strip-value-row">
                <span
                  className={`status-indicator-dot ${
                    overview?.running_services === overview?.total_services
                      ? 'healthy'
                      : 'degraded'
                  }`}
                />
                <span className="strip-value-main">
                  {overview
                    ? overview.running_services === overview.total_services
                      ? 'Healthy'
                      : 'Degraded'
                    : '--'}
                </span>
                <span className="strip-sub">
                  {overview
                    ? `(${overview.running_services}/${overview.total_services})`
                    : ''}
                </span>
              </div>
            </div>

            <div className="summary-strip-divider" />

            <div className="summary-strip-item">
              <span className="strip-label">Avg CPU</span>
              <div className="strip-value-row">
                <Cpu size={15} style={{ color: '#2563eb', alignSelf: 'center' }} />
                <span className="strip-value-main">
                  {overview ? overview.cpu_utilization : 0}
                </span>
                <span className="strip-unit">%</span>
              </div>
            </div>

            <div className="summary-strip-divider" />

            <div className="summary-strip-item">
              <span className="strip-label">Memory Utilization</span>
              <div className="strip-value-row">
                <Database size={15} style={{ color: '#059669', alignSelf: 'center' }} />
                <span className="strip-value-main">
                  {overview ? overview.memory_utilization : 0}
                </span>
                <span className="strip-unit">%</span>
                <span className="strip-sub">
                  ({services.reduce((acc, s) => acc + s.memory_mb, 0).toFixed(0)} MB)
                </span>
              </div>
            </div>

            <div className="summary-strip-divider" />

            <div className="summary-strip-item">
              <span className="strip-label">Network Throughput</span>
              <div className="strip-value-row">
                <ArrowDownUp size={15} style={{ color: '#d97706', alignSelf: 'center' }} />
                <span className="strip-value-main">
                  {overview ? overview.network_throughput_kbps : 0}
                </span>
                <span className="strip-unit">KB/s</span>
              </div>
            </div>
          </div>

          <div className="metrics-horizontal-divider" />

          {/* Charts Toolbar */}
          <div className="charts-top-controls">
            <select
              className="monitoring-select"
              value={chartResource}
              onChange={(e) => setChartResource(e.target.value)}
            >
              <option value="ALL">All Services (Stacked Comparison)</option>
              {services.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <div className="time-range-group">
                {TIME_RANGES.map((r) => (
                  <button
                    key={r.label}
                    className={`time-range-btn ${timeRange.label === r.label ? 'active' : ''}`}
                    onClick={() => setTimeRange(r)}
                  >
                    {r.label}
                  </button>
                ))}
              </div>

              <div className="time-range-group">
                <button
                  className={`time-range-btn ${useLocalTime ? 'active' : ''}`}
                  onClick={() => setUseLocalTime(true)}
                  title={`Local browser timezone (${localTz})`}
                >
                  Local ({localTz.split('/').pop()?.replace('_', ' ') || 'Local'})
                </button>
                <button
                  className={`time-range-btn ${!useLocalTime ? 'active' : ''}`}
                  onClick={() => setUseLocalTime(false)}
                  title="Coordinated Universal Time (UTC)"
                >
                  UTC
                </button>
              </div>
            </div>
          </div>

          {/* 2x2 Grid of Plotly Charts */}
          <div className="charts-grid-2x2">
            {CHART_CONFIGS.map((config) => {
              const isStacked = chartResource === 'ALL';
              const groupData = groupedSeries[config.key];
              const singleData = singleSeries[config.key];

              const cleanServiceName = (rawName: string) => {
                return rawName
                  .replace(/^docker:/, '')
                  .replace(/^compassx-/, '')
                  .replace(/-1$/, '')
                  .replace('enterprise-gateway', 'gateway')
                  .replace('airflow-webserver', 'airflow-web')
                  .replace('airflow-scheduler', 'airflow-sched')
                  .replace('spark-master', 'spark-m')
                  .replace('spark-worker', 'spark-w');
              };

              const plotData: Data[] = isStacked
                ? (groupData?.series || []).map((s, idx) => ({
                    x: s.points.map((p) => formatPlotlyTimestamp(p.timestamp, useLocalTime)),
                    y: s.points.map((p) => p.value),
                    type: 'bar',
                    name: cleanServiceName(s.name),
                    marker: { color: PALETTE[idx % PALETTE.length] },
                    hovertemplate: `${s.name.replace(/^docker:/, '').replace(/^compassx-/, '')}: %{y:.2f} ${config.unit}<extra></extra>`,
                  }))
                : [
                    {
                      x: (singleData?.points || []).map((p) =>
                        formatPlotlyTimestamp(p.timestamp, useLocalTime)
                      ),
                      y: (singleData?.points || []).map((p) => p.value),
                      type: 'bar',
                      name: services.find((s) => s.id === chartResource)?.name || 'Service',
                      marker: { color: config.color },
                      hovertemplate: `${services.find((s) => s.id === chartResource)?.name || 'Service'}: %{y:.2f} ${config.unit}<extra></extra>`,
                    },
                  ];

              // Memory limit calculation for memory chart
              let memLimit = 0;
              if (config.key === 'memory') {
                if (chartResource !== 'ALL') {
                  const selectedServiceObj = services.find((s) => s.id === chartResource);
                  if (selectedServiceObj) {
                    memLimit =
                      selectedServiceObj.memory_limit_mb ||
                      (selectedServiceObj.memory_percent > 0
                        ? (selectedServiceObj.memory_mb / selectedServiceObj.memory_percent) * 100
                        : 0);
                  }
                } else if (services.length > 0) {
                  const validLimits = services
                    .map(
                      (s) =>
                        s.memory_limit_mb ||
                        (s.memory_percent > 0 ? (s.memory_mb / s.memory_percent) * 100 : 0)
                    )
                    .filter((l) => l > 0);
                  if (validLimits.length > 0) {
                    memLimit = Math.max(...validLimits);
                  }
                }
              }

              // Compute maximum Y across points to properly scale Y-axis with limit
              let maxDataY = 0;
              if (isStacked) {
                const seriesList = groupData?.series || [];
                if (seriesList.length > 0 && seriesList[0].points.length > 0) {
                  for (let i = 0; i < seriesList[0].points.length; i++) {
                    let sum = 0;
                    for (const s of seriesList) {
                      sum += s.points[i]?.value || 0;
                    }
                    if (sum > maxDataY) maxDataY = sum;
                  }
                }
              } else {
                const pts = singleData?.points || [];
                maxDataY = pts.reduce((max, p) => Math.max(max, p.value), 0);
              }

              const yRange =
                config.key === 'memory' && memLimit > 0
                  ? [0, Math.max(maxDataY * 1.15, memLimit * 1.08)]
                  : undefined;

              return (
                <div key={config.key} className="monitoring-chart-card">
                  <div className="chart-card-header">
                    <h3 className="chart-card-title">
                      {config.title} ({config.unit})
                      {config.key === 'memory' && memLimit > 0 && (
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 500,
                            color: '#ef4444',
                            marginLeft: '8px',
                          }}
                        >
                          • Limit:{' '}
                          {memLimit >= 1024
                            ? `${(memLimit / 1024).toFixed(1)} GB`
                            : `${Math.round(memLimit)} MB`}
                        </span>
                      )}
                    </h3>
                  </div>

                  <Plot
                    data={plotData}
                    layout={{
                      autosize: true,
                      height: 360,
                      margin: { l: 28, r: 0, t: 10, b: 64 },
                      paper_bgcolor: 'transparent',
                      plot_bgcolor: 'transparent',
                      bargap: 0.25,
                      barmode: isStacked ? 'stack' : 'group',
                      showlegend: isStacked,
                      shapes:
                        memLimit > 0
                          ? [
                              {
                                type: 'line',
                                xref: 'paper',
                                x0: 0,
                                x1: 1,
                                yref: 'y',
                                y0: memLimit,
                                y1: memLimit,
                                line: {
                                  color: '#ef4444',
                                  width: 1.5,
                                  dash: 'dash',
                                },
                              },
                            ]
                          : undefined,
                      annotations:
                        memLimit > 0
                          ? [
                              {
                                xref: 'paper',
                                x: 0.98,
                                yref: 'y',
                                y: memLimit,
                                xanchor: 'right',
                                yanchor: 'bottom',
                                text: `Limit: ${
                                  memLimit >= 1024
                                    ? `${(memLimit / 1024).toFixed(1)} GB`
                                    : `${Math.round(memLimit)} MB`
                                }`,
                                showarrow: false,
                                font: { size: 10, color: '#dc2626' },
                                bgcolor: 'rgba(254, 242, 242, 0.9)',
                                bordercolor: '#fca5a5',
                                borderwidth: 1,
                                borderpad: 3,
                              },
                            ]
                          : undefined,
                      legend: {
                        orientation: 'h',
                        x: -0.06,
                        xanchor: 'left',
                        y: -0.28,
                        yanchor: 'top',
                        font: { size: 9.5, color: '#334155' },
                        itemgap: 4,
                      },
                      xaxis: {
                        showgrid: false,
                        showline: true,
                        linecolor: '#64748b',
                        linewidth: 1.5,
                        tickfont: { size: 10, color: '#475569' },
                        ticks: '',
                        nticks: 6,
                        tickformat:
                          timeRange.value.includes('d') || timeRange.value.includes('w')
                            ? '%m/%d %H:%M'
                            : '%H:%M',
                      },
                      yaxis: {
                        showgrid: true,
                        gridcolor: '#e2e8f0',
                        gridwidth: 1,
                        showline: false,
                        zeroline: true,
                        zerolinecolor: '#64748b',
                        zerolinewidth: 1.5,
                        rangemode: yRange ? undefined : 'tozero',
                        range: yRange,
                        tickfont: { size: 10, color: '#64748b' },
                      },
                      hovermode: 'x unified',
                      hoverlabel: {
                        bgcolor: '#1e293b',
                        bordercolor: '#334155',
                        font: { color: '#ffffff', size: 11 },
                      },
                    }}
                    config={{ displaylogo: false, responsive: true }}
                    style={{ width: '100%' }}
                    useResizeHandler
                  />
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Slide-Over Service Inspection Drawer ──────────────────────────────── */}
      {selectedService && (
        <aside className="service-drawer-overlay">
          <div className="drawer-header">
            <div>
              <h3>{selectedService.name}</h3>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                {selectedService.container_name || selectedService.id}
              </span>
            </div>
            <button className="drawer-close-btn" onClick={() => setSelectedService(null)}>
              <X size={18} />
            </button>
          </div>

          <div className="drawer-body">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 14px',
                background: '#f8fafc',
                borderRadius: '8px',
              }}
            >
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#475569' }}>
                Operational Health
              </span>
              <span
                className={`service-health-badge ${getHealthBadgeClass(
                  selectedService.health,
                  selectedService.status
                )}`}
              >
                {selectedService.health}
              </span>
            </div>

            <div className="drawer-info-grid">
              <div className="drawer-info-item">
                <span>CPU Usage</span>
                <strong>{selectedService.cpu_percent}%</strong>
              </div>
              <div className="drawer-info-item">
                <span>Memory Allocation</span>
                <strong>{selectedService.memory_mb} MB ({selectedService.memory_percent}%)</strong>
              </div>
              <div className="drawer-info-item">
                <span>Network In</span>
                <strong>{selectedService.network_in_kbps} KB/s</strong>
              </div>
              <div className="drawer-info-item">
                <span>Network Out</span>
                <strong>{selectedService.network_out_kbps} KB/s</strong>
              </div>
              <div className="drawer-info-item">
                <span>Restart Count</span>
                <strong>{selectedService.restarts}</strong>
              </div>
              <div className="drawer-info-item">
                <span>Uptime</span>
                <strong>{selectedService.uptime}</strong>
              </div>
              <div className="drawer-info-item">
                <span>Runtime Type</span>
                <strong>{selectedService.runtime}</strong>
              </div>
              <div className="drawer-info-item">
                <span>Status</span>
                <strong>{selectedService.status}</strong>
              </div>
            </div>

            {selectedService.image && (
              <div className="drawer-info-item" style={{ wordBreak: 'break-all' }}>
                <span>Container Image</span>
                <strong style={{ fontSize: '12px', fontFamily: 'var(--cx-font-mono)' }}>
                  {selectedService.image}
                </strong>
              </div>
            )}

            <button
              style={{
                marginTop: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                height: '36px',
                borderRadius: '6px',
                border: 'none',
                background: '#2563eb',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
              onClick={() => {
                setChartResource(selectedService.id);
                setActiveTab('charts');
                setSelectedService(null);
              }}
            >
              <BarChart3 size={15} />
              <span>View Time-series History</span>
            </button>
          </div>
        </aside>
      )}
    </div>
  );
}
