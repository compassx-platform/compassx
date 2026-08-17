import { create } from 'zustand';
import { randomUUID } from '@/lib/utils';
import type {
  Dashboard, DashboardPage, Widget, Dataset,
  FilterState, ParamState, GridItem, FilterValue,
  DashboardSettings,
} from '@/types/dashboard';

interface HistoryEntry {
  pages: DashboardPage[];
  widgets: Widget[];
}

interface DashboardStore {
  // Active dashboard
  activeDashboard: Dashboard | null;
  activePageId: string | null;
  editMode: boolean;
  selectedWidgetId: string | null;

  // Filter/param runtime state
  filterState: FilterState;
  pendingFilterState: FilterState;
  paramState: ParamState;

  // Undo/redo
  history: HistoryEntry[];
  historyIndex: number;

  // Drill-through context
  drillContext: Record<string, FilterValue> | null;

  // Actions: dashboard lifecycle
  setActiveDashboard: (d: Dashboard | null) => void;
  setEditMode: (v: boolean) => void;
  setActivePageId: (id: string) => void;
  setSelectedWidget: (id: string | null) => void;

  // Actions: pages
  addPage: () => void;
  deletePage: (id: string) => void;
  renamePage: (id: string, name: string) => void;
  clonePage: (id: string) => void;
  reorderPages: (ids: string[]) => void;

  // Actions: widgets
  addWidget: (widget: Widget) => void;
  deleteWidget: (id: string) => void;
  cloneWidget: (id: string) => void;
  updateWidget: (id: string, patch: Partial<Widget>) => void;
  updateLayout: (pageId: string, layout: GridItem[]) => void;

  // Actions: datasets
  addDataset: (ds: Dataset) => void;
  updateDataset: (id: string, patch: Partial<Dataset>) => void;
  deleteDataset: (id: string) => void;
  cloneDataset: (id: string) => void;

  // Actions: settings
  updateSettings: (patch: Partial<DashboardSettings>) => void;

  // Actions: filters
  setFilterValue: (id: string, value: FilterValue) => void;
  setPendingFilterValue: (id: string, value: FilterValue) => void;
  applyPendingFilters: () => void;
  clearAllFilters: () => void;
  setParamValue: (keyword: string, value: FilterValue) => void;

  // Actions: drill-through
  setDrillContext: (ctx: Record<string, FilterValue> | null) => void;

  // Undo/redo
  undo: () => void;
  redo: () => void;
  _pushHistory: () => void;
}

const MAX_HISTORY = 50;

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  activeDashboard: null,
  activePageId: null,
  editMode: false,
  selectedWidgetId: null,
  filterState: {},
  pendingFilterState: {},
  paramState: {},
  history: [],
  historyIndex: -1,
  drillContext: null,

  setActiveDashboard: (d) => set((state) => {
    const pageExists = d?.pages?.some((p) => p.id === state.activePageId);
    const nextPageId = pageExists ? state.activePageId : (d?.pages[0]?.id ?? null);
    return {
      activeDashboard: d,
      activePageId: nextPageId,
      filterState: {},
      pendingFilterState: {},
      paramState: {},
      history: [],
      historyIndex: -1,
      selectedWidgetId: null,
    };
  }),

  setEditMode: (v) => set({ editMode: v }),
  setActivePageId: (id) => set({ activePageId: id, selectedWidgetId: null }),
  setSelectedWidget: (id) => set({ selectedWidgetId: id }),

  // ── Pages ──────────────────────────────────────────────────────────────────

  addPage: () => set((s) => {
    if (!s.activeDashboard) return s;
    s._pushHistory();
    const newPage: DashboardPage = {
      id: randomUUID(),
      dashboardId: s.activeDashboard.id,
      name: `Page ${s.activeDashboard.pages.length + 1}`,
      order: s.activeDashboard.pages.length,
      layout: [],
    };
    return {
      activeDashboard: {
        ...s.activeDashboard,
        pages: [...s.activeDashboard.pages, newPage],
      },
      activePageId: newPage.id,
    };
  }),

  deletePage: (id) => set((s) => {
    if (!s.activeDashboard) return s;
    s._pushHistory();
    const pages = s.activeDashboard.pages.filter((p) => p.id !== id);
    const widgets = s.activeDashboard.widgets.filter((w) => w.pageId !== id);
    const nextPageId = pages[0]?.id ?? null;
    return {
      activeDashboard: { ...s.activeDashboard, pages, widgets },
      activePageId: s.activePageId === id ? nextPageId : s.activePageId,
    };
  }),

  renamePage: (id, name) => set((s) => {
    if (!s.activeDashboard) return s;
    return {
      activeDashboard: {
        ...s.activeDashboard,
        pages: s.activeDashboard.pages.map((p) => p.id === id ? { ...p, name } : p),
      },
    };
  }),

  clonePage: (id) => set((s) => {
    if (!s.activeDashboard) return s;
    s._pushHistory();
    const src = s.activeDashboard.pages.find((p) => p.id === id);
    if (!src) return s;
    const newPageId = randomUUID();
    let baseName = src.name;
    const existing = s.activeDashboard.pages.map((p) => p.name);
    let suffix = 2;
    let candidate = `${baseName} (${suffix})`;
    while (existing.includes(candidate)) { suffix++; candidate = `${baseName} (${suffix})`; }
    const newPage: DashboardPage = { ...src, id: newPageId, name: candidate, order: s.activeDashboard.pages.length };
    const widgetsToCopy = s.activeDashboard.widgets
      .filter((w) => w.pageId === id)
      .map((w) => ({ ...w, id: randomUUID(), pageId: newPageId }));
    return {
      activeDashboard: {
        ...s.activeDashboard,
        pages: [...s.activeDashboard.pages, newPage],
        widgets: [...s.activeDashboard.widgets, ...widgetsToCopy],
      },
      activePageId: newPageId,
    };
  }),

  reorderPages: (ids) => set((s) => {
    if (!s.activeDashboard) return s;
    const pageMap = Object.fromEntries(s.activeDashboard.pages.map((p) => [p.id, p]));
    const pages = ids.map((id, i) => ({ ...pageMap[id], order: i }));
    return { activeDashboard: { ...s.activeDashboard, pages } };
  }),

  // ── Widgets ────────────────────────────────────────────────────────────────

  addWidget: (widget) => set((s) => {
    if (!s.activeDashboard) return s;
    s._pushHistory();
    return { activeDashboard: { ...s.activeDashboard, widgets: [...s.activeDashboard.widgets, widget] } };
  }),

  deleteWidget: (id) => set((s) => {
    if (!s.activeDashboard) return s;
    s._pushHistory();
    return {
      activeDashboard: { ...s.activeDashboard, widgets: s.activeDashboard.widgets.filter((w) => w.id !== id) },
      selectedWidgetId: s.selectedWidgetId === id ? null : s.selectedWidgetId,
    };
  }),

  cloneWidget: (id) => set((s) => {
    if (!s.activeDashboard) return s;
    s._pushHistory();
    const src = s.activeDashboard.widgets.find((w) => w.id === id);
    if (!src) return s;
    const clone: Widget = {
      ...src,
      id: randomUUID(),
      gridItem: { ...src.gridItem, i: randomUUID(), x: src.gridItem.x, y: src.gridItem.y + src.gridItem.h + 1 },
    };
    return { activeDashboard: { ...s.activeDashboard, widgets: [...s.activeDashboard.widgets, clone] } };
  }),

  updateWidget: (id, patch) => set((s) => {
    if (!s.activeDashboard) return s;
    return {
      activeDashboard: {
        ...s.activeDashboard,
        widgets: s.activeDashboard.widgets.map((w) => w.id === id ? { ...w, ...patch } : w),
      },
    };
  }),

  updateLayout: (pageId, layout) => set((s) => {
    if (!s.activeDashboard) return s;
    const gridMap = Object.fromEntries(layout.map((g) => [g.i, g]));
    return {
      activeDashboard: {
        ...s.activeDashboard,
        pages: s.activeDashboard.pages.map((p) =>
          p.id === pageId ? { ...p, layout } : p
        ),
        widgets: s.activeDashboard.widgets.map((w) =>
          w.pageId === pageId && gridMap[w.id]
            ? { ...w, gridItem: gridMap[w.id] }
            : w
        ),
      },
    };
  }),

  // ── Datasets ───────────────────────────────────────────────────────────────

  addDataset: (ds) => set((s) => {
    if (!s.activeDashboard) return s;
    return { activeDashboard: { ...s.activeDashboard, datasets: [...s.activeDashboard.datasets, ds] } };
  }),

  updateDataset: (id, patch) => set((s) => {
    if (!s.activeDashboard) return s;
    return {
      activeDashboard: {
        ...s.activeDashboard,
        datasets: s.activeDashboard.datasets.map((d) => d.id === id ? { ...d, ...patch } : d),
      },
    };
  }),

  deleteDataset: (id) => set((s) => {
    if (!s.activeDashboard) return s;
    const inUse = s.activeDashboard.widgets.some((w) => w.chartConfig?.datasetId === id);
    if (inUse) return s;
    return {
      activeDashboard: { ...s.activeDashboard, datasets: s.activeDashboard.datasets.filter((d) => d.id !== id) },
    };
  }),

  cloneDataset: (id) => set((s) => {
    if (!s.activeDashboard) return s;
    const src = s.activeDashboard.datasets.find((d) => d.id === id);
    if (!src) return s;
    const clone: Dataset = { ...src, id: randomUUID(), name: `${src.name} (copy)` };
    return { activeDashboard: { ...s.activeDashboard, datasets: [...s.activeDashboard.datasets, clone] } };
  }),

  // ── Settings ───────────────────────────────────────────────────────────────

  updateSettings: (patch) => set((s) => {
    if (!s.activeDashboard) return s;
    return {
      activeDashboard: {
        ...s.activeDashboard,
        settings: { ...s.activeDashboard.settings, ...patch },
      },
    };
  }),

  // ── Filters ────────────────────────────────────────────────────────────────

  setFilterValue: (id, value) => set((s) => ({ filterState: { ...s.filterState, [id]: value } })),
  setPendingFilterValue: (id, value) => set((s) => ({ pendingFilterState: { ...s.pendingFilterState, [id]: value } })),
  applyPendingFilters: () => set((s) => ({ filterState: { ...s.filterState, ...s.pendingFilterState }, pendingFilterState: {} })),
  clearAllFilters: () => set({ filterState: {}, pendingFilterState: {} }),
  setParamValue: (keyword, value) => set((s) => ({ paramState: { ...s.paramState, [keyword]: value } })),

  // ── Drill-through ──────────────────────────────────────────────────────────

  setDrillContext: (ctx) => set({ drillContext: ctx }),

  // ── Undo / Redo ────────────────────────────────────────────────────────────

  _pushHistory: () => {
    const s = get();
    if (!s.activeDashboard) return;
    const entry: HistoryEntry = {
      pages: JSON.parse(JSON.stringify(s.activeDashboard.pages)),
      widgets: JSON.parse(JSON.stringify(s.activeDashboard.widgets)),
    };
    const newHistory = s.history.slice(0, s.historyIndex + 1);
    if (newHistory.length >= MAX_HISTORY) newHistory.shift();
    set({ history: [...newHistory, entry], historyIndex: Math.min(newHistory.length, MAX_HISTORY - 1) });
  },

  undo: () => set((s) => {
    if (!s.activeDashboard || s.historyIndex < 0) return s;
    const entry = s.history[s.historyIndex];
    return {
      activeDashboard: { ...s.activeDashboard, pages: entry.pages, widgets: entry.widgets },
      historyIndex: s.historyIndex - 1,
    };
  }),

  redo: () => set((s) => {
    if (!s.activeDashboard || s.historyIndex >= s.history.length - 1) return s;
    const entry = s.history[s.historyIndex + 1];
    return {
      activeDashboard: { ...s.activeDashboard, pages: entry.pages, widgets: entry.widgets },
      historyIndex: s.historyIndex + 1,
    };
  }),
}));
