import React, { useEffect } from 'react';
import DashboardEditorPage from '@/modules/dashboards/pages/DashboardEditorPage';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';

interface PortalDashboardViewProps {
  dashboardId: string;
}

export function PortalDashboardView({ dashboardId }: PortalDashboardViewProps) {
  const setEditMode = useDashboardStore((s) => s.setEditMode);

  useEffect(() => {
    // Ensure dashboard renders in clean presentation mode without editor chrome
    setEditMode(false);
  }, [dashboardId, setEditMode]);

  return (
    <div style={{ width: '100%', height: '100%', overflow: 'hidden' }}>
      <DashboardEditorPage dashboardId={dashboardId} embedded={true} />
    </div>
  );
}
