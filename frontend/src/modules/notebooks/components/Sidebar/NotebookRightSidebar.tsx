import React from 'react';
import {
  SlidersHorizontal,
  Terminal,
  X,
  Info,
} from 'lucide-react';
import { useNotebookStore, type RightSidebarTab } from '../../store/notebookStore';
import ComputeConfigPanel from './ComputeConfigPanel';
import VariablesPanel from './VariablesPanel';
import PodLogsPanel from './PodLogsPanel';
import InfoPanel from './InfoPanel';

interface TabConfig {
  id: RightSidebarTab;
  label: string;
  title: string;
  icon: React.ComponentType<any>;
  badge?: number | string | null;
  customIcon?: React.ReactNode;
}

export default function NotebookRightSidebar() {
  const isRightSidebarOpen = useNotebookStore((s) => s.isRightSidebarOpen);
  const activeRightSidebarTab = useNotebookStore((s) => s.activeRightSidebarTab);
  const toggleRightSidebarTab = useNotebookStore((s) => s.toggleRightSidebarTab);
  const setRightSidebarOpen = useNotebookStore((s) => s.setRightSidebarOpen);
  const isBottomTerminalOpen = useNotebookStore((s) => s.isBottomTerminalOpen);
  const toggleBottomTerminal = useNotebookStore((s) => s.toggleBottomTerminal);
  const variables = useNotebookStore((s) => s.variables);
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);

  // Custom {x} Variable icon SVG matching Databricks style
  const VariableIcon = () => (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 3c-1 0-1.5.5-1.5 2v1.5c0 1-.5 1.5-1.5 1.5 1 0 1.5.5 1.5 1.5V11c0 1.5.5 2 1.5 2" />
      <path d="M12 3c1 0 1.5.5 1.5 2v1.5c0 1 .5 1.5 1.5 1.5-1 0-1.5.5-1.5 1.5V11c0 1.5-.5 2-1.5 2" />
      <path d="M6.5 6.5l3 3" />
      <path d="M9.5 6.5l-3 3" />
    </svg>
  );

  // Top group dock tabs
  const TABS: TabConfig[] = [
    {
      id: 'variables',
      label: 'Variables',
      title: 'Variables',
      icon: SlidersHorizontal,
      customIcon: <VariableIcon />,
      badge: variables.length > 0 ? variables.length : null,
    },
    {
      id: 'config',
      label: 'Configuration',
      title: 'Configuration',
      icon: SlidersHorizontal,
    },
    {
      id: 'info',
      label: 'Information',
      title: 'Information',
      icon: Info,
    },
  ];

  const currentTab = TABS.find((t) => t.id === activeRightSidebarTab);

  return (
    <div className={`dbx-sidebar-wrapper ${isRightSidebarOpen ? 'is-open' : 'is-collapsed'}`}>
      {/* ── Collapsible Content Panel (Drawer) ── */}
      {isRightSidebarOpen && (
        <aside className="dbx-drawer-panel">
          {/* Header */}
          <div className="dbx-drawer-header">
            <h3 className="dbx-drawer-title">{currentTab?.title || 'Configuration'}</h3>
            <div className="dbx-drawer-header-actions">
              <button
                type="button"
                className="dbx-close-btn"
                onClick={() => setRightSidebarOpen(false)}
                title="Close panel"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="dbx-drawer-body">
            {activeRightSidebarTab === 'config' && <ComputeConfigPanel />}
            {activeRightSidebarTab === 'variables' && <VariablesPanel />}
            {activeRightSidebarTab === 'logs' && <PodLogsPanel />}
            {activeRightSidebarTab === 'info' && <InfoPanel />}
          </div>
        </aside>
      )}

      {/* ── Vertical Icon Strip (Databricks-style Dock) ── */}
      <div className="dbx-icon-dock">
        <div className="dbx-dock-group dbx-dock-group--top">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = isRightSidebarOpen && activeRightSidebarTab === tab.id;
            return (
              <button
                type="button"
                key={tab.id}
                className={`dbx-dock-item ${isActive ? 'is-active' : ''}`}
                onClick={() => toggleRightSidebarTab(tab.id)}
                title={tab.label}
              >
                {tab.customIcon ? tab.customIcon : <Icon size={15} />}
                {tab.badge !== null && tab.badge !== undefined && (
                  <span className="dbx-dock-badge">{tab.badge}</span>
                )}
              </button>
            );
          })}

          {/* Terminal Toggle Button */}
          <button
            type="button"
            className={`dbx-dock-item ${isBottomTerminalOpen ? 'is-active' : ''}`}
            onClick={toggleBottomTerminal}
            title="Terminal • Pod Shell"
          >
            <Terminal size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
