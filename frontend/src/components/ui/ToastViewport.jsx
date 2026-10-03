import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from 'lucide-react';

import { useToastStore } from '../../stores/toastStore';
import { cn } from '../../utils/cn';

const VARIANTS = {
  info: { Icon: Info, className: 'border-accent/30 text-accent' },
  success: { Icon: CheckCircle2, className: 'border-success/40 text-success' },
  warning: { Icon: TriangleAlert, className: 'border-warning/40 text-warning' },
  error: { Icon: AlertCircle, className: 'border-danger/40 text-danger' },
};

/** Renders queued toasts. Errors stay longer and are never auto-dismissed twice. */
export function ToastViewport() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (!toasts.length) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,380px)] flex-col gap-2"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const meta = VARIANTS[toast.variant] || VARIANTS.info;
        const { Icon } = meta;
        return (
          <div
            key={toast.id}
            className={cn(
              'pointer-events-auto flex items-start gap-2.5 rounded-md border bg-surface p-3 shadow-lg animate-slide-up',
              meta.className,
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-content">{toast.title}</p>
              {toast.description && (
                <p className="mt-0.5 text-xs text-muted">{toast.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="rounded p-0.5 text-muted transition-colors hover:bg-surface-2 hover:text-content"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default ToastViewport;
