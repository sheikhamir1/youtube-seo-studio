import { create } from 'zustand';

let counter = 0;

/** Lightweight toast system (never uses window.alert for app feedback). */
export const useToastStore = create((set, get) => ({
  toasts: [],
  push: ({ title, description, variant = 'info', duration = 4500 }) => {
    counter += 1;
    const id = counter;
    set((state) => ({ toasts: [...state.toasts, { id, title, description, variant }] }));
    if (duration > 0) {
      setTimeout(() => get().dismiss(id), duration);
    }
    return id;
  },
  success: (title, description) => get().push({ title, description, variant: 'success' }),
  error: (title, description) => get().push({ title, description, variant: 'error', duration: 8000 }),
  warning: (title, description) => get().push({ title, description, variant: 'warning' }),
  info: (title, description) => get().push({ title, description, variant: 'info' }),
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
  clear: () => set({ toasts: [] }),
}));
