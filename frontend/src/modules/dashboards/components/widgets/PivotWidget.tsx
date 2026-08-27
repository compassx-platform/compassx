/**
 * PivotWidget — cross-tabular aggregation with row/col/value fields.
 * Reference: pivot-ad5c969da7334a2a641e43c3bd6f4aaf.png
 *            cohort-ef6006c4bf9526a7db26722839b29aaa.png (color scale cells)
 */

import { useMemo } from 'react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useDatasetQuery } from '@/modules/dashboards/hooks/useDashboard';
import type { Widget } from '@/types/dashboard';

interface Props {
  widget: Widget;
}

export default function PivotWidget({ widget }: Props) {
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

  const { rowField, colField, valField } = useMemo(() => ({
    rowField: cfg?.xField ?? '',
    colField: cfg?.colorField ?? '',
    valField: cfg?.yFields?.[0] ?? '',
  }), [cfg]);

  const { rowKeys, colKeys, pivotMap, maxVal } = useMemo(() => {
    if (!queryResult || !rowField || !colField || !valField) {
      return { rowKeys: [], colKeys: [], pivotMap: {}, maxVal: 1 };
    }
    const rows = queryResult.rows;
    const rks = Array.from(new Set(rows.map((r) => String(r[rowField]))));
    const cks = Array.from(new Set(rows.map((r) => String(r[colField]))));
    const map: Record<string, Record<string, number>> = {};
    let max = 0;
    for (const row of rows) {
      const r = String(row[rowField]);
      const c = String(row[colField]);
      const v = Number(row[valField]) || 0;
      if (!map[r]) map[r] = {};
      map[r][c] = (map[r][c] ?? 0) + v;
      if (map[r][c] > max) max = map[r][c];
    }
    return { rowKeys: rks, colKeys: cks, pivotMap: map, maxVal: max || 1 };
  }, [queryResult, rowField, colField, valField]);

  if (isLoading) {
    return <div style={{ padding: 16, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Loading…</div>;
  }

  if (!queryResult || rowKeys.length === 0) {
    return <div style={{ padding: 16, fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>No pivot data. Configure row, column, value fields.</div>;
  }

  function cellColor(val: number): string {
    const ratio = val / maxVal;
    const r = Math.round(235 - ratio * (235 - 27));
    const g = Math.round(244 - ratio * (244 - 110));
    const b = Math.round(255 - ratio * (255 - 243));
    return `rgb(${r},${g},${b})`;
  }

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', fontSize: '0.75rem' }}>
        <thead style={{ position: 'sticky', top: 0, background: 'var(--color-surface)', zIndex: 1 }}>
          <tr>
            <th style={{ padding: '4px 10px', borderBottom: '2px solid var(--color-border)', borderRight: '1px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              {rowField}
            </th>
            {colKeys.map((ck) => (
              <th key={ck} style={{ padding: '4px 10px', borderBottom: '2px solid var(--color-border)', textAlign: 'center', color: 'var(--color-text-muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                {ck}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rowKeys.map((rk) => (
            <tr key={rk}>
              <td style={{ padding: '3px 10px', borderBottom: '1px solid var(--color-border)', borderRight: '1px solid var(--color-border)', fontWeight: 500, whiteSpace: 'nowrap' }}>
                {rk}
              </td>
              {colKeys.map((ck) => {
                const val = pivotMap[rk]?.[ck] ?? 0;
                return (
                  <td key={ck} style={{
                    padding: '3px 10px',
                    textAlign: 'center',
                    borderBottom: '1px solid var(--color-border)',
                    background: val > 0 ? cellColor(val) : undefined,
                    color: val / maxVal > 0.6 ? '#fff' : 'var(--color-text)',
                  }}>
                    {val > 0 ? val.toLocaleString() : ''}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

