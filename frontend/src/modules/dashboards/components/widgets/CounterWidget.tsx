/**
 * CounterWidget — single KPI value with delta comparison + sparkline.
 * Reference: counter-d93df35ca3de1303c4c030bc672d25ce.png
 *            counter-customization-options-940f0b880abc7bea8c4e55faf19a0637.png
 */

import { useMemo } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useDatasetQuery } from '@/modules/dashboards/hooks/useDashboard';
import type { Widget } from '@/types/dashboard';

function formatValue(val: number, format?: string): string {
  if (!val && val !== 0) return '—';
  if (format === 'percent') return `${(val * 100).toFixed(1)}%`;
  if (format === 'currency') return `$${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
  return val.toLocaleString();
}

interface Props {
  widget: Widget;
}

export default function CounterWidget({ widget }: Props) {
  const { filterState, paramState } = useDashboardStore();
  const cfg = widget.chartConfig;

  const { data: queryResult, isLoading } = useDatasetQuery(
    cfg?.datasetId,
    paramState as any,
    filterState as any,
    !!cfg?.datasetId
  );

  const { mainValue, compareValue, delta, deltaPercent, trend } = useMemo(() => {
    if (!queryResult || !cfg?.yFields?.[0]) {
      return { mainValue: null, compareValue: null, delta: null, deltaPercent: null, trend: null };
    }
    const rows = queryResult.rows;
    const yField = cfg.yFields[0];
    const main = rows[0] ? Number(rows[0][yField]) : null;
    const compare = cfg.comparisonField && rows[0]
      ? Number(rows[0][cfg.comparisonField])
      : (rows[1] ? Number(rows[1][yField]) : null);

    const d = main !== null && compare !== null ? main - compare : null;
    const dp = d !== null && compare ? (d / compare) * 100 : null;
    const t = d !== null ? (d >= 0 ? 'up' : 'down') : null;

    return { mainValue: main, compareValue: compare, delta: d, deltaPercent: dp, trend: t };
  }, [queryResult, cfg]);

  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
        Loading…
      </div>
    );
  }

  // Conditional formatting
  let valueColor = 'var(--color-text)';
  if (cfg?.conditionalFormatting && mainValue !== null) {
    for (const rule of cfg.conditionalFormatting) {
      const inMin = rule.min === undefined || mainValue >= rule.min;
      const inMax = rule.max === undefined || mainValue <= rule.max;
      if (inMin && inMax) { valueColor = rule.color; break; }
    }
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
      padding: 16,
    }}>
      {/* Main value */}
      <div style={{ fontSize: '2.4rem', fontWeight: 700, lineHeight: 1, color: valueColor }}>
        {mainValue !== null ? formatValue(mainValue, cfg?.numberFormat?.type) : '—'}
      </div>

      {/* Delta */}
      {delta !== null && deltaPercent !== null && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: '0.78rem',
          color: trend === 'up' ? 'var(--color-success)' : 'var(--color-danger)',
        }}>
          {trend === 'up' ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          <span>{delta > 0 ? '+' : ''}{formatValue(delta)} ({deltaPercent.toFixed(1)}%)</span>
        </div>
      )}

      {/* Label */}
      {cfg?.xField && (
        <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
          {cfg.xField}
        </div>
      )}
    </div>
  );
}

