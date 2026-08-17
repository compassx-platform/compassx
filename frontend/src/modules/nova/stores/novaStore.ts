import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type NovaTarget = { type: 'agent'; agentId: number };

interface NovaStoreState {
  isOpen: boolean;
  requirement: string;
  selectedLlmConnectionId: number | null;
  selectedTarget: NovaTarget | null;
  activeAgentSessionIds: Record<number, number>;
  historyOpen: boolean;
  setOpen: (value: boolean) => void;
  toggleOpen: () => void;
  setRequirement: (value: string) => void;
  setSelectedLlmConnectionId: (value: number | null) => void;
  setSelectedTarget: (target: NovaTarget | null) => void;
  setActiveAgentSession: (agentId: number, sessionId: number | null) => void;
  setHistoryOpen: (value: boolean) => void;
  toggleHistoryOpen: () => void;
}

export const useNovaStore = create<NovaStoreState>()(
  persist(
    (set) => ({
      isOpen: true,
      requirement: '',
      selectedLlmConnectionId: null,
      selectedTarget: null,
      activeAgentSessionIds: {},
      historyOpen: false,
      setOpen: (value) => set({ isOpen: value }),
      toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
      setRequirement: (value) => set({ requirement: value }),
      setSelectedLlmConnectionId: (value) => set({ selectedLlmConnectionId: value }),
      setSelectedTarget: (target) => set({ selectedTarget: target, requirement: '', historyOpen: false }),
      setActiveAgentSession: (agentId, sessionId) =>
        set((state) => {
          const next = { ...state.activeAgentSessionIds };
          if (sessionId == null) delete next[agentId];
          else next[agentId] = sessionId;
          return { activeAgentSessionIds: next };
        }),
      setHistoryOpen: (value) => set({ historyOpen: value }),
      toggleHistoryOpen: () => set((state) => ({ historyOpen: !state.historyOpen })),
    }),
    {
      name: 'nova-sidebar-store',
      version: 4,
      migrate: (persistedState) => {
        const state = persistedState as Partial<NovaStoreState>;
        const selectedTarget = state.selectedTarget?.type === 'agent' ? state.selectedTarget : null;
        return {
          isOpen: state.isOpen ?? true,
          requirement: state.requirement ?? '',
          selectedLlmConnectionId: state.selectedLlmConnectionId ?? null,
          selectedTarget,
          activeAgentSessionIds: state.activeAgentSessionIds ?? {},
          historyOpen: false,
        };
      },
      partialize: (state) => ({
        isOpen: state.isOpen,
        requirement: state.requirement,
        selectedLlmConnectionId: state.selectedLlmConnectionId,
        selectedTarget: state.selectedTarget,
        activeAgentSessionIds: state.activeAgentSessionIds,
        historyOpen: state.historyOpen,
      }),
    },
  ),
);

