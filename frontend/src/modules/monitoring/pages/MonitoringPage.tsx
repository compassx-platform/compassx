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
  total_nodes?: number;
  total_cores?: number;
  platform_status?: string;
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
  const [memLimitGrouped, setMemLimitGrouped] = useState<GroupedSeries | null>(null);
  const [memLimitSingle, setMemLimitSingle] = useState<SingleSeries | null>(null);
  const [nodeTimeseries, setNodeTimeseries] = useState<GroupedSeries | null>(null);

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
        const [results, memLimitRes, nodeRes] = await Promise.all([
          Promise.all(
            CHART_CONFIGS.map((c) =>
              api
                .get<GroupedSeries>('/monitoring/timeseries/services', {
                  params: { metric: c.key, start, end, resolution },
                })
                .then((res) => [c.key, res.data] as const)
                .catch(() => [c.key, { unit: c.unit, series: [] }] as const)
            )
          ),
          api
            .get<GroupedSeries>('/monitoring/timeseries/services', {
              params: { metric: 'memory_limit', start, end, resolution },
            })
            .then((res) => res.data)
            .catch(() => null),
          api
            .get<GroupedSeries>('/monitoring/timeseries/nodes', {
              params: { metric: 'cpu', start, end, resolution },
            })
            .then((res) => res.data)
            .catch(() => null),
        ]);
        setGroupedSeries(Object.fromEntries(results));
        setMemLimitGrouped(memLimitRes);
        setNodeTimeseries(nodeRes);
      } else {
        setNodeTimeseries(null);
        const [results, memLimitRes] = await Promise.all([
          Promise.all(
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
          ),
          api
            .get<SingleSeries>('/monitoring/timeseries', {
              params: {
                resource_type: 'service',
                resource_id: chartResource,
                metric: 'memory_limit',
                start,
                end,
                resolution,
              },
            })
            .then((res) => res.data)
            .catch(() => null),
        ]);
        setSingleSeries(Object.fromEntries(results));
        setMemLimitSingle(memLimitRes);
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
              <span className="strip-label">User Nodes</span>
              <div className="strip-value-row">
                <Server size={15} style={{ color: '#8b5cf6', alignSelf: 'center' }} />
                <span className="strip-value-main">
                  {overview ? (overview.total_nodes || 1) : '--'}
                </span>
                <span className="strip-sub">
                  ({overview ? `${overview.total_nodes || 1} Active, ${overview.total_cores || 1} Cores` : ''})
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
                <span className="strip-sub">
                  ({overview?.total_cores || 1} Cores)
                </span>
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
                  ({services.reduce((acc, s) => acc + s.memory_mb, 0).toFixed(0)} MB / {
                    (() => {
                      const userNodes = nodes.filter(
                        (n) =>
                          !n.runtime?.toLowerCase().includes('system') &&
                          !n.name?.toLowerCase().includes('system')
                      );
                      const targetNodes = userNodes.length > 0 ? userNodes : nodes;
                      const totalLimit = targetNodes.reduce(
                        (acc, n) => acc + (n.memory_limit_mb ?? 0),
                        0
                      );
                      if (totalLimit > 0) {
                        return `${(totalLimit / 1024).toFixed(1)} GB`;
                      }
                      const totalServiceLimit = services.reduce(
                        (acc, s) => acc + (s.memory_limit_mb || 0),
                        0
                      );
                      if (totalServiceLimit > 0) {
                        return `${(totalServiceLimit / 1024).toFixed(1)} GB`;
                      }
                      const totalUsed = services.reduce((acc, s) => acc + s.memory_mb, 0);
                      return `${(totalUsed / 1024).toFixed(1)} GB`;
                    })()
                  })
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

              // Build pod limits map for rich tooltip annotations
              const podLimitMap = new Map<string, number>();
              services.forEach((svc) => {
                if (svc.memory_limit_mb && svc.memory_limit_mb > 0) {
                  podLimitMap.set(svc.id, svc.memory_limit_mb);
                }
              });
              (memLimitGrouped?.series || []).forEach((ls) => {
                const lastPt = (ls.points || []).filter((p) => p.value > 0).pop();
                if (lastPt && !podLimitMap.has(ls.resource_id)) {
                  podLimitMap.set(ls.resource_id, lastPt.value);
                }
              });

              const totalCores = Math.max(1, overview?.total_cores || 1);
              const isCpu = config.key === 'cpu';
              const isMemory = config.key === 'memory';

              // Pure simple bar traces using standard ISO timestamps
              const plotData: Data[] = isStacked
                ? (groupData?.series || []).map((s, idx) => {
                    const podLimit = podLimitMap.get(s.resource_id) || 0;

                    // Normalize CPU values by total cluster cores so the stacked total is bounded between 0-100%
                    const yValues = (s.points || []).map((p) => {
                      if (isCpu) {
                        return Math.max(0, Math.round((p.value / totalCores) * 100) / 100);
                      }
                      return p.value;
                    });

                    const customdata = (s.points || []).map((p) => {
                      if (isCpu) {
                        const rawCores = (p.value / 100).toFixed(2);
                        const normPct = (p.value / totalCores).toFixed(1);
                        return `Cluster CPU: ${normPct}% (${rawCores} cores / ${totalCores} total)`;
                      }
                      if (isMemory) {
                        if (podLimit > 0) {
                          const pct = ((p.value / podLimit) * 100).toFixed(1);
                          return `Limit: ${podLimit.toLocaleString()} MB (${pct}% used)`;
                        }
                        return 'Limit: Uncapped';
                      }
                      return '';
                    });

                    return {
                      x: (s.points || []).map((p) => p.timestamp),
                      y: yValues,
                      type: 'bar',
                      name: cleanServiceName(s.name),
                      marker: { color: PALETTE[idx % PALETTE.length] },
                      customdata,
                      hovertemplate: isCpu
                        ? `<b>${cleanServiceName(s.name)}</b><br>%{customdata}<extra></extra>`
                        : isMemory
                        ? `<b>${cleanServiceName(s.name)}</b><br>Used: %{y:.1f} MB<br>%{customdata}<extra></extra>`
                        : `${cleanServiceName(s.name)}: %{y:.2f} ${config.unit}<extra></extra>`,
                    };
                  })
                : [
                    (() => {
                      const selectedServiceObj = services.find((s) => s.id === chartResource);
                      const staticLimit = selectedServiceObj?.memory_limit_mb || 0;

                      const yValues = (singleData?.points || []).map((p) => {
                        if (isCpu) {
                          return Math.max(0, Math.round((p.value / totalCores) * 100) / 100);
                        }
                        return p.value;
                      });

                      const customdata = (singleData?.points || []).map((p) => {
                        if (isCpu) {
                          const rawCores = (p.value / 100).toFixed(2);
                          const normPct = (p.value / totalCores).toFixed(1);
                          return `Cluster CPU: ${normPct}% (${rawCores} cores / ${totalCores} total)`;
                        }
                        if (isMemory) {
                          if (staticLimit > 0) {
                            const pct = ((p.value / staticLimit) * 100).toFixed(1);
                            return `Limit: ${staticLimit.toLocaleString()} MB (${pct}% used)`;
                          }
                          return 'Limit: Uncapped';
                        }
                        return '';
                      });

                      return {
                        x: (singleData?.points || []).map((p) => p.timestamp),
                        y: yValues,
                        type: 'bar',
                        name: selectedServiceObj?.name || 'Service',
                        marker: { color: config.color },
                        customdata,
                        hovertemplate: isCpu
                          ? `<b>${selectedServiceObj?.name || 'Service'}</b><br>%{customdata}<extra></extra>`
                          : isMemory
                          ? `<b>${selectedServiceObj?.name || 'Service'}</b><br>Used: %{y:.1f} MB<br>%{customdata}<extra></extra>`
                          : `${selectedServiceObj?.name || 'Service'}: %{y:.2f} ${config.unit}<extra></extra>`,
                      };
                    })(),
                  ];

              // Dynamic Memory Limit Time Series (Only for Memory Usage Chart)
              if (config.key === 'memory') {
                if (isStacked) {
                  // Aggregate all pod limits bucketed by timestamp for an accurate time series
                  const limitSeries = memLimitGrouped?.series || [];
                  const limitByTimestamp = new Map<string, number>();

                  for (const s of limitSeries) {
                    for (const pt of s.points || []) {
                      if (pt.value > 0) {
                        const current = limitByTimestamp.get(pt.timestamp) || 0;
                        limitByTimestamp.set(pt.timestamp, current + pt.value);
                      }
                    }
                  }

                  const sortedTimestamps = Array.from(limitByTimestamp.keys()).sort();
                  const limitPoints = sortedTimestamps
                    .map((ts) => ({ timestamp: ts, value: limitByTimestamp.get(ts)! }))
                    .filter((p) => p.value > 0);

                  // Fallback to current live pod limits if Prometheus timeseries has not accumulated points yet
                  if (limitPoints.length === 0) {
                    const currentTotalLimit = services.reduce((acc, s) => acc + (s.memory_limit_mb || 0), 0);
                    if (currentTotalLimit > 0) {
                      const allTimestamps = (groupData?.series || []).flatMap((s) => (s.points || []).map((p) => p.timestamp));
                      const uniqueTimestamps = Array.from(new Set(allTimestamps)).sort();
                      uniqueTimestamps.forEach((ts) => {
                        limitPoints.push({ timestamp: ts, value: currentTotalLimit });
                      });
                    }
                  }

                  if (limitPoints.length > 0) {
                    plotData.push({
                      x: limitPoints.map((p) => p.timestamp),
                      y: limitPoints.map((p) => p.value),
                      type: 'scatter',
                      mode: 'lines',
                      name: 'Total Allocated Limit',
                      line: { color: '#ef4444', width: 2, dash: 'dash' },
                      hovertemplate: 'Total Allocated Limit: %{y:.1f} MB<extra></extra>',
                    });
                  }
                } else {
                  // Single service view: plot exact time series for that pod's limit
                  const limitPoints = (memLimitSingle?.points || []).filter((p) => p.value > 0);
                  const selectedServiceObj = services.find((s) => s.id === chartResource);
                  const staticLimit = selectedServiceObj?.memory_limit_mb || 0;

                  if (limitPoints.length > 0) {
                    plotData.push({
                      x: limitPoints.map((p) => p.timestamp),
                      y: limitPoints.map((p) => p.value),
                      type: 'scatter',
                      mode: 'lines',
                      name: 'Pod Memory Limit',
                      line: { color: '#ef4444', width: 2, dash: 'dash' },
                      hovertemplate: 'Pod Memory Limit: %{y:.1f} MB<extra></extra>',
                    });
                  } else if (staticLimit > 0 && (singleData?.points || []).length > 0) {
                    plotData.push({
                      x: (singleData?.points || []).map((p) => p.timestamp),
                      y: (singleData?.points || []).map(() => staticLimit),
                      type: 'scatter',
                      mode: 'lines',
                      name: 'Pod Memory Limit',
                      line: { color: '#ef4444', width: 2, dash: 'dash' },
                      hovertemplate: `Pod Memory Limit: ${staticLimit} MB<extra></extra>`,
                    });
                  }
                }
              }

              // Secondary Y-Axis: Active Node Count Time Series (Only for CPU Chart in Stacked View)
              if (config.key === 'cpu' && isStacked) {
                const nodeCountMap = new Map<string, number>();
                if (nodeTimeseries && nodeTimeseries.series && nodeTimeseries.series.length > 0) {
                  for (const s of nodeTimeseries.series) {
                    for (const pt of s.points || []) {
                      nodeCountMap.set(pt.timestamp, (nodeCountMap.get(pt.timestamp) || 0) + 1);
                    }
                  }
                }

                let nodePoints: { timestamp: string; value: number }[] = [];
                if (nodeCountMap.size > 0) {
                  const sortedTs = Array.from(nodeCountMap.keys()).sort();
                  nodePoints = sortedTs.map((ts) => ({ timestamp: ts, value: nodeCountMap.get(ts)! }));
                } else {
                  const fallbackNodes = Math.max(1, overview?.total_nodes || 1);
                  const allTimestamps = (groupData?.series || []).flatMap((s) => (s.points || []).map((p) => p.timestamp));
                  const uniqueTs = Array.from(new Set(allTimestamps)).sort();
                  nodePoints = uniqueTs.map((ts) => ({ timestamp: ts, value: fallbackNodes }));
                }

                if (nodePoints.length > 0) {
                  plotData.push({
                    x: nodePoints.map((p) => p.timestamp),
                    y: nodePoints.map((p) => p.value),
                    type: 'scatter',
                    mode: 'lines',
                    line: { shape: 'hv', color: '#8b5cf6', width: 2, dash: 'dot' },
                    name: 'Active Nodes',
                    yaxis: 'y2',
                    hovertemplate: 'Active Nodes: %{y:.0f}<extra></extra>',
                  });
                }
              }

              return (
                <div key={config.key} className="monitoring-chart-card">
                  <div className="chart-card-header">
                    <h3 className="chart-card-title">
                      {config.key === 'cpu'
                        ? `CPU Utilization (% of ${totalCores} Cores)`
                        : `${config.title} (${config.unit})`}
                    </h3>
                  </div>

                  <Plot
                    data={plotData}
                    layout={{
                      autosize: true,
                      height: 320,
                      margin: { l: 50, r: config.key === 'cpu' ? 45 : 20, t: 15, b: 45 },
                      barmode: isStacked ? 'stack' : 'group',
                      showlegend: isStacked,
                      xaxis: {
                        type: 'date',
                      },
                      yaxis: {
                        title: { text: config.unit, font: { size: 11 } },
                        rangemode: 'tozero',
                        autorange: true,
                      },
                      ...(config.key === 'cpu'
                        ? {
                            yaxis2: {
                              title: { text: 'Nodes', font: { size: 11, color: '#8b5cf6' } },
                              overlaying: 'y',
                              side: 'right',
                              rangemode: 'tozero',
                              dtick: 1,
                              tickformat: 'd',
                              showgrid: false,
                              tickfont: { size: 10, color: '#8b5cf6' },
                            },
                          }
                        : {}),
                      legend: {
                        orientation: 'h',
                        y: -0.25,
                        font: { size: 10 },
                      },
                    }}
                    config={{ responsive: true, displayModeBar: false }}
                    style={{ width: '100%', height: '320px' }}
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
