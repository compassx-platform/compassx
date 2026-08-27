/**
 * DashboardCanvas — react-grid-layout surface.
 * 12-col grid, rowHeight=40, drag+resize in edit mode.
 * Reference: Databricks dashboard canvas with grid widgets.
 */

import { useCallback, useRef, useState, useEffect } from 'react';
import GridLayout from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import WidgetCard from './WidgetCard';
import PlotlyWidget from './widgets/PlotlyWidget';
import CounterWidget from './widgets/CounterWidget';
import TableWidget from './widgets/TableWidget';
import PivotWidget from './widgets/PivotWidget';
import HtmlWidget from './widgets/HtmlWidget';
import FilterWidget from './filters/FilterWidget';
import type { Widget } from '@/types/dashboard';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const RESIZE_HANDLES: Array<'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'> = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];

function useContainerWidth(ref: React.RefObject<HTMLDivElement | null>, editMode: boolean) {
  const [width, setWidth] = useState(1200);
  useEffect(() => {
    if (!ref.current) return;
    const padding = editMode ? 24 : 32;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(w);
    });
    ro.observe(ref.current);
    setWidth((ref.current.offsetWidth - padding) || 1200);
    return () => ro.disconnect();
  }, [ref, editMode]);
  return width;
}

function WidgetRenderer({ widget }: { widget: Widget }) {
  if (widget.widgetType === 'filter') {
    return <FilterWidget widget={widget} />;
  }
  if (widget.widgetType === 'html') {
    return <HtmlWidget widget={widget} />;
  }
  if (widget.widgetType !== 'chart') {
    return (
      <div style={{ padding: 12, fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
        {widget.content ?? 'Widget'}
      </div>
    );
  }

  const ct = widget.chartConfig?.chartType;
  if (ct === 'counter') return <CounterWidget widget={widget} />;
  if (ct === 'table') return <TableWidget widget={widget} />;
  if (ct === 'pivot') return <PivotWidget widget={widget} />;
  return <PlotlyWidget widget={widget} />;
}

export default function DashboardCanvas() {
  const { activeDashboard, activePageId, editMode, updateLayout } = useDashboardStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const containerWidth = useContainerWidth(containerRef, editMode);
  const Grid = GridLayout as any;

  const gridCols = activeDashboard?.settings?.gridCols ?? 12;
  const gridRowHeight = activeDashboard?.settings?.gridRowHeight ?? 40;
  const minWidgetH = activeDashboard?.settings?.minWidgetHeight ?? 1;

  const page = activeDashboard?.pages.find((p) => p.id === activePageId);
  const widgets = (activeDashboard?.widgets ?? []).filter(
    (w) => w.pageId === activePageId && (w.widgetType !== 'filter' || w.filterConfig?.placement !== 'bar')
  );

  const layout = widgets.map((w) => ({
    i: w.id,
    x: w.gridItem.x,
    y: w.gridItem.y,
    w: w.gridItem.w,
    h: w.gridItem.h,
    minW: w.gridItem.minW ?? 1,
    minH: minWidgetH,
  }));

  const handleLayoutChange = useCallback((newLayout: Layout) => {
    if (!activePageId) return;
    updateLayout(activePageId, newLayout as any);
  }, [activePageId, updateLayout]);

  if (!page) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)' }}>
        No page selected
      </div>
    );
  }

  if (widgets.length === 0 && editMode) {
    return (
      <div ref={containerRef} style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--color-text-muted)',
        gap: 8,
      }}>
        <div style={{ fontSize: '2rem', opacity: 0.15 }}>+</div>
        <div style={{ fontSize: '0.85rem' }}>Start by adding a chart or filter to this page</div>
      </div>
    );
  }

  const theme = activeDashboard?.settings?.theme;
  const canvasBackground = theme?.canvasBg && theme.canvasBg !== 'Auto' ? theme.canvasBg : 'var(--color-bg)';
  const showGrid = activeDashboard?.settings?.showGridLines ?? true;

  const marginX = theme?.margin !== undefined ? theme.margin : 8;
  const marginY = theme?.margin !== undefined ? theme.margin : 8;
  const containerPaddingX = editMode ? 12 : 16;
  const containerPaddingY = editMode ? 12 : 16;

  const netWidth = Math.max(0, containerWidth - (containerPaddingX * 2));
  const colWidth = Math.max(1, (netWidth - (marginX * (gridCols - 1))) / gridCols);
  const stepX = colWidth + marginX;
  const stepY = gridRowHeight + marginY;

  const gridOverlayStyle: React.CSSProperties = (showGrid && editMode) ? {
    backgroundImage: `
      linear-gradient(to right, rgba(0, 82, 204, 0.12) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(0, 82, 204, 0.12) 1px, transparent 1px)
    `,
    backgroundSize: `${stepX}px ${stepY}px`,
    backgroundPosition: `${containerPaddingX}px ${containerPaddingY}px`,
  } : {};

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        overflowY: 'auto',
        background: canvasBackground,
        padding: editMode ? 12 : '16px 16px 16px',
        transition: 'background-color 0.15s',
        ...gridOverlayStyle,
      }}
    >
      <Grid
        layout={layout}
        cols={gridCols}
        rowHeight={gridRowHeight}
        width={containerWidth}
        isDraggable={editMode}
        isResizable={editMode}
        draggableHandle=".widget-drag-handle"
        draggableCancel=".widget-content-interactive, .js-plotly-plot, .plot-container, .modebar, .html-report-interactive, input, textarea, button, select, a"
        resizeHandles={RESIZE_HANDLES}
        resizeHandle={(axis: 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw', ref: React.Ref<HTMLElement>) => (
          <span
            ref={ref}
            className={`react-resizable-handle react-resizable-handle-${axis}`}
          />
        )}
        onLayoutChange={handleLayoutChange}
        margin={[marginX, marginY]}
        containerPadding={[containerPaddingX, containerPaddingY]}
      >
        {widgets.map((widget) => (
          <div
            key={widget.id}
            style={{
              overflow: 'visible',
              boxSizing: 'border-box',
              padding: 0,
            }}
          >
            <WidgetCard widget={widget}>
              <WidgetRenderer widget={widget} />
            </WidgetCard>
          </div>
        ))}
      </Grid>
    </div>
  );
}

