import { useCallback } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { stripAppScope } from '@/lib/appNavigation';
import { useNotebookStore, type Cell, type CellOutput } from '@/modules/notebooks/store/notebookStore';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';

function outputToSerializable(output: CellOutput) {
  if (output.type === 'stream') return { type: output.type, name: output.name, text: output.text };
  if (output.type === 'result') return output;
  if (output.type === 'display') return output;
  return output;
}

function buildCellStates(cells: Cell[]) {
  return cells.map((cell, index) => ({
    cell_index: index,
    output: cell.outputs.map(outputToSerializable),
    execution_count: cell.executionCount,
    variable_state: {},
    source: cell.source,
    committed_source: cell.committedSource ?? null,
    pending_source: cell.pendingSource ?? null,
    cell_status: cell.cellStatus ?? 'clean',
  }));
}

function findLastExecutedIndex(cells: Cell[]) {
  let lastIndex: number | null = null;
  let lastTime = -1;
  cells.forEach((cell, index) => {
    if (!cell.executedAt) return;
    const time = new Date(cell.executedAt).getTime();
    if (time > lastTime) {
      lastTime = time;
      lastIndex = index;
    }
  });
  return lastIndex;
}

export function useCurrentPageContext() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const scopedPathname = stripAppScope(location.pathname);

  const buildPageContextPayload = useCallback(() => {
    const currentCells = useNotebookStore.getState().cells;
    const currentFocusedCellId = useNotebookStore.getState().focusedCellId;
    const currentFocusedCellIndex = currentCells.findIndex((cell) => cell.id === currentFocusedCellId);

    // Dashboard context — injected when the user is on any /dashboards/:id route
    let dashboardContext: Record<string, unknown> | null = null;
    if (scopedPathname.match(/^\/dashboards\/[^/]+/)) {
      const activeDashboard = useDashboardStore.getState().activeDashboard;
      if (activeDashboard) {
        dashboardContext = {
          dashboard_id: activeDashboard.id,
          dashboard_name: activeDashboard.name,
          is_draft: activeDashboard.isDraft,
          pages: activeDashboard.pages.map((p) => ({
            id: p.id,
            name: p.name,
            order: p.order,
            widget_count: activeDashboard.widgets.filter((w) => w.pageId === p.id).length,
          })),
          widgets: activeDashboard.widgets.map((w) => ({
            id: w.id,
            page_id: w.pageId,
            widget_type: w.widgetType,
            title: w.title ?? null,
            chart_type: w.chartConfig?.chartType ?? null,
            dataset_id: w.chartConfig?.datasetId ?? null,
            x_field: w.chartConfig?.xField ?? null,
            y_fields: w.chartConfig?.yFields ?? null,
            color_field: w.chartConfig?.colorField ?? null,
          })),
          datasets: activeDashboard.datasets.map((d) => ({
            id: d.id,
            name: d.name,
            sql: d.sql,
          })),
        };
      }
    }

    const activeNotebookPath =
      searchParams.get('path') ||
      (scopedPathname.startsWith('/notebooks/open') ? searchParams.get('path') ?? 'notebooks/untitled.ipynb' : null) ||
      useNotebookStore.getState().notebookPath;

    const isNotebookActive =
      scopedPathname.startsWith('/notebooks/open') ||
      (scopedPathname.startsWith('/data-catalog') &&
        (scopedPathname.endsWith('.ipynb') || searchParams.has('notebook') || searchParams.has('path') || currentCells.length > 0));

    return {
      surface: 'agent_side_panel',
      route: scopedPathname,
      notebook: isNotebookActive
        ? {
            notebook_path: activeNotebookPath,
            focused_cell_index: currentFocusedCellIndex >= 0 ? currentFocusedCellIndex : null,
            last_executed_cell_index: findLastExecutedIndex(currentCells),
            attached_kernel: 'python3',
            kernel_id: useNotebookStore.getState().kernelRef?.id || null,
            cell_states: buildCellStates(currentCells),
          }
        : null,
      dashboard: dashboardContext,
    };
  }, [scopedPathname, searchParams]);

  return {
    scopedPathname,
    buildPageContextPayload,
  };
}
