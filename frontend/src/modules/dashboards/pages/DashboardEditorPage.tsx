/**
 * DashboardEditorPage — top-level editor/viewer page.
 * Composes: TopBar, PageTabBar, FilterBar, DataPanel, Canvas, ConfigPanel.
 * Keyboard shortcuts: Ctrl+Z undo, Ctrl+Y redo, Ctrl+C/V copy/paste, Delete.
 * Reference: Databricks AI/BI dashboard editor full layout.
 */

import { useEffect, useState, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useDashboard, useSaveDashboard } from '@/modules/dashboards/hooks/useDashboard';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useToast } from '@/lib/toast';
import { randomUUID } from '@/lib/utils';
import { useCurrentAppId } from '@/lib/appNavigation';
import DashboardTopBar from '@/modules/dashboards/components/DashboardTopBar';
import PageTabBar from '@/modules/dashboards/components/PageTabBar';
import FilterBar from '@/modules/dashboards/components/FilterBar';
import DataPanel from '@/modules/dashboards/components/DataPanel';
import DashboardCanvas from '@/modules/dashboards/components/DashboardCanvas';
import ChartConfigPanel from '@/modules/dashboards/components/ChartConfigPanel';
import DashboardSettings from '@/modules/dashboards/components/DashboardSettings';
import type { Widget } from '@/types/dashboard';

type EditorTab = 'data' | 'page';
type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';
const AUTOSAVE_DELAY_MS = 1200;

interface Props {
  dashboardId?: string;
  embedded?: boolean;
}

export default function DashboardEditorPage({ dashboardId: dashboardIdProp, embedded = false }: Props) {
  const { dashboardId: routeDashboardId } = useParams<{ dashboardId: string }>();
  const dashboardId = dashboardIdProp ?? routeDashboardId;
  const toast = useToast();
  const appId = useCurrentAppId();
  const isBusinessCenter = appId === 'business_center';

  const { data: dashboard, isLoading, error, refetch: refetchDashboard } = useDashboard(dashboardId);
  const saveDashboardMutation = useSaveDashboard();
  const {
    activeDashboard,
    editMode,
    selectedWidgetId,
    setActiveDashboard,
    setEditMode,
    undo,
    redo,
    addWidget,
    activePageId,
    deleteWidget,
  } = useDashboardStore();


  const [activeTab, setActiveTab] = useState<EditorTab>('page');
  const [showSettings, setShowSettings] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const copiedWidget = useRef<Widget | null>(null);
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveStatusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedSnapshotRef = useRef<string>('');
  const latestDashboardRef = useRef<typeof activeDashboard>(null);
  const isHydratedRef = useRef(false);
  const isAutosavingRef = useRef(false);
  const initializedDashboardIdRef = useRef<string | null>(null);

  const activeDashboardSnapshot = activeDashboard ? JSON.stringify(activeDashboard) : '';

  function clearSaveStatusTimer() {
    if (saveStatusTimerRef.current) {
      clearTimeout(saveStatusTimerRef.current);
      saveStatusTimerRef.current = null;
    }
  }

  function markSaved() {
    clearSaveStatusTimer();
    setSaveStatus('saved');
    saveStatusTimerRef.current = setTimeout(() => {
      setSaveStatus('idle');
    }, 1600);
  }

  async function flushAutosave() {
    const dashboardToSave = latestDashboardRef.current;
    if (!dashboardToSave) return;

    const snapshot = JSON.stringify(dashboardToSave);
    if (snapshot === lastSavedSnapshotRef.current) return;
    if (isAutosavingRef.current) return;

    isAutosavingRef.current = true;
    clearSaveStatusTimer();
    setSaveStatus('saving');

    try {
      await saveDashboardMutation.mutateAsync(dashboardToSave);
      lastSavedSnapshotRef.current = snapshot;
      markSaved();
    } catch {
      setSaveStatus('error');
    } finally {
      isAutosavingRef.current = false;
    }
  }

  const isEditRoute = embedded || window.location.pathname.endsWith('/edit');

  useEffect(() => {
    setEditMode(!isBusinessCenter && isEditRoute);
  }, [isBusinessCenter, isEditRoute, setEditMode]);

  // Listen for the signal emitted by AppNovaSidebar after a mutating
  // dashboard_manager tool call. Explicitly refetches the dashboard from the server
  // and directly updates the Zustand store so the UI updates live.
  useEffect(() => {
    async function handleAgentMutation(e: Event) {
      const detail = (e as CustomEvent<{ dashboardId: string }>).detail;
      if (detail?.dashboardId === dashboardId) {
        const { data: freshDashboard } = await refetchDashboard();
        if (freshDashboard) {
          setActiveDashboard(freshDashboard);
          lastSavedSnapshotRef.current = JSON.stringify(freshDashboard);
          latestDashboardRef.current = freshDashboard;
          setSaveStatus('idle');
        }
      }
    }
    window.addEventListener('dashboard:agent-mutation', handleAgentMutation);
    return () => window.removeEventListener('dashboard:agent-mutation', handleAgentMutation);
  }, [dashboardId, refetchDashboard, setActiveDashboard]);

  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    if (dashboard) {
      if (initializedDashboardIdRef.current === dashboard.id) return;

      initializedDashboardIdRef.current = dashboard.id;
      setActiveDashboard(dashboard);
      setEditMode(!isBusinessCenter && isEditRoute);
      setActiveTab('page');

      // Sync active page from URL query parameter on page load / refresh
      const urlPageParam = searchParams.get('page');
      if (urlPageParam && dashboard.pages.length > 0) {
        const targetPage = dashboard.pages.find(
          (p) => p.id === urlPageParam || p.name.toLowerCase() === urlPageParam.toLowerCase()
        );
        if (targetPage) {
          useDashboardStore.getState().setActivePageId(targetPage.id);
        }
      }

      lastSavedSnapshotRef.current = JSON.stringify(dashboard);
      latestDashboardRef.current = dashboard;
      isHydratedRef.current = true;
      setSaveStatus('idle');
    }
  }, [dashboard, setActiveDashboard, setEditMode, isBusinessCenter, isEditRoute, searchParams]);

  // Keep URL query parameter ?page= in sync when activePageId changes
  useEffect(() => {
    if (!activePageId || !isHydratedRef.current) return;
    const currentUrlPage = searchParams.get('page');
    if (currentUrlPage !== activePageId) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set('page', activePageId);
          return next;
        },
        { replace: true }
      );
    }
  }, [activePageId, searchParams, setSearchParams]);


  useEffect(() => {
    latestDashboardRef.current = activeDashboard;
  }, [activeDashboard]);

  useEffect(() => {
    if (!editMode && activeTab === 'data') {
      setActiveTab('page');
    }
  }, [editMode, activeTab]);

  useEffect(() => {
    if (!activeDashboard || !isHydratedRef.current) return;
    if (activeDashboardSnapshot === lastSavedSnapshotRef.current) return;

    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
    }

    setSaveStatus('saving');
    autosaveTimerRef.current = setTimeout(() => {
      flushAutosave();
    }, AUTOSAVE_DELAY_MS);

    return () => {
      if (autosaveTimerRef.current) {
        clearTimeout(autosaveTimerRef.current);
        autosaveTimerRef.current = null;
      }
    };
  }, [activeDashboard, activeDashboardSnapshot]);

  useEffect(() => {
    if (editMode) return;
    if (activeDashboardSnapshot !== lastSavedSnapshotRef.current) {
      void flushAutosave();
    }
  }, [editMode, activeDashboardSnapshot]);

  useEffect(() => {
    function handlePageHide() {
      if (activeDashboardSnapshot !== lastSavedSnapshotRef.current) {
        void flushAutosave();
      }
    }

    window.addEventListener('pagehide', handlePageHide);
    return () => window.removeEventListener('pagehide', handlePageHide);
  }, [activeDashboardSnapshot]);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const ctrl = e.ctrlKey || e.metaKey;
      if (!ctrl && e.key !== 'Delete' && e.key !== 'Backspace') return;

      if (ctrl && e.key === 'z') { e.preventDefault(); undo(); return; }
      if (ctrl && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) { e.preventDefault(); redo(); return; }
      if (ctrl && e.key === 'c' && selectedWidgetId) {
        const w = activeDashboard?.widgets.find((widget) => widget.id === selectedWidgetId);
        if (w) {
          copiedWidget.current = w;
          toast.info('Widget copied');
        }
        return;
      }
      if (ctrl && e.key === 'v' && copiedWidget.current && activePageId) {
        const src = copiedWidget.current;
        const newId = randomUUID();
        const newW: Widget = {
          ...src,
          id: newId,
          pageId: activePageId,
          gridItem: { ...src.gridItem, i: newId, y: src.gridItem.y + src.gridItem.h + 1 },
        };
        addWidget(newW);
        return;
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedWidgetId) {
        const tag = (e.target as HTMLElement).tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        deleteWidget(selectedWidgetId);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedWidgetId, activePageId, activeDashboard, undo, redo, addWidget, deleteWidget, toast]);

  useEffect(() => {
    if (selectedWidgetId) {
      setShowSettings(false);
    }
  }, [selectedWidgetId]);

  function handleAddChart() {
    if (!activePageId || !activeDashboard) return;
    const id = randomUUID();
    const widget: Widget = {
      id,
      pageId: activePageId,
      widgetType: 'chart',
      title: 'New chart',
      gridItem: { i: id, x: 0, y: 0, w: 4, h: 2, minW: 2, minH: 2 },
      chartConfig: {
        chartType: 'bar',
        datasetId: activeDashboard.datasets[0]?.id,
        showGridlines: true,
        legend: { show: true, position: 'bottom' },
      },
    };
    addWidget(widget);
  }

  function handleAddFilter() {
    if (!activePageId || !activeDashboard) return;
    const id = randomUUID();
    const widget: Widget = {
      id,
      pageId: activePageId,
      widgetType: 'filter',
      title: 'Filter',
      gridItem: { i: id, x: 0, y: 0, w: 3, h: 3, minW: 2, minH: 2 },
      filterConfig: {
        scope: 'page',
        filterType: 'single_value',
        datasetIds: activeDashboard.datasets[0] ? [activeDashboard.datasets[0].id] : [],
        allowAll: true,
      },
    };
    addWidget(widget);
  }

  function handleAddHtmlWidget() {
    if (!activePageId || !activeDashboard) return;
    const id = randomUUID();
    const widget: Widget = {
      id,
      pageId: activePageId,
      widgetType: 'html',
      title: 'HTML widget',
      gridItem: { i: id, x: 0, y: 0, w: 4, h: 2, minW: 2, minH: 2 },
      content: '',
      htmlConfig: {
        title: 'Custom HTML widget',
        subtitle: 'Write HTML/CSS to create a reusable dashboard component',
      },
    };
    addWidget(widget);
    setActiveTab('page');
    toast.info('HTML widget added');
  }

  if (isLoading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, color: 'var(--color-text-muted)' }}>
        <Loader2 size={20} className="spin" /> Loading dashboard...
      </div>
    );
  }

  if (error || !activeDashboard) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-danger)' }}>
        Failed to load dashboard.
      </div>
    );
  }

  const effectiveTab: EditorTab = editMode ? activeTab : 'page';

  function handleToggleSettings() {
    if (!showSettings) {
      useDashboardStore.getState().setSelectedWidget(null);
    }
    setShowSettings((prev) => !prev);
  }

  return (
    <div className="dashboard-editor-page" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {editMode && (
        <DashboardTopBar
          onOpenSettings={handleToggleSettings}
          onAddChart={handleAddChart}
          onAddFilter={handleAddFilter}
          onAddHtmlReport={handleAddHtmlWidget}
          saveStatus={saveStatus}
          hideBackButton={embedded}
        />
      )}

      <PageTabBar
        activeTab={effectiveTab}
        onSelectDataTab={() => setActiveTab('data')}
        onSelectPageTab={() => setActiveTab('page')}
      />

      <FilterBar />

      <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'stretch', overflow: 'hidden' }}>
        {effectiveTab === 'data' ? (
          <DataPanel onBackToPages={() => setActiveTab('page')} />
        ) : (
          <DashboardCanvas />
        )}

        {editMode && effectiveTab === 'page' && (
          showSettings ? (
            <DashboardSettings onClose={() => setShowSettings(false)} />
          ) : selectedWidgetId ? (
            <ChartConfigPanel onClose={() => useDashboardStore.getState().setSelectedWidget(null)} />
          ) : null
        )}
      </div>
    </div>
  );
}

