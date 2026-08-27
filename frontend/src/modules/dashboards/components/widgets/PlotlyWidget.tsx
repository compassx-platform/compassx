/**
 * PlotlyWidget — renders all chart types via Plotly.
 * Reference screenshots: area/bar/box/bubble/choropleth/combo/funnel/heatmap/
 *   histogram/line/pie/point_map/sankey/scatter/waterfall charts.
 */

import { useRef, useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useDatasetQuery } from '@/modules/dashboards/hooks/useDashboard';
import { aggregateValues } from '@/modules/dashboards/utils/dataTransforms';
import type { AxisConfig, Widget, ChartConfig } from '@/types/dashboard';

// Lazy-load Plotly to keep initial bundle lighter
let Plotly: typeof import('plotly.js') | null = null;
async function getPlotly() {
  if (!Plotly) {
    Plotly = (await import('plotly.js')).default as any;
  }
  return Plotly!;
}

function applyDataTransforms(rows: Record<string, unknown>[], cfg: ChartConfig): Record<string, unknown>[] {
  const transform = cfg.yAxis?.transform || cfg.xAxis?.transform;
  if (!transform || transform.toUpperCase() === 'NONE') {
    return rows;
  }

  const { xField, yFields = [], colorField } = cfg;
  if (!xField) return rows;

  const groupMap = new Map<string, { xVal: unknown; colorVal?: unknown; rawRows: Record<string, unknown>[] }>();

  for (const row of rows) {
    const xVal = row[xField];
    const colorVal = colorField ? row[colorField] : undefined;
    const groupKey = `${String(xVal)}:::${String(colorVal ?? '')}`;

    if (!groupMap.has(groupKey)) {
      groupMap.set(groupKey, { xVal, colorVal, rawRows: [] });
    }
    groupMap.get(groupKey)!.rawRows.push(row);
  }

  const aggregatedRows: Record<string, unknown>[] = [];

  for (const group of groupMap.values()) {
    const newRow: Record<string, unknown> = {
      [xField]: group.xVal,
    };
    if (colorField && group.colorVal !== undefined) {
      newRow[colorField] = group.colorVal;
    }

    const allYFields = Array.from(new Set([
      ...(cfg.yFields ?? []),
      ...(cfg.y2Fields ?? []),
    ]));
    for (const yf of allYFields.length > 0 ? allYFields : ['value']) {
      const numericVals = group.rawRows.map((r) => Number(r[yf])).filter((v) => !isNaN(v));
      newRow[yf] = aggregateValues(numericVals, transform);
    }

    aggregatedRows.push(newRow);
  }

  return aggregatedRows;
}

function applySorting(rows: Record<string, unknown>[], cfg: ChartConfig): Record<string, unknown>[] {
  const isLineOrCombo = cfg.chartType === 'line' || cfg.chartType === 'area' || cfg.chartType === 'combo';
  const defaultSortOrder = isLineOrCombo ? 'asc' : undefined;

  const rawSortOrder = cfg.xAxis?.sortByOrder || cfg.yAxis?.sortByOrder || cfg.y2Axis?.sortByOrder;
  const sortOrder = rawSortOrder || (cfg.xAxis?.sortOrder === 'desc' ? 'desc' : (cfg.xAxis?.sortOrder === 'asc' || cfg.xAxis?.sortOrder === 'alpha' ? 'asc' : defaultSortOrder));

  const sortField = cfg.xAxis?.sortByField || cfg.yAxis?.sortByField || cfg.y2Axis?.sortByField || cfg.xField;

  if (!sortOrder || !sortField) return rows;

  return [...rows].sort((a, b) => {
    const valA = a[sortField];
    const valB = b[sortField];

    if (valA === valB) return 0;
    if (valA === null || valA === undefined) return 1;
    if (valB === null || valB === undefined) return -1;

    const numA = Number(valA);
    const numB = Number(valB);

    const isDateStrA = typeof valA === 'string' && /^\d{4}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4}|[A-Za-z]+\s+\d{4}/.test(valA.trim());
    const isDateStrB = typeof valB === 'string' && /^\d{4}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4}|[A-Za-z]+\s+\d{4}/.test(valB.trim());

    const dateA = isDateStrA ? Date.parse(valA) : NaN;
    const dateB = isDateStrB ? Date.parse(valB) : NaN;

    let comp = 0;
    if (!isNaN(dateA) && !isNaN(dateB)) {
      comp = dateA - dateB;
    } else if (!isNaN(numA) && !isNaN(numB)) {
      comp = numA - numB;
    } else {
      comp = String(valA).localeCompare(String(valB), undefined, { numeric: true, sensitivity: 'base' });
    }

    return sortOrder === 'desc' ? -comp : comp;
  });
}

function formatCompactNumber(num: number): string {
  if (num === null || num === undefined || isNaN(num)) return '0';
  const abs = Math.abs(num);
  if (abs >= 1e9) return (num / 1e9).toFixed(2).replace(/\.00$/, '') + 'B';
  if (abs >= 1e6) return (num / 1e6).toFixed(2).replace(/\.00$/, '') + 'M';
  if (abs >= 1e3) return (num / 1e3).toFixed(2).replace(/\.00$/, '') + 'K';
  if (Number.isInteger(num)) return num.toString();
  return num.toFixed(2).replace(/\.00$/, '');
}

function buildTooltipHtml(
  xVal: unknown,
  yVal: number,
  yFieldName: string,
  row: Record<string, unknown>,
  cfg: ChartConfig
): string {
  const transform = cfg.yAxis?.transform;
  const label = cfg.yAxis?.displayName || (transform && transform !== 'NONE' ? `${transform} of ${yFieldName}` : `Sum of ${yFieldName}`);
  const formattedY = formatCompactNumber(yVal);

  let html = `<div style="font-family:'Inter',system-ui,sans-serif;padding:4px 6px;min-width:150px;background:#ffffff;color:#0f172a;">`;
  html += `<div style="font-weight:700;font-size:12px;color:#0f172a;margin-bottom:6px;padding-bottom:3px">${String(xVal)}</div>`;

  // Primary Y field row
  html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:11px;line-height:1.6">`;
  html += `<span style="color:#64748b">${label}:</span>`;
  html += `<span style="font-weight:600;color:#0f172a">${formattedY}</span>`;
  html += `</div>`;

  // Additional Y fields if multiple
  if (cfg.yFields && cfg.yFields.length > 1) {
    for (const yf of cfg.yFields.slice(1)) {
      const val = Number(row[yf]);
      const formatted = !isNaN(val) ? formatCompactNumber(val) : String(row[yf] ?? '');
      const yfLabel = transform && transform !== 'NONE' ? `${transform} of ${yf}` : `Sum of ${yf}`;
      html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:11px;line-height:1.6">`;
      html += `<span style="color:#64748b">${yfLabel}:</span>`;
      html += `<span style="font-weight:600;color:#0f172a">${formatted}</span>`;
      html += `</div>`;
    }
  }

  // Tooltip fields if configured
  if (cfg.tooltipFields && cfg.tooltipFields.length > 0) {
    for (const tf of cfg.tooltipFields) {
      const tfVal = Number(row[tf]);
      const formatted = !isNaN(tfVal) ? formatCompactNumber(tfVal) : String(row[tf] ?? '');
      html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:11px;line-height:1.6">`;
      html += `<span style="color:#64748b">${tf}:</span>`;
      html += `<span style="font-weight:600;color:#0f172a">${formatted}</span>`;
      html += `</div>`;
    }
  }

  html += `</div>`;
  return html;
}

const PRESET_COLORS = [
  '#1B6EF3', '#10B981', '#8B5CF6', '#F59E0B', '#EF4444',
  '#06B6D4', '#EC4899', '#64748B', '#F97316', '#14B8A6'
];

function getSeriesColor(field: string, index: number, cfg: ChartConfig): string {
  if (cfg.seriesColors && cfg.seriesColors.length > 0) {
    const found = cfg.seriesColors.find(
      (sc) => sc.field === field || sc.field.toLowerCase() === field.toLowerCase()
    );
    if (found?.color) return found.color;
    if (cfg.seriesColors[index]?.color) return cfg.seriesColors[index].color;
    if (cfg.seriesColors[0]?.color) return cfg.seriesColors[0].color;
  }
  return PRESET_COLORS[index % PRESET_COLORS.length];
}

function getSeriesTitle(field: string, cfg: ChartConfig): string {
  const found = cfg.seriesTitles?.find((st) => st.field === field);
  if (found?.title) return found.title;
  return field;
}

function buildTraces(rows: Record<string, unknown>[], cfg: ChartConfig): Partial<Plotly.Data>[] {
  const { chartType, xField, yFields = [], colorField, sizeField, y2Fields = [] } = cfg;

  if (!xField && chartType !== 'sankey' && chartType !== 'funnel') return [];

  const xValues = rows.map((r) => r[xField!]);

  switch (chartType) {
    case 'bar':
      return (yFields.length > 0 ? yFields : ['value']).map((yf, idx) => ({
        type: 'bar',
        x: xValues,
        y: rows.map((r) => r[yf]),
        name: getSeriesTitle(yf, cfg),
        hoverinfo: 'none',
        marker: { color: getSeriesColor(yf, idx, cfg) },
        ...(cfg.layout === 'stack' ? { stackgroup: 'one' } : {}),
        ...(cfg.showValueLabels ? { texttemplate: '%{y}', textposition: 'auto' } : {}),
      } as any));

    case 'line':
    case 'area':
      return (yFields.length > 0 ? yFields : ['value']).map((yf, idx) => ({
        type: 'scatter',
        mode: cfg.showValueLabels ? 'lines+markers+text' : 'lines+markers',
        x: xValues,
        y: rows.map((r) => r[yf]),
        name: getSeriesTitle(yf, cfg),
        hoverinfo: 'none',
        line: { color: getSeriesColor(yf, idx, cfg), width: cfg.lineThickness || 2 },
        marker: { color: getSeriesColor(yf, idx, cfg) },
        ...(cfg.showValueLabels ? { texttemplate: '%{y}', textposition: 'top center' } : {}),
        ...(chartType === 'area' ? { fill: 'tozeroy' } : {}),
        ...(cfg.layout === 'stack' ? { stackgroup: 'one' } : {}),
      } as any));

    case 'scatter':
      return [{
        type: 'scatter',
        mode: 'markers',
        x: xValues,
        y: rows.map((r) => r[yFields[0] ?? 'y']),
        marker: {
          color: colorField ? rows.map((r) => String(r[colorField])) : getSeriesColor(yFields[0] ?? 'y', 0, cfg),
          size: sizeField ? rows.map((r) => Number(r[sizeField]) / 5) : 8,
        },
      } as any];

    case 'bubble':
      return [{
        type: 'scatter',
        mode: 'markers',
        x: xValues,
        y: rows.map((r) => r[yFields[0] ?? 'y']),
        marker: {
          size: sizeField ? rows.map((r) => Number(r[sizeField]) / 5) : 12,
          color: colorField ? rows.map((r) => String(r[colorField])) : getSeriesColor(yFields[0] ?? 'y', 0, cfg),
          sizemode: 'area',
        },
      } as any];

    case 'pie':
      return [{
        type: 'pie',
        labels: xValues,
        values: rows.map((r) => r[yFields[0] ?? 'value']),
      } as any];

    case 'heatmap':
      return [{
        type: 'heatmap',
        x: xValues,
        y: rows.map((r) => r[yFields[0] ?? 'y']),
        z: rows.map((r) => r[yFields[1] ?? 'value']),
        colorscale: 'Blues',
      } as any];

    case 'histogram':
      return [{
        type: 'histogram',
        x: xValues,
        nbinsx: 20,
      } as any];

    case 'box':
      return (yFields.length > 0 ? yFields : ['value']).map((yf) => ({
        type: 'box',
        y: rows.map((r) => r[yf]),
        x: colorField ? rows.map((r) => r[colorField]) : undefined,
        name: yf,
        boxpoints: 'outliers',
      } as any));

    case 'funnel':
      return [{
        type: 'funnel',
        y: xValues,
        x: rows.map((r) => r[yFields[0] ?? 'value']),
      } as any];

    case 'waterfall':
      return [{
        type: 'waterfall',
        x: xValues,
        y: rows.map((r) => r[yFields[0] ?? 'value']),
        connector: { line: { color: 'var(--color-border)' } },
      } as any];

    case 'sankey': {
      const sourceField = xField ?? 'source';
      const targetField = yFields[0] ?? 'target';
      const valueField = yFields[1] ?? 'value';
      const nodes = Array.from(new Set([
        ...rows.map((r) => String(r[sourceField])),
        ...rows.map((r) => String(r[targetField])),
      ]));
      const nodeIndex = Object.fromEntries(nodes.map((n, i) => [n, i]));
      return [{
        type: 'sankey',
        node: { label: nodes, pad: 10, thickness: 20 },
        link: {
          source: rows.map((r) => nodeIndex[String(r[sourceField])]),
          target: rows.map((r) => nodeIndex[String(r[targetField])]),
          value: rows.map((r) => Number(r[valueField])),
        },
      } as any];
    }

    case 'combo':
      return [
        ...(yFields.length > 0 ? yFields : ['value']).map((yf, idx) => ({
          type: 'bar',
          x: xValues,
          y: rows.map((r) => r[yf]),
          name: getSeriesTitle(yf, cfg),
          hoverinfo: 'none',
          marker: { color: getSeriesColor(yf, idx, cfg) },
          ...(cfg.showValueLabels ? { texttemplate: '%{y}', textposition: 'auto' } : {}),
        } as any)),
        ...y2Fields.map((yf, idx) => ({
          type: 'scatter',
          mode: cfg.showValueLabels ? 'lines+markers+text' : 'lines+markers',
          x: xValues,
          y: rows.map((r) => r[yf]),
          name: getSeriesTitle(yf, cfg),
          hoverinfo: 'none',
          yaxis: 'y2',
          line: { color: getSeriesColor(yf, idx + yFields.length, cfg), width: cfg.lineThickness || 2 },
          marker: { color: getSeriesColor(yf, idx + yFields.length, cfg) },
          ...(cfg.showValueLabels ? { texttemplate: '%{y}', textposition: 'top center' } : {}),
        } as any)),
      ];

    case 'choropleth':
      return [{
        type: 'choropleth',
        locations: xValues as string[],
        z: rows.map((r) => r[yFields[0] ?? 'value']),
        locationmode: 'country names',
        colorscale: 'Blues',
      } as any];

    case 'point_map':
      return [{
        type: 'scattergeo',
        lat: rows.map((r) => r[cfg.latField ?? 'lat']),
        lon: rows.map((r) => r[cfg.lonField ?? 'lon']),
        mode: 'markers',
        marker: {
          size: sizeField ? rows.map((r) => Number(r[sizeField]) / 5) : 8,
          color: colorField ? rows.map((r) => r[colorField]) : '#1B6EF3',
        },
      } as any];

    default:
      return [];
  }
}

function getAxisRange(
  axisConfig?: AxisConfig,
  rows?: Record<string, unknown>[],
  fields?: string[]
): { autorange: boolean | 'reversed'; range?: [number, number] } {
  if (!axisConfig) return { autorange: true };

  const { min, max, reversed } = axisConfig;
  const hasMin = min !== undefined && min !== null && !isNaN(min);
  const hasMax = max !== undefined && max !== null && !isNaN(max);

  if (!hasMin && !hasMax) {
    return { autorange: reversed ? 'reversed' : true };
  }

  let finalMin = hasMin ? Number(min) : 0;
  let finalMax = hasMax ? Number(max) : 100;

  if (rows && rows.length > 0 && fields && fields.length > 0) {
    const allVals: number[] = [];
    for (const r of rows) {
      for (const f of fields) {
        const v = Number(r[f]);
        if (!isNaN(v)) allVals.push(v);
      }
    }
    if (allVals.length > 0) {
      const dataMin = Math.min(...allVals);
      const dataMax = Math.max(...allVals);
      const span = dataMax - dataMin || Math.abs(dataMax) || 1;

      if (!hasMin) {
        finalMin = dataMin < 0 ? dataMin - span * 0.05 : 0;
      }
      if (!hasMax) {
        finalMax = dataMax + span * 0.05;
      }
    }
  }

  if (finalMin >= finalMax) {
    finalMax = finalMin + 1;
  }

  if (reversed) {
    return { autorange: false, range: [finalMax, finalMin] };
  }

  return { autorange: false, range: [finalMin, finalMax] };
}

function buildLayout(cfg: ChartConfig, rows?: Record<string, unknown>[]): Partial<Plotly.Layout> {
  const legendPos = cfg.legend?.position ?? 'bottom';
  const legendLayout = {
    showlegend: cfg.legend?.show !== false,
    legend: {
      orientation: (legendPos === 'top' || legendPos === 'bottom' ? 'h' : 'v') as 'h' | 'v',
      x: legendPos === 'right' ? 1.02 : (legendPos === 'left' ? -0.18 : 0.5),
      xanchor: (legendPos === 'top' || legendPos === 'bottom' ? 'center' : (legendPos === 'right' ? 'left' : 'right')) as any,
      y: legendPos === 'top' ? 1.08 : (legendPos === 'bottom' ? -0.12 : 0.5),
      yanchor: (legendPos === 'top' ? 'bottom' : (legendPos === 'bottom' ? 'top' : 'middle')) as any,
    },
  };

  let yTickFormat: string | undefined = undefined;
  let yTickPrefix: string | undefined = undefined;
  let yTickSuffix: string | undefined = undefined;

  if (cfg.numberFormat) {
    if (cfg.numberFormat.type === 'currency') yTickPrefix = cfg.numberFormat.currencySymbol || '$';
    if (cfg.numberFormat.type === 'percent') yTickSuffix = '%';
    if (cfg.numberFormat.abbreviation === 'compact') yTickFormat = '.2s';
    if (cfg.numberFormat.abbreviation === 'scientific') yTickFormat = '.2e';
  }

  const yFields = cfg.yFields && cfg.yFields.length > 0 ? cfg.yFields : ['value'];
  const yRangeOpts = getAxisRange(cfg.yAxis, rows, yFields);
  const xFields = cfg.xField ? [cfg.xField] : [];
  const xRangeOpts = getAxisRange(cfg.xAxis, rows, xFields);

  const isXCategory = cfg.xAxis?.scaleType === 'categorical' ||
    (rows && rows.length > 0 && typeof rows[0][cfg.xField ?? ''] === 'string') ||
    cfg.xAxis?.scaleType !== 'continuous';

  const xCategoryStep = isXCategory && cfg.xAxis?.tickCount && rows && rows.length > 0
    ? Math.max(1, Math.ceil(rows.length / cfg.xAxis.tickCount))
    : undefined;

  const base: Partial<Plotly.Layout> = {
    autosize: true,
    margin: {
      t: legendPos === 'top' ? 30 : 16,
      b: legendPos === 'bottom' ? (cfg.xAxis?.labelAngle ? 45 : 30) : 22,
      l: 45,
      r: cfg.y2Fields && cfg.y2Fields.length > 0 ? 45 : 18,
    },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { family: 'Inter, system-ui, sans-serif', size: 11 },
    hovermode: 'closest',
    hoverlabel: {
      bgcolor: '#ffffff',
      bordercolor: '#e2e8f0',
      font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#0f172a' },
      align: 'left',
      namelength: -1,
    } as any,
    ...legendLayout,
    xaxis: {
      title: (cfg.xAxis?.showTitle !== false ? (cfg.xAxis?.displayName ?? cfg.xAxis?.title) : undefined) as any,
      showticklabels: cfg.xAxis?.showValues !== false,
      autorange: xRangeOpts.autorange,
      ...(xRangeOpts.range ? { range: xRangeOpts.range } : {}),
      ...(cfg.xAxis?.labelAngle !== undefined ? { tickangle: cfg.xAxis.labelAngle } : {}),
      ...(isXCategory ? { dtick: xCategoryStep ?? 1, tickmode: 'linear' } : (cfg.xAxis?.tickCount ? { nticks: cfg.xAxis.tickCount } : {})),
      type: isXCategory ? 'category' : (cfg.xAxis?.scaleType === 'continuous' ? 'linear' : (cfg.xAxis?.logScale ? 'log' : undefined)),
      showgrid: cfg.showGridlines !== false,
      gridcolor: '#E0E0E0',
      zeroline: false,
    },
    yaxis: {
      title: (cfg.yAxis?.showTitle !== false ? (cfg.yAxis?.displayName ?? cfg.yAxis?.title) : undefined) as any,
      showticklabels: cfg.yAxis?.showValues !== false,
      autorange: yRangeOpts.autorange,
      ...(yRangeOpts.range ? { range: yRangeOpts.range } : {}),
      ...(cfg.yAxis?.labelAngle !== undefined ? { tickangle: cfg.yAxis.labelAngle } : {}),
      ...(cfg.yAxis?.tickCount ? { nticks: cfg.yAxis.tickCount } : {}),
      type: cfg.yAxis?.scaleType === 'categorical' ? 'category' : (cfg.yAxis?.scaleType === 'continuous' ? 'linear' : (cfg.yAxis?.logScale ? 'log' : undefined)),
      showgrid: cfg.showGridlines !== false,
      gridcolor: '#E0E0E0',
      zeroline: false,
      tickformat: yTickFormat,
      tickprefix: yTickPrefix,
      ticksuffix: yTickSuffix,
    },
  };

  if (cfg.y2Fields && cfg.y2Fields.length > 0) {
    const y2RangeOpts = getAxisRange(cfg.y2Axis, rows, cfg.y2Fields);
    (base as any).yaxis2 = {
      overlaying: 'y',
      side: 'right',
      title: (cfg.y2Axis?.showTitle !== false ? (cfg.y2Axis?.displayName ?? cfg.y2Axis?.title) : undefined) as any,
      showgrid: false,
      zeroline: false,
      autorange: y2RangeOpts.autorange,
      ...(y2RangeOpts.range ? { range: y2RangeOpts.range } : {}),
      ...(cfg.y2Axis?.tickCount ? { nticks: cfg.y2Axis.tickCount } : {}),
      tickformat: yTickFormat,
      tickprefix: yTickPrefix,
      ticksuffix: yTickSuffix,
    };
  }

  if (cfg.chartType === 'choropleth' || cfg.chartType === 'point_map') {
    (base as any).geo = { showframe: false, showcoastlines: true };
  }

  // Annotations
  if (cfg.annotations && cfg.annotations.length > 0) {
    base.shapes = cfg.annotations.map((ann) => ({
      type: 'line',
      ...(ann.axis === 'x'
        ? { x0: ann.value, x1: ann.value, y0: 0, y1: 1, yref: 'paper' }
        : { y0: ann.value, y1: ann.value, x0: 0, x1: 1, xref: 'paper' }),
      line: { color: ann.color ?? '#666', dash: 'dot', width: 1.5 },
    })) as any;
  }

  return base;
}

interface Props {
  widget: Widget;
}

interface CustomTooltipState {
  x: number;
  y: number;
  header: string;
  items: { label: string; value: string }[];
}

export default function PlotlyWidget({ widget }: Props) {
  const plotRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { activeDashboard, filterState, paramState, setFilterValue } = useDashboardStore();
  const [tooltipState, setTooltipState] = useState<CustomTooltipState | null>(null);
  const [selectedSwitcherField, setSelectedSwitcherField] = useState<string | null>(null);

  const cfg = useMemo(() => {
    if (!widget.chartConfig) return undefined;
    const raw = widget.chartConfig as any;
    return {
      ...raw,
      chartType: raw.chartType ?? raw.chart_type ?? 'bar',
      datasetId: raw.datasetId ?? raw.dataset_id,
      xField: raw.xField ?? raw.x_field,
      yFields: Array.isArray(raw.yFields)
        ? raw.yFields
        : Array.isArray(raw.y_fields)
        ? raw.y_fields
        : raw.yField || raw.y_field
        ? [raw.yField || raw.y_field]
        : [],
      colorField: raw.colorField ?? raw.color_field,
      sizeField: raw.sizeField ?? raw.size_field,
      y2Fields: raw.y2Fields ?? raw.y2_fields,
      showGridlines: raw.showGridlines ?? raw.show_gridlines,
      seriesColors: raw.seriesColors ?? raw.series_colors ?? [],
      enableSeriesSwitcher: raw.enableSeriesSwitcher ?? raw.enable_series_switcher,
    } as ChartConfig;
  }, [widget.chartConfig]);

  const dataset = activeDashboard?.datasets.find((d) => d.id === cfg?.datasetId);

  const activeSwitcherField = (cfg?.enableSeriesSwitcher && (cfg?.yFields ?? []).length > 1)
    ? (selectedSwitcherField && cfg?.yFields?.includes(selectedSwitcherField) ? selectedSwitcherField : cfg?.yFields?.[0])
    : null;

  const effectiveCfg = useMemo(() => {
    if (!cfg) return undefined;
    if (activeSwitcherField) {
      return {
        ...cfg,
        yFields: [activeSwitcherField],
      };
    }
    return cfg;
  }, [cfg, activeSwitcherField]);

  function stopDragPropagation(e: React.MouseEvent | React.TouchEvent) {
    e.stopPropagation();
  }

  const resolvedParams = useMemo(() => ({ ...paramState }), [paramState]);

  const { data: queryResult, isLoading, error } = useDatasetQuery(
    cfg?.datasetId,
    resolvedParams as any,
    filterState as any,
    !!cfg?.datasetId,
    dataset?.sql
  );

  useEffect(() => {
    if (!plotRef.current || !effectiveCfg || !queryResult) return;
    let cancelled = false;

    getPlotly().then((P) => {
      if (cancelled || !plotRef.current) return;
      const transformedRows = applyDataTransforms(queryResult.rows, effectiveCfg);
      const processedRows = applySorting(transformedRows, effectiveCfg);
      const rawTraces = buildTraces(processedRows, effectiveCfg);
      const traces = rawTraces.map((t) => ({ ...t, hoverinfo: 'none', hovertemplate: '' }));
      const layout = buildLayout(effectiveCfg, processedRows);
      P.react(plotRef.current, traces as any, layout as any, {
        responsive: true,
        displaylogo: false,
        displayModeBar: false,
        scrollZoom: true,
      }).then(() => {
        if (!cancelled && plotRef.current) {
          P.Plots.resize(plotRef.current);
        }
      });

      // Tooltip hover listener
      (plotRef.current as any).on('plotly_hover', (event: any) => {
        const pt = event?.points?.[0];
        if (!pt || !cfg) return;

        const xVal = pt.x ?? pt.label ?? '';
        const ptIndex = pt.pointIndex ?? 0;
        const row = processedRows[ptIndex] ?? {};

        const transform = cfg.yAxis?.transform;
        const items: { label: string; value: string }[] = [];

        const allHoverYFields = Array.from(new Set([...(cfg.yFields ?? []), ...(cfg.y2Fields ?? [])]));
        const yFs = allHoverYFields.length > 0 ? allHoverYFields : ['value'];
        for (const yf of yFs) {
          const val = Number(row[yf] ?? pt.y);
          const formatted = !isNaN(val) ? formatCompactNumber(val) : String(row[yf] ?? pt.y ?? '');
          const seriesTitleVal = cfg.seriesTitles?.find((st) => st.field === yf)?.title;
          const isY2 = (cfg.y2Fields ?? []).includes(yf);
          const axisTransform = isY2 ? cfg.y2Axis?.transform : cfg.yAxis?.transform;
          const axisName = isY2 ? cfg.y2Axis?.displayName : cfg.yAxis?.displayName;
          const label = seriesTitleVal || axisName || (axisTransform && axisTransform !== 'NONE' ? `${axisTransform} of ${yf}` : yf);
          items.push({ label, value: formatted });
        }

        if (cfg.tooltipFields && cfg.tooltipFields.length > 0) {
          for (const tf of cfg.tooltipFields) {
            const tfVal = Number(row[tf]);
            const formatted = !isNaN(tfVal) ? formatCompactNumber(tfVal) : String(row[tf] ?? '');
            items.push({ label: `${tf}`, value: formatted });
          }
        }

        if (containerRef.current) {
          const rect = containerRef.current.getBoundingClientRect();
          const mouseEvt = event.event;
          const mouseX = (mouseEvt?.clientX ?? 0) - rect.left + 12;
          const mouseY = (mouseEvt?.clientY ?? 0) - rect.top - 12;

          setTooltipState({
            x: Math.min(mouseX, Math.max(10, rect.width - 180)),
            y: Math.max(10, Math.min(mouseY, rect.height - 100)),
            header: String(xVal),
            items,
          });
        }
      });

      (plotRef.current as any).on('plotly_unhover', () => {
        setTooltipState(null);
      });

      // Cross-filtering: click handler
      (plotRef.current as any).on('plotly_click', (event: any) => {
        const pt = event?.points?.[0];
        if (!pt || !widget.chartConfig?.xField) return;
        setFilterValue(`cross_${widget.id}`, pt.x ?? pt.label ?? null);
      });
    });

    return () => { cancelled = true; };
  }, [effectiveCfg, queryResult]);

  // ResizeObserver to automatically resize chart when widget or sidebar size changes
  useEffect(() => {
    if (!plotRef.current) return;
    const el = plotRef.current;
    const parent = el.parentElement;
    let frameId: number | null = null;

    const doResize = () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      frameId = requestAnimationFrame(() => {
        if (el && ((el as any)._fullLayout || (el as any).layout || el.querySelector('.svg-container'))) {
          getPlotly().then((P) => {
            P.Plots.resize(el);
          });
        }
      });
    };

    const observer = new ResizeObserver(doResize);
    observer.observe(el);
    if (parent) observer.observe(parent);

    return () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, []);

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!tooltipState || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left + 15;
    const mouseY = e.clientY - rect.top - 15;

    setTooltipState((prev) =>
      prev
        ? {
            ...prev,
            x: Math.min(mouseX, Math.max(10, rect.width - 185)),
            y: Math.max(10, Math.min(mouseY, rect.height - 110)),
          }
        : null
    );
  }

  if (!cfg) return null;

  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
        <Loader2 size={15} className="spin" /> Loading…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-danger)', fontSize: '0.78rem', padding: 12 }}>
        Query error
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
      onMouseDown={stopDragPropagation}
      onTouchStart={stopDragPropagation}
      onPointerDown={stopDragPropagation as any}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setTooltipState(null)}
    >
      {cfg?.enableSeriesSwitcher && (cfg.yFields ?? []).length > 1 && (
        <div
          className="widget-content-interactive"
          onMouseDown={stopDragPropagation}
          onTouchStart={stopDragPropagation}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 8px',
            background: '#f8fafc',
            borderBottom: '1px solid #e2e8f0',
            overflowX: 'auto',
            flexShrink: 0,
          }}
        >
          {(cfg.yFields ?? []).map((field, idx) => {
            const isActive = (activeSwitcherField ?? cfg.yFields![0]) === field;
            const seriesColor = getSeriesColor(field, idx, cfg);
            return (
              <button
                key={field}
                type="button"
                onClick={() => setSelectedSwitcherField(field)}
                style={{
                  padding: '2px 9px',
                  fontSize: '0.71rem',
                  fontWeight: isActive ? 600 : 400,
                  borderRadius: 12,
                  border: isActive ? `1.5px solid ${seriesColor}` : '1px solid #cbd5e1',
                  background: isActive ? `${seriesColor}15` : '#ffffff',
                  color: isActive ? seriesColor : '#475569',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: seriesColor }} />
                {getSeriesTitle(field, cfg)}
              </button>
            );
          })}
        </div>
      )}

      <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%', minHeight: 0 }}>
        <div
          ref={plotRef}
          className="widget-content-interactive"
          style={{ width: '100%', height: '100%', overflow: 'hidden', minWidth: 0, minHeight: 0 }}
        />
      </div>
      {tooltipState && (
        <div
          style={{
            position: 'absolute',
            left: tooltipState.x,
            top: tooltipState.y,
            background: '#ffffff',
            border: '1px solid #cbd5e1',
            borderRadius: 6,
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.08)',
            padding: '8px 12px',
            pointerEvents: 'none',
            zIndex: 1000,
            minWidth: 160,
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#0f172a', borderBottom: '1px solid #f1f5f9', paddingBottom: 4, marginBottom: 2 }}>
            {tooltipState.header}
          </div>
          {tooltipState.items.map((item: { label: string; value: string }, idx: number) => (
            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, fontSize: '0.75rem', lineHeight: 1.5 }}>
              <span style={{ color: '#64748b' }}>{item.label}:</span>
              <span style={{ fontWeight: 600, color: '#0f172a', fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}>{item.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

