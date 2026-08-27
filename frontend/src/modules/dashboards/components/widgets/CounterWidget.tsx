/**
 * CounterWidget — single KPI value with delta comparison + sparkline.
 * Reference: counter-d93df35ca3de1303c4c030bc672d25ce.png
 *            counter-customization-options-940f0b880abc7bea8c4e55faf19a0637.png
 */

import { useMemo } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useDatasetQuery } from '@/modules/dashboards/hooks/useDashboard';
import { aggregateValues } from '@/modules/dashboards/utils/dataTransforms';
import type { Widget, NumberFormat } from '@/types/dashboard';

function formatValue(val: number, format?: NumberFormat): string {
  if (val === null || val === undefined || isNaN(val)) return '—';

  const type = format?.type ?? 'number';
  const abbreviation = format?.abbreviation ?? 'none';
  const decimalMode = format?.decimalMode ?? (format?.decimals !== undefined ? 'exact' : 'all');
  const decimals = format?.decimals ?? 2;
  const symbol = format?.currencySymbol || '$';

  let minDecimals = 0;
  let maxDecimals = 2;

  if (decimalMode === 'all') {
    minDecimals = 0;
    maxDecimals = 20;
  } else if (decimalMode === 'exact') {
    minDecimals = decimals;
    maxDecimals = decimals;
  } else if (decimalMode === 'max') {
    minDecimals = 0;
    maxDecimals = decimals;
  }

  if (type === 'percent') {
    const pVal = val * 100;
    if (decimalMode === 'all') {
      return `${pVal}%`;
    }
    return `${pVal.toLocaleString(undefined, {
      minimumFractionDigits: minDecimals,
      maximumFractionDigits: maxDecimals,
    })}%`;
  }

  let formattedNum = '';
  if (abbreviation === 'scientific') {
    formattedNum = val.toExponential(decimalMode === 'all' ? undefined : decimals);
  } else if (abbreviation === 'compact' || (abbreviation !== 'none' && Math.abs(val) >= 1_000)) {
    if (Math.abs(val) >= 1_000_000_000) {
      const scaled = val / 1_000_000_000;
      formattedNum = `${scaled.toLocaleString(undefined, { minimumFractionDigits: minDecimals, maximumFractionDigits: maxDecimals })}B`;
    } else if (Math.abs(val) >= 1_000_000) {
      const scaled = val / 1_000_000;
      formattedNum = `${scaled.toLocaleString(undefined, { minimumFractionDigits: minDecimals, maximumFractionDigits: maxDecimals })}M`;
    } else if (Math.abs(val) >= 1_000) {
      const scaled = val / 1_000;
      formattedNum = `${scaled.toLocaleString(undefined, { minimumFractionDigits: minDecimals, maximumFractionDigits: maxDecimals })}K`;
    } else {
      formattedNum = val.toLocaleString(undefined, {
        minimumFractionDigits: minDecimals,
        maximumFractionDigits: maxDecimals,
      });
    }
  } else {
    formattedNum = val.toLocaleString(undefined, {
      minimumFractionDigits: minDecimals,
      maximumFractionDigits: maxDecimals,
    });
  }

  if (type === 'currency') {
    return `${symbol}${formattedNum}`;
  }

  return formattedNum;
}

interface Props {
  widget: Widget;
}

export default function CounterWidget({ widget }: Props) {
  const { activeDashboard, filterState, paramState } = useDashboardStore();
  const cfg = widget.chartConfig;
  const dataset = activeDashboard?.datasets.find((d) => d.id === cfg?.datasetId);

  const { data: queryResult, isLoading } = useDatasetQuery(
    cfg?.datasetId,
    paramState as any,
    filterState as any,
    !!cfg?.datasetId,
    dataset?.sql
  );

  const { mainValue, compareValue, delta, deltaPercent, trend } = useMemo(() => {
    if (!queryResult || !cfg?.yFields?.[0]) {
      return { mainValue: null, compareValue: null, delta: null, deltaPercent: null, trend: null };
    }
    const rows = queryResult.rows;
    if (!rows || rows.length === 0) {
      return { mainValue: null, compareValue: null, delta: null, deltaPercent: null, trend: null };
    }

    const yField = cfg.yFields[0];
    const mainTransform = cfg.yAxis?.transform || 'NONE';
    const compTransform = cfg.comparisonTransform || mainTransform;

    // Compute main value using selected transformation across series rows
    const yVals = rows.map((r) => r[yField]);
    const main = aggregateValues(yVals, mainTransform);

    // Compute comparison value using transformation or comparison field
    let compare: number | null = null;
    if (cfg.comparisonField) {
      const compVals = rows.map((r) => r[cfg.comparisonField!]);
      compare = aggregateValues(compVals, compTransform);
    } else if (rows.length >= 2 && (mainTransform.toUpperCase() === 'NONE' || mainTransform.toUpperCase() === 'FIRST')) {
      compare = rows[1] && rows[1][yField] !== undefined ? aggregateValues([rows[1][yField]], 'NONE') : null;
    }

    const d = main !== null && compare !== null && !isNaN(main) && !isNaN(compare) ? main - compare : null;
    const dp = d !== null && compare ? (d / Math.abs(compare)) * 100 : null;
    const t = d !== null ? (d >= 0 ? 'up' : 'down') : null;

    return { mainValue: main, compareValue: compare, delta: d, deltaPercent: dp, trend: t };
  }, [queryResult, cfg]);

  if (isLoading) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-text-muted)',
          fontSize: '0.8rem',
        }}
      >
        Loading…
      </div>
    );
  }

  // Conditional formatting
  let valueColor = 'var(--color-text)';
  if (cfg?.conditionalFormatting && mainValue !== null && !isNaN(mainValue)) {
    for (const rule of cfg.conditionalFormatting) {
      const inMin = rule.min === undefined || mainValue >= rule.min;
      const inMax = rule.max === undefined || mainValue < rule.max;
      if (inMin && inMax) {
        valueColor = rule.color;
        break;
      }
    }
  }

  const showDelta = cfg?.showSparkline !== false && delta !== null && deltaPercent !== null;
  const label = cfg?.xField;

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        padding: 16,
      }}
    >
      {/* Main value + Unit */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'center',
          gap: 6,
          lineHeight: 1.1,
        }}
      >
        <span style={{ fontSize: '2.4rem', fontWeight: 700, color: valueColor }}>
          {mainValue !== null ? formatValue(mainValue, cfg?.numberFormat) : '—'}
        </span>
        {cfg?.numberFormat?.unit && (
          <span
            style={{
              fontSize: '1.25rem',
              fontWeight: 600,
              color: 'var(--color-text-muted)',
              letterSpacing: '0.2px',
            }}
          >
            {cfg.numberFormat.unit}
          </span>
        )}
      </div>

      {/* Delta & Trend indicator */}
      {showDelta && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: '0.78rem',
            color: trend === 'up' ? 'var(--color-success)' : 'var(--color-danger)',
          }}
        >
          {trend === 'up' ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          <span>
            {delta > 0 ? '+' : ''}
            {formatValue(delta, cfg?.numberFormat)} ({deltaPercent.toFixed(1)}%)
          </span>
        </div>
      )}

      {/* Label / Subtext */}
      {label && (
        <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
          {label}
        </div>
      )}
    </div>
  );
}
