import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import type { JobRun, TaskDefinition } from '../lib/jobsTypes';
import { formatDuration } from '../lib/cronUtils';

interface Props {
  runs: JobRun[];
  tasks?: TaskDefinition[];
  onRunClick: (runId: string) => void;
}

const STATE_COLORS: Record<string, string> = {
  success: '#22c55e',
  failed: '#ef4444',
  running: '#3b82f6',
  queued: '#6b7280',
  up_for_retry: '#f59e0b',
  upstream_failed: '#ef4444',
  cancelled: '#6b7280',
  skipped: '#9ca3af',
};

const COLUMN_WIDTH = 32;
const LABEL_COL_WIDTH = 190;

export default function JobRunsTimelineChart({ runs, tasks = [], onRunClick }: Props) {
  const [dateFilter, setDateFilter] = useState<string>('');
  const [page, setPage] = useState<number>(0);
  const pageSize = 30;

  const getRunTime = (r: JobRun) => {
    if (r.started_at) return new Date(r.started_at).getTime();
    if ((r as any).created_at) return new Date((r as any).created_at).getTime();
    return Date.now();
  };

  // Filter runs by date if set
  const filteredRuns = useMemo(() => {
    let list = [...runs];
    if (dateFilter) {
      const endOfDay = new Date(dateFilter);
      endOfDay.setHours(23, 59, 59, 999);
      const filterTime = endOfDay.getTime();
      list = list.filter((r) => getRunTime(r) <= filterTime);
    }
    // Sort chronological (oldest to newest for timeline chart left to right)
    list.sort((a, b) => getRunTime(a) - getRunTime(b));
    return list;
  }, [runs, dateFilter]);

  const totalPages = Math.ceil(filteredRuns.length / pageSize) || 1;
  const visibleRuns = useMemo(() => {
    const start = page * pageSize;
    return filteredRuns.slice(start, start + pageSize);
  }, [filteredRuns, page]);

  // Determine all task keys to display in matrix
  const taskKeys = useMemo(() => {
    if (tasks.length > 0) return tasks.map((t) => ({ key: t.task_key, name: t.name || t.task_key }));
    const set = new Map<string, string>();
    runs.forEach((r) => {
      r.task_runs.forEach((tr) => {
        if (!set.has(tr.task_key)) set.set(tr.task_key, tr.task_key);
      });
    });
    return Array.from(set.entries()).map(([key, name]) => ({ key, name }));
  }, [tasks, runs]);

  // Max duration for scaling bar chart
  const maxDuration = useMemo(() => {
    const max = Math.max(...visibleRuns.map((r) => r.duration_seconds ?? 0), 10);
    return Math.ceil(max);
  }, [visibleRuns]);

  if (runs.length === 0) return null;

  return (
    <div className="jd-chart-card" style={{ marginBottom: '1.25rem' }}>
      {/* Header Controls */}
      <div className="jd-chart-header">
        <div className="jd-chart-title" style={{ fontSize: '1rem', fontWeight: 700 }}>Runs</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
            <span>Started before</span>
            <div className="search-bar-wrapper" style={{ padding: '3px 8px', maxWidth: 160 }}>
              <Calendar size={13} className="search-icon" />
              <input
                type="date"
                className="search-input"
                style={{ fontSize: '0.78rem' }}
                value={dateFilter}
                onChange={(e) => { setDateFilter(e.target.value); setPage(0); }}
              />
              {dateFilter && (
                <button
                  type="button"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--color-text-subtle)', fontSize: '0.75rem' }}
                  onClick={() => setDateFilter('')}
                  title="Clear filter"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                {page + 1} / {totalPages}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <button
                className="btn btn-secondary btn-sm"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Timeline Chart Area */}
      <div className="jd-run-chart-shell" style={{ paddingTop: '1rem' }}>
        <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
          <div style={{ minWidth: visibleRuns.length * (COLUMN_WIDTH + 8) + LABEL_COL_WIDTH + 40 }}>
            
            {/* 1. Dates Header Row */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
              {/* Left Spacer */}
              <div style={{ width: LABEL_COL_WIDTH, flexShrink: 0 }} />

              {/* Date Columns */}
              <div style={{ display: 'flex', gap: 8 }}>
                {visibleRuns.map((run, idx) => {
                  const d = run.started_at ? new Date(run.started_at) : null;
                  const dateStr = d ? d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' }) : '';
                  const showLabel = idx === 0 || idx % Math.ceil(visibleRuns.length / 6) === 0;
                  return (
                    <div
                      key={run.job_run_id}
                      style={{
                        width: COLUMN_WIDTH,
                        textAlign: 'center',
                        fontSize: '0.72rem',
                        color: 'var(--color-text-muted)',
                        whiteSpace: 'nowrap',
                        visibility: showLabel ? 'visible' : 'hidden',
                        flexShrink: 0,
                      }}
                    >
                      {dateStr}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 2. Run Total Duration Bar Chart Row */}
            <div style={{ display: 'flex', alignItems: 'flex-end', marginBottom: 16 }}>
              {/* Left Y-Axis Title + Duration Ticks */}
              <div style={{ width: LABEL_COL_WIDTH, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8, paddingRight: 12, height: 120 }}>
                <div className="jd-run-chart-axis-title">Run total duration</div>
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%', fontSize: '0.72rem', color: 'var(--color-text-subtle)', textAlign: 'right' }}>
                  <span>{formatDuration(maxDuration)}</span>
                  <span>{formatDuration(Math.round(maxDuration / 2))}</span>
                  <span>0s</span>
                </div>
              </div>

              {/* Duration Bars Container with Grid Line background */}
              <div style={{ display: 'flex', gap: 8, height: 120, alignItems: 'flex-end', position: 'relative', borderLeft: '1px solid var(--color-border)', borderBottom: '1px solid var(--color-border)', paddingLeft: 0 }}>
                {/* Horizontal Gridlines */}
                <div style={{ position: 'absolute', left: 0, right: 0, top: 0, borderTop: '1px dashed var(--color-border)', opacity: 0.5, pointerEvents: 'none' }} />
                <div style={{ position: 'absolute', left: 0, right: 0, top: 60, borderTop: '1px dashed var(--color-border)', opacity: 0.5, pointerEvents: 'none' }} />

                {visibleRuns.map((run) => {
                  const dur = run.duration_seconds ?? 5;
                  const heightPercent = Math.max(6, Math.min(100, (dur / maxDuration) * 100));
                  const barColor = STATE_COLORS[run.state] ?? 'var(--color-primary)';
                  return (
                    <div
                      key={run.job_run_id}
                      style={{ width: COLUMN_WIDTH, height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'flex-end', flexShrink: 0 }}
                    >
                      <div
                        onClick={() => onRunClick(run.job_run_id)}
                        title={`Run ${run.job_run_id.slice(0, 8)} (${run.state}) - ${formatDuration(dur)}`}
                        style={{
                          width: 22,
                          height: `${heightPercent}%`,
                          background: run.state === 'failed' ? 'repeating-linear-gradient(45deg, #ef4444, #ef4444 6px, #dc2626 6px, #dc2626 12px)' : barColor,
                          borderRadius: '4px 4px 0 0',
                          cursor: 'pointer',
                          transition: 'opacity 0.15s ease, transform 0.15s ease',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.82'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 3. Tasks Heatmap Matrix Section */}
            {taskKeys.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'flex-start', marginTop: 12 }}>
                {/* Left Y-Axis Title "Tasks" */}
                <div style={{ width: 28, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', height: taskKeys.length * 24 }}>
                  <div className="jd-run-chart-task-axis-title">Tasks</div>
                </div>

                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {taskKeys.map(({ key, name }) => (
                    <div key={key} style={{ display: 'flex', alignItems: 'center' }}>
                      {/* Left Task Name Label */}
                      <div
                        title={name}
                        style={{
                          width: LABEL_COL_WIDTH - 28,
                          flexShrink: 0,
                          paddingRight: 12,
                          fontSize: '0.75rem',
                          color: 'var(--color-text-muted)',
                          textOverflow: 'ellipsis',
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                          textAlign: 'right',
                        }}
                      >
                        {name}
                      </div>

                      {/* Task Status Pills row aligned perfectly with columns */}
                      <div style={{ display: 'flex', gap: 8 }}>
                        {visibleRuns.map((run) => {
                          const tr = run.task_runs.find((t) => t.task_key === key);
                          const pillColor = tr ? (STATE_COLORS[tr.state] ?? '#9ca3af') : 'rgba(156,163,175,0.25)';
                          return (
                            <div
                              key={`${run.job_run_id}-${key}`}
                              style={{ width: COLUMN_WIDTH, display: 'flex', justifyContent: 'center', flexShrink: 0 }}
                            >
                              <div
                                onClick={() => onRunClick(run.job_run_id)}
                                title={`${name}: ${tr?.state ?? 'not run'}`}
                                style={{
                                  width: 22,
                                  height: 14,
                                  borderRadius: 4,
                                  background: pillColor,
                                  cursor: 'pointer',
                                  transition: 'transform 0.15s ease',
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.15)'; }}
                                onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
                              />
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
