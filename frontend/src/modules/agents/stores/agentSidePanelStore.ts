import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AgentSidePanelState {
  isOpen: boolean;
  selectedAgentId: number | null;
  activeSessionPerAgent: Record<number, number>;
  panelWidth: number;

  setOpen: (value: boolean) => void;
  toggleOpen: () => void;
  setSelectedAgentId: (agentId: number | null) => void;
  setActiveSession: (agentId: number, sessionId: number | null) => void;
  setPanelWidth: (width: number) => void;
  openWithAgent: (agentId: number, sessionId?: number | null) => void;
}

export const useAgentSidePanelStore = create<AgentSidePanelState>()(
  persist(
    (set) => ({
      isOpen: false,
      selectedAgentId: null,
      activeSessionPerAgent: {},
      panelWidth: 400,

      setOpen: (value) => set({ isOpen: value }),
      toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
      setSelectedAgentId: (agentId) => set({ selectedAgentId: agentId }),
      setActiveSession: (agentId, sessionId) =>
        set((state) => {
          const next = { ...state.activeSessionPerAgent };
          if (sessionId == null) {
            delete next[agentId];
          } else {
            next[agentId] = sessionId;
          }
          return { activeSessionPerAgent: next };
        }),
      setPanelWidth: (width) => set({ panelWidth: Math.max(300, Math.min(800, width)) }),
      openWithAgent: (agentId, sessionId) =>
        set((state) => {
          const next = { ...state.activeSessionPerAgent };
          if (sessionId != null) {
            next[agentId] = sessionId;
          }
          return {
            isOpen: true,
            selectedAgentId: agentId,
            activeSessionPerAgent: next,
          };
        }),
    }),
    {
      name: 'agent-side-panel-store',
      version: 1,
      partialize: (state) => ({
        isOpen: state.isOpen,
        selectedAgentId: state.selectedAgentId,
        activeSessionPerAgent: state.activeSessionPerAgent,
        panelWidth: state.panelWidth,
      }),
    }
  )
);
