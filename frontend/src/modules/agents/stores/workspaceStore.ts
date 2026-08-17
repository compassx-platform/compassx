import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Workspace {
  id: number;
  name: string;
  description?: string;
  created_at: string;
}

interface WorkspaceStore {
  activeWorkspaceId: number | null;
  setActiveWorkspace: (id: number | null) => void;
}

export const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set) => ({
      activeWorkspaceId: null,
      setActiveWorkspace: (id) => set({ activeWorkspaceId: id }),
    }),
    { name: "compass-active-workspace" }
  )
);
