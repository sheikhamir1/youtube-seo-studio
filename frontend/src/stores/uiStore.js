import { create } from 'zustand';

/** Local UI state only - server data lives in TanStack Query. */
export const useUiStore = create((set) => ({
  sidebarCollapsed: false,
  mobileNavOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
}));
