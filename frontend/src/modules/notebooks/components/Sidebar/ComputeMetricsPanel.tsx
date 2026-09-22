import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  Cpu,
  HardDrive,
  RefreshCw,
  Server,
  Layers,
  Clock,
  CheckCircle2,
  AlertCircle,
  Pause,
  Play,
  TrendingUp,
} from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import { useNotebookStore } from '../../store/notebookStore';

interface MetricPoint {
  timestamp: string;
  value: number;
}

interface ComputeMetricsData {
  resource_id: string;
  status: string;
  phase?: string | null;
  pod_name?: string | null;
  node_name?: string | null;
  runtime: string;
  profile: string;
  cpu_cores_limit: number;
  cpu_cores_request: number;
  memory_limit_mb: number;
  memory_request_mb: number;
  cpu_percent: number;
  cpu_millicores: number;
  memory_mb: number;
  memory_percent: number;
  cpu_timeseries: MetricPoint[];
  memory_timeseries: MetricPoint[];
  collected_at: string;
}

type TimeRange = '15m' | '1h' | '6h' | '24h';

// Helper component for interactive SVG Area Chart
function TimeSeriesChart({
  title,
  unit,
  points,
  color,
  limitValue,
  limitLabel,
}: {
  title: string;
  unit: string;
  points: MetricPoint[];
  color: string;
  limitValue?: number;
  limitLabel?: string;
}) {
  const [hoveredPoint, setHoveredPoint] = useState<{ point: MetricPoint; x: number; y: number } | null>(null);

  if (!points || points.length === 0) {
    return (
      <div className="dbx-chart-card">
        <div className="dbx-chart-header">
          <span className="dbx-chart-title">{title}</span>
        </div>
        <div className="dbx-chart-empty">
          <Clock size={16} />
          <span>Collecting telemetry data...</span>
        </div>
      </div>
    );
  }

  const width = 340;
  const height = 110;
  const padding = { top: 12, right: 12, bottom: 20, left: 36 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const values = points.map((p) => p.value);
  const rawMax = Math.max(...values, limitValue ?? 0);
  const maxY = rawMax > 0 ? (limitValue && limitValue > rawMax * 0.9 ? limitValue * 1.1 : rawMax * 1.25) : 10;
  const minY = 0;

  const getX = (index: number) => {
    if (points.length <= 1) return padding.left + chartWidth / 2;
    return padding.left + (index / (points.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    const clamped = Math.max(minY, Math.min(maxY, val));
    return padding.top + chartHeight - ((clamped - minY) / (maxY - minY)) * chartHeight;
  };

  // Build SVG path
  const pathD = points.reduce((acc, curr, idx) => {
    const x = getX(idx);
    const y = getY(curr.value);
    return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, '');

  const areaD = `${pathD} L ${getX(points.length - 1)} ${padding.top + chartHeight} L ${getX(0)} ${padding.top + chartHeight} Z`;

  const limitY = limitValue !== undefined && limitValue <= maxY ? getY(limitValue) : null;
  const latestValue = values[values.length - 1] ?? 0;
  const avgValue = values.reduce((a, b) => a + b, 0) / (values.length || 1);

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="dbx-chart-card">
      <div className="dbx-chart-header">
        <div className="dbx-chart-header-left">
          <span className="dbx-chart-title">{title}</span>
          <span className="dbx-chart-latest" style={{ color }}>
            {latestValue.toFixed(latestValue < 10 && latestValue !== 0 ? 1 : 0)} {unit}
          </span>
        </div>
        <div className="dbx-chart-header-right">
          <span className="dbx-chart-avg">Avg: {avgValue.toFixed(avgValue < 10 ? 1 : 0)} {unit}</span>
        </div>
      </div>

      <div className="dbx-chart-svg-wrapper" onMouseLeave={() => setHoveredPoint(null)}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="dbx-metric-svg"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id={`grad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.32" />
              <stop offset="100%" stopColor={color} stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={width - padding.right}
            y2={padding.top}
            stroke="#f1f5f9"
            strokeDasharray="2,2"
          />
          <line
            x1={padding.left}
            y1={padding.top + chartHeight / 2}
            x2={width - padding.right}
            y2={padding.top + chartHeight / 2}
            stroke="#f1f5f9"
            strokeDasharray="2,2"
          />
          <line
            x1={padding.left}
            y1={padding.top + chartHeight}
            x2={width - padding.right}
            y2={padding.top + chartHeight}
            stroke="#e2e8f0"
          />

          {/* Y Axis Labels */}
          <text x={padding.left - 4} y={padding.top + 8} textAnchor="end" className="dbx-chart-axis-label">
            {maxY >= 1000 ? `${(maxY / 1000).toFixed(1)}k` : maxY.toFixed(0)}
          </text>
          <text x={padding.left - 4} y={padding.top + chartHeight} textAnchor="end" className="dbx-chart-axis-label">
            0
          </text>

          {/* Limit Baseline */}
          {limitY !== null && (
            <>
              <line
                x1={padding.left}
                y1={limitY}
                x2={width - padding.right}
                y2={limitY}
                stroke="#ef4444"
                strokeDasharray="3,3"
                strokeWidth="1"
              />
              {limitLabel && (
                <text
                  x={width - padding.right - 2}
                  y={Math.max(padding.top + 8, limitY - 3)}
                  textAnchor="end"
                  className="dbx-chart-limit-label"
                >
                  {limitLabel}
                </text>
              )}
            </>
          )}

          {/* Area Fill */}
          <path d={areaD} fill={`url(#grad-${color.replace('#', '')})`} />

          {/* Line Path */}
          <path
            d={pathD}
            fill="none"
            stroke={color}
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Hover interactive points */}
          {points.map((pt, idx) => {
            const cx = getX(idx);
            const cy = getY(pt.value);
            return (
              <circle
                key={idx}
                cx={cx}
                cy={cy}
                r={hoveredPoint?.point === pt ? 4 : 2}
                fill={hoveredPoint?.point === pt ? '#ffffff' : color}
                stroke={color}
                strokeWidth={hoveredPoint?.point === pt ? 2 : 1}
                className="dbx-chart-point"
                onMouseEnter={() => setHoveredPoint({ point: pt, x: cx, y: cy })}
              />
            );
          })}
        </svg>

        {/* Tooltip */}
        {hoveredPoint && (
          <div
            className="dbx-chart-tooltip"
            style={{
              left: `${(hoveredPoint.x / width) * 100}%`,
              top: `${Math.max(10, hoveredPoint.y - 12)}px`,
            }}
          >
            <div className="dbx-tooltip-val">
              {hoveredPoint.point.value.toFixed(1)} {unit}
            </div>
            <div className="dbx-tooltip-time">{formatTime(hoveredPoint.point.timestamp)}</div>
          </div>
        )}
      </div>

      {/* X Axis Range Labels */}
      <div className="dbx-chart-footer">
        <span>{formatTime(points[0]?.timestamp)}</span>
        <span>{formatTime(points[points.length - 1]?.timestamp)}</span>
      </div>
    </div>
  );
}

export default function ComputeMetricsPanel() {
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const notebookId = useNotebookStore((s) => s.notebookId);
  const setActiveRightSidebarTab = useNotebookStore((s) => s.setActiveRightSidebarTab);

  const [metrics, setMetrics] = useState<ComputeMetricsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('15m');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date());

  const activeResourceId = selectedPod?.resource_id;

  const fetchMetrics = useCallback(
    async (showSpinner = false) => {
      if (!activeResourceId) return;
      if (showSpinner) setLoading(true);
      setError(null);
      try {
        const data = await computeApi.getResourceMetrics(activeResourceId, timeRange);
        setMetrics(data);
        setLastRefreshedAt(new Date());
      } catch (err: any) {
        console.warn('Failed to load compute metrics:', err);
        setError(err.response?.data?.message || err.message || 'Unable to fetch telemetry');
      } finally {
        if (showSpinner) setLoading(false);
      }
    },
    [activeResourceId, timeRange]
  );

  // Initial and range-change fetch
  useEffect(() => {
    if (activeResourceId) {
      fetchMetrics(true);
    }
  }, [activeResourceId, timeRange, fetchMetrics]);

  // Polling effect every 5 seconds when autoRefresh is enabled
  useEffect(() => {
    if (!autoRefresh || !activeResourceId) return;
    const interval = setInterval(() => {
      fetchMetrics(false);
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, activeResourceId, fetchMetrics]);

  if (!activeResourceId) {
    return (
      <div className="dbx-metrics-empty-state">
        <Server size={32} className="dbx-empty-icon" />
        <h4 className="dbx-empty-title">No Compute Attached</h4>
        <p className="dbx-empty-desc">
          Attach or start a compute instance to view live CPU, memory utilization, and Prometheus telemetry.
        </p>
        <button
          type="button"
          className="dbx-btn-primary"
          onClick={() => setActiveRightSidebarTab('config')}
        >
          Configure Compute
        </button>
      </div>
    );
  }

  const isRunning = (metrics?.status || metrics?.phase || '').toLowerCase() === 'running';
  const cpuPercent = metrics?.cpu_percent ?? 0;
  const memoryPercent = metrics?.memory_percent ?? 0;
  const memoryMb = metrics?.memory_mb ?? 0;
  const memoryLimitMb = metrics?.memory_limit_mb ?? 2048;
  const memoryRequestMb = metrics?.memory_request_mb ?? 512;
  const cpuLimit = metrics?.cpu_cores_limit ?? 1.0;
  const cpuRequest = metrics?.cpu_cores_request ?? 0.25;

  const getProgressColor = (pct: number) => {
    if (pct >= 85) return '#ef4444';
    if (pct >= 65) return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="dbx-metrics-container">
      {/* ── Header Controls ── */}
      <div className="dbx-metrics-toolbar">
        <div className="dbx-metrics-status-badge-wrap">
          <span
            className={`dbx-status-dot ${
              isRunning ? 'is-running' : metrics?.status === 'Pending' ? 'is-pending' : 'is-stopped'
            }`}
          />
          <span className="dbx-status-text">
            {isRunning ? 'Running' : metrics?.status || 'Active'}
          </span>
        </div>

        <div className="dbx-metrics-actions">
          {/* Time range selector */}
          <div className="dbx-range-pill-group">
            {(['15m', '1h', '6h', '24h'] as TimeRange[]).map((r) => (
              <button
                key={r}
                type="button"
                className={`dbx-range-pill ${timeRange === r ? 'is-active' : ''}`}
                onClick={() => setTimeRange(r)}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Auto-refresh toggle */}
          <button
            type="button"
            className={`dbx-icon-btn ${autoRefresh ? 'is-active' : ''}`}
            onClick={() => setAutoRefresh(!autoRefresh)}
            title={autoRefresh ? 'Pause auto-refresh (every 5s)' : 'Resume auto-refresh'}
          >
            {autoRefresh ? <Pause size={12} /> : <Play size={12} />}
          </button>

          {/* Manual refresh button */}
          <button
            type="button"
            className={`dbx-icon-btn ${loading ? 'is-spinning' : ''}`}
            onClick={() => fetchMetrics(true)}
            title="Refresh now"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {error && (
        <div className="dbx-error-banner" style={{ margin: '8px 12px' }}>
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* ── Pod & Node Info Card ── */}
      <div className="dbx-card" style={{ margin: '0 12px 10px 12px' }}>
        <div className="dbx-card-row">
          <div className="dbx-card-item">
            <span className="dbx-label-dim">Resource ID</span>
            <span className="dbx-val-mono">{activeResourceId.slice(0, 12)}</span>
          </div>
          <div className="dbx-card-item">
            <span className="dbx-label-dim">Runtime</span>
            <span className="dbx-val-bold">{metrics?.runtime?.toUpperCase() || 'DUCKDB'}</span>
          </div>
        </div>

        {metrics?.pod_name && (
          <div className="dbx-card-row" style={{ marginTop: '6px' }}>
            <div className="dbx-card-item" style={{ width: '100%' }}>
              <span className="dbx-label-dim">Pod Name</span>
              <span className="dbx-val-mono" style={{ fontSize: '0.7rem', wordBreak: 'break-all' }}>
                {metrics.pod_name}
              </span>
            </div>
          </div>
        )}

        {metrics?.node_name && (
          <div className="dbx-card-row" style={{ marginTop: '4px' }}>
            <div className="dbx-card-item" style={{ width: '100%' }}>
              <span className="dbx-label-dim">Node Pool</span>
              <span className="dbx-val-mono" style={{ fontSize: '0.7rem', color: '#475569' }}>
                {metrics.node_name}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Gauges / Live Utilization Summary ── */}
      <div className="dbx-gauges-grid">
        {/* CPU Gauge Card */}
        <div className="dbx-gauge-card">
          <div className="dbx-gauge-header">
            <div className="dbx-gauge-title-wrap">
              <Cpu size={14} className="dbx-gauge-icon" style={{ color: '#1b6ef3' }} />
              <span className="dbx-gauge-title">CPU Utilization</span>
            </div>
            <span className="dbx-gauge-value" style={{ color: getProgressColor(cpuPercent) }}>
              {cpuPercent.toFixed(1)}%
            </span>
          </div>

          <div className="dbx-progress-track">
            <div
              className="dbx-progress-bar"
              style={{
                width: `${Math.min(100, Math.max(2, cpuPercent))}%`,
                backgroundColor: getProgressColor(cpuPercent),
              }}
            />
          </div>

          <div className="dbx-gauge-footer">
            <span>Req: {cpuRequest} vCPU</span>
            <span>Limit: {cpuLimit} vCPU</span>
          </div>
        </div>

        {/* Memory Gauge Card */}
        <div className="dbx-gauge-card">
          <div className="dbx-gauge-header">
            <div className="dbx-gauge-title-wrap">
              <HardDrive size={14} className="dbx-gauge-icon" style={{ color: '#8b5cf6' }} />
              <span className="dbx-gauge-title">Memory Utilization</span>
            </div>
            <span className="dbx-gauge-value" style={{ color: getProgressColor(memoryPercent) }}>
              {memoryPercent.toFixed(1)}%
            </span>
          </div>

          <div className="dbx-progress-track">
            <div
              className="dbx-progress-bar"
              style={{
                width: `${Math.min(100, Math.max(2, memoryPercent))}%`,
                backgroundColor: getProgressColor(memoryPercent),
              }}
            />
          </div>

          <div className="dbx-gauge-footer">
            <span>Used: {memoryMb.toFixed(0)} MB</span>
            <span>Limit: {(memoryLimitMb / 1024).toFixed(1)} GB</span>
          </div>
        </div>
      </div>

      {/* ── Telemetry Charts ── */}
      <div className="dbx-charts-section">
        <div className="dbx-section-heading">
          <TrendingUp size={13} />
          <span>Prometheus Telemetry ({timeRange})</span>
        </div>

        {/* CPU Time Series */}
        <TimeSeriesChart
          title="CPU Usage"
          unit="%"
          points={metrics?.cpu_timeseries || []}
          color="#1b6ef3"
          limitValue={100}
          limitLabel="100% Core Limit"
        />

        {/* Memory Time Series */}
        <TimeSeriesChart
          title="Memory Usage"
          unit="MB"
          points={metrics?.memory_timeseries || []}
          color="#8b5cf6"
          limitValue={memoryLimitMb}
          limitLabel={`${(memoryLimitMb / 1024).toFixed(1)}GB Limit`}
        />
      </div>

      {/* Footer Timestamp */}
      <div className="dbx-metrics-footer">
        <span>Last sampled: {lastRefreshedAt.toLocaleTimeString()}</span>
        <span>• Auto-refresh {autoRefresh ? 'on (5s)' : 'off'}</span>
      </div>
    </div>
  );
}
