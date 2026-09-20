import { create } from "zustand";

export interface ActiveSessionRole {
  id: string;
  name: string;
}

interface SessionRoleState {
  activeRole: ActiveSessionRole | null;
  setActiveRole: (role: ActiveSessionRole | null) => void;
  clearActiveRole: () => void;
}

const STORAGE_KEY = "compassx_active_session_role";

const getInitialRole = (): ActiveSessionRole | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const useSessionRoleStore = create<SessionRoleState>((set) => ({
  activeRole: getInitialRole(),
  setActiveRole: (role) => {
    try {
      if (role) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(role));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
    set({ activeRole: role });
  },
  clearActiveRole: () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    set({ activeRole: null });
  },
}));

export const getActiveSessionRoleId = (): string | null => {
  return useSessionRoleStore.getState().activeRole?.id || null;
};
