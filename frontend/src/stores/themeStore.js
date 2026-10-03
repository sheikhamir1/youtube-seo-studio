import { create } from 'zustand';

/**
 * Theme state: 'dark' | 'light' | 'system' (dark is the default).
 * The choice is persisted in localStorage and applied as a class on <html>.
 */
const STORAGE_KEY = 'yss-theme';

function systemPrefersLight() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: light)').matches
  );
}

export function resolveTheme(theme) {
  if (theme === 'system') return systemPrefersLight() ? 'light' : 'dark';
  return theme === 'light' ? 'light' : 'dark';
}

function readStoredTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  } catch {
    /* ignore */
  }
  return 'dark';
}

export function applyTheme(theme) {
  const resolved = resolveTheme(theme);
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', resolved === 'dark');
    document.documentElement.dataset.theme = resolved;
  }
  return resolved;
}

export const useThemeStore = create((set, get) => ({
  theme: readStoredTheme(),
  resolved: resolveTheme(readStoredTheme()),
  setTheme: (theme) => {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* ignore */
    }
    const resolved = applyTheme(theme);
    set({ theme, resolved });
  },
  cycleTheme: () => {
    const order = ['dark', 'light', 'system'];
    const next = order[(order.indexOf(get().theme) + 1) % order.length];
    get().setTheme(next);
  },
  init: () => {
    const resolved = applyTheme(get().theme);
    set({ resolved });
    if (typeof window !== 'undefined' && window.matchMedia) {
      const media = window.matchMedia('(prefers-color-scheme: light)');
      media.addEventListener?.('change', () => {
        if (get().theme === 'system') set({ resolved: applyTheme('system') });
      });
    }
  },
}));
