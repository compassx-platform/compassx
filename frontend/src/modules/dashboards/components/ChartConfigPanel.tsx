/**
 * ChartConfigPanel — right-side configuration panel for dashboard widgets.
 * Follows SOLID principles with modular, registry-driven visualization configuration sections.
 */

import { useState } from 'react';
import {
  X, BarChart2, LineChart, PieChart, ScatterChart, Table2,
  MoreVertical
} from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import type { ChartType, Widget } from '@/types/dashboard';
import DashboardSidePanel from './DashboardSidePanel';
import SectionRow from './config/common/SectionRow';
import Select from './config/common/Select';
import HtmlConfigSection from './config/sections/HtmlConfigSection';
import { getVisualizationConfigComponent } from './config/vizConfigRegistry';

const CHART_TYPES: { type: ChartType; label: string }[] = [
  { type: 'bar', label: 'Bar' },
  { type: 'line', label: 'Line' },
  { type: 'area', label: 'Area' },
  { type: 'scatter', label: 'Scatter' },
  { type: 'pie', label: 'Pie' },
  { type: 'counter', label: 'Counter' },
  { type: 'table', label: 'Table' },
  { type: 'pivot', label: 'Pivot' },
  { type: 'heatmap', label: 'Heatmap' },
  { type: 'histogram', label: 'Histogram' },
  { type: 'box', label: 'Box' },
  { type: 'funnel', label: 'Funnel' },
  { type: 'waterfall', label: 'Waterfall' },
  { type: 'combo', label: 'Combo' },
  { type: 'bubble', label: 'Bubble' },
  { type: 'sankey', label: 'Sankey' },
  { type: 'choropleth', label: 'Map' },
  { type: 'point_map', label: 'Point Map' },
  { type: 'cohort', label: 'Cohort' },
];

function getChartIcon(type: ChartType) {
  const size = 13;
  switch (type) {
    case 'bar':
    case 'histogram':
    case 'waterfall':
    case 'combo':
      return <BarChart2 size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'line':
    case 'area':
      return <LineChart size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'pie':
    case 'funnel':
      return <PieChart size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'scatter':
    case 'bubble':
      return <ScatterChart size={size} style={{ color: 'var(--color-primary)' }} />;
    case 'table':
    case 'pivot':
      return <Table2 size={size} style={{ color: 'var(--color-primary)' }} />;
    default:
      return <BarChart2 size={size} style={{ color: 'var(--color-primary)' }} />;
  }
}

interface Props {
  onClose: () => void;
}

export default function ChartConfigPanel({ onClose }: Props) {
  const { activeDashboard, selectedWidgetId, updateWidget, cloneWidget, deleteWidget } = useDashboardStore();

  const [showTitleInput, setShowTitleInput] = useState(true);
  const [showDescInput, setShowDescInput] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showWidgetMenu, setShowWidgetMenu] = useState(false);

  const widget: Widget | undefined = activeDashboard?.widgets.find((w) => w.id === selectedWidgetId);
  if (!widget) {
    return (
      <DashboardSidePanel style={{ alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Select a widget to configure
        </span>
      </DashboardSidePanel>
    );
  }

  const datasetOptions = (activeDashboard?.datasets ?? []).map((d) => ({ value: d.id, label: d.name }));

  if (widget.widgetType === 'html') {
    return (
      <DashboardSidePanel>
        <HtmlConfigSection
          widget={widget}
          datasetOptions={datasetOptions}
          updateWidget={updateWidget}
          onClose={onClose}
        />
      </DashboardSidePanel>
    );
  }

  if (!widget.chartConfig) {
    return (
      <DashboardSidePanel style={{ alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Select a widget to configure
        </span>
      </DashboardSidePanel>
    );
  }

  const cfg = widget.chartConfig;
  const dataset = activeDashboard?.datasets.find((d) => d.id === cfg.datasetId);
  const fieldOptions = (dataset?.schema ?? []).map((f) => ({ value: f.name, label: f.name }));

  function patch(p: Partial<typeof cfg>) {
    const currentWidget = useDashboardStore.getState().activeDashboard?.widgets.find((w) => w.id === widget!.id);
    const currentCfg = currentWidget?.chartConfig ?? cfg;
    updateWidget(widget!.id, { chartConfig: { ...currentCfg, ...p } as typeof cfg });
  }

  function patchAxis(axis: 'xAxis' | 'yAxis' | 'y2Axis', p: Record<string, unknown>) {
    const currentWidget = useDashboardStore.getState().activeDashboard?.widgets.find((w) => w.id === widget!.id);
    const currentCfg = currentWidget?.chartConfig ?? cfg;
    updateWidget(widget!.id, {
      chartConfig: {
        ...currentCfg,
        [axis]: {
          ...(currentCfg as any)[axis],
          ...p,
        },
      } as typeof cfg,
    });
  }

  function getFieldType(fieldName: string): string {
    const field = dataset?.schema.find((f) => f.name === fieldName);
    return field?.type || 'string';
  }

  // Get modular configuration component from registry
  const ConfigComponent = getVisualizationConfigComponent(cfg.chartType);

  return (
    <DashboardSidePanel>
      {/* Scrollable Container */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>

        {/* Widget Header Section */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1a1a1a' }}>Widget</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }}>
              <button
                type="button"
                className="btn-icon"
                onClick={() => setShowWidgetMenu(!showWidgetMenu)}
                title="Widget actions"
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                <MoreVertical size={13} />
              </button>
              {showWidgetMenu && (
                <>
                  <div style={{ position: 'fixed', inset: 0, zIndex: 998 }} onClick={() => setShowWidgetMenu(false)} />
                  <div
                    style={{
                      position: 'absolute',
                      top: 24,
                      right: 20,
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: 6,
                      boxShadow: '0 4px 14px rgba(0,0,0,0.15)',
                      zIndex: 999,
                      width: 150,
                      padding: '4px 0',
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '6px 12px',
                        fontSize: '0.76rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        color: '#1e293b',
                      }}
                      onClick={() => {
                        setShowWidgetMenu(false);
                        cloneWidget(widget.id);
                      }}
                    >
                      📋 Duplicate widget
                    </button>
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '6px 12px',
                        fontSize: '0.76rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        color: '#1e293b',
                      }}
                      onClick={() => {
                        setShowWidgetMenu(false);
                        if (widget.chartConfig) {
                          updateWidget(widget.id, {
                            chartConfig: {
                              chartType: widget.chartConfig.chartType,
                              datasetId: widget.chartConfig.datasetId,
                            },
                          });
                        }
                      }}
                    >
                      🔄 Reset config
                    </button>
                    <div style={{ height: 1, background: '#e2e8f0', margin: '4px 0' }} />
                    <button
                      type="button"
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '6px 12px',
                        fontSize: '0.76rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        color: '#dc2626',
                        fontWeight: 500,
                      }}
                      onClick={() => {
                        setShowWidgetMenu(false);
                        if (confirm('Delete this widget?')) {
                          deleteWidget(widget.id);
                          onClose();
                        }
                      }}
                    >
                      🗑️ Delete widget
                    </button>
                  </div>
                </>
              )}
              <button
                type="button"
                className="btn-icon"
                onClick={onClose}
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                <X size={14} />
              </button>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
            <label style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#172b4d' }}>
              <input
                type="checkbox"
                checked={showTitleInput}
                onChange={(e) => setShowTitleInput(e.target.checked)}
                style={{ accentColor: '#0052cc' }}
              />
              Title
            </label>
            <label style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#172b4d' }}>
              <input
                type="checkbox"
                checked={showDescInput}
                onChange={(e) => setShowDescInput(e.target.checked)}
                style={{ accentColor: '#0052cc' }}
              />
              Description
            </label>
          </div>
          {showTitleInput && (
            <div style={{ marginTop: 8 }}>
              <input
                value={widget.title ?? ''}
                onChange={(e) => updateWidget(widget.id, { title: e.target.value })}
                placeholder="Widget title"
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: '0.77rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: 4,
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                }}
              />
            </div>
          )}
          {showDescInput && (
            <div style={{ marginTop: 8 }}>
              <input
                value={widget.content ?? ''}
                onChange={(e) => updateWidget(widget.id, { content: e.target.value })}
                placeholder="Widget description"
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: '0.77rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: 4,
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                }}
              />
            </div>
          )}
        </div>

        {/* Dataset Section */}
        <SectionRow
          title="Dataset"
          onPlus={() => setShowFilters(!showFilters)}
          actionText={showFilters ? 'Hide filters' : 'Show filters'}
        >
          <Select
            value={cfg.datasetId ?? ''}
            onChange={(v) => patch({ datasetId: v })}
            options={datasetOptions}
            placeholder="Select dataset..."
          />
          {showFilters && (
            <div style={{ marginTop: 8, padding: '6px 8px', background: '#f4f5f7', borderRadius: 4 }}>
              <span style={{ fontSize: '0.7rem', color: '#5e6c84', display: 'block', marginBottom: 2 }}>Static Filters</span>
              {widget.staticFilters && widget.staticFilters.length > 0 ? (
                widget.staticFilters.map((f) => (
                  <div
                    key={f.id}
                    style={{
                      fontSize: '0.72rem',
                      color: '#172b4d',
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '2px 0',
                    }}
                  >
                    <span>{f.field}</span>
                    <span style={{ fontWeight: 600 }}>{String(f.value)}</span>
                  </div>
                ))
              ) : (
                <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                  No static filters configured
                </span>
              )}
            </div>
          )}
        </SectionRow>

        {/* Parameters Section */}
        <SectionRow title="Parameters" onPlus={() => {}}>
          {dataset && dataset.params.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {dataset.params.map((p) => (
                <div
                  key={p.keyword}
                  style={{
                    fontSize: '0.72rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    background: '#f4f5f7',
                    padding: '4px 6px',
                    borderRadius: 4,
                  }}
                >
                  <span>{p.displayName || p.keyword}</span>
                  <span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>{p.type}</span>
                </div>
              ))}
            </div>
          ) : (
            <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
              No parameters in dataset
            </span>
          )}
        </SectionRow>

        {/* Visualization Selector Section */}
        <SectionRow title="Visualization">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative' }}>
            <div
              style={{
                position: 'absolute',
                left: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                display: 'flex',
                alignItems: 'center',
                pointerEvents: 'none',
                opacity: 0.6,
              }}
            >
              {getChartIcon(cfg.chartType)}
            </div>
            <select
              value={cfg.chartType}
              onChange={(e) => patch({ chartType: e.target.value as ChartType })}
              style={{
                width: '100%',
                padding: '6px 8px 6px 28px',
                fontSize: '0.77rem',
                border: '1px solid var(--color-border)',
                borderRadius: 4,
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                cursor: 'pointer',
              }}
            >
              {CHART_TYPES.map((ct) => (
                <option key={ct.type} value={ct.type}>
                  {ct.label}
                </option>
              ))}
            </select>
          </div>
        </SectionRow>

        {/* Dynamic Visualization-Specific Configuration (Strategy/Registry) */}
        <ConfigComponent
          widget={widget}
          config={cfg}
          dataset={dataset}
          fieldOptions={fieldOptions}
          getFieldType={getFieldType}
          patch={patch}
          patchAxis={patchAxis}
        />

      </div>
    </DashboardSidePanel>
  );
}
