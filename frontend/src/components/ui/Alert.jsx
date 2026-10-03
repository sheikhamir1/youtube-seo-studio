import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react';

import { cn } from '../../utils/cn';

const VARIANTS = {
  info: { className: 'border-accent/30 bg-accent/8 text-content', Icon: Info, icon: 'text-accent' },
  success: {
    className: 'border-success/30 bg-success/8 text-content',
    Icon: CheckCircle2,
    icon: 'text-success',
  },
  warning: {
    className: 'border-warning/40 bg-warning/10 text-content',
    Icon: TriangleAlert,
    icon: 'text-warning',
  },
  error: { className: 'border-danger/40 bg-danger/10 text-content', Icon: AlertCircle, icon: 'text-danger' },
};

export function Alert({ variant = 'info', title, children, className, actions }) {
  const meta = VARIANTS[variant] || VARIANTS.info;
  const { Icon } = meta;
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-md border p-3 text-sm', meta.className, className)}
    >
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', meta.icon)} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn('text-sm text-muted', title && 'mt-0.5')}>{children}</div>}
        {actions && <div className="mt-2 flex flex-wrap gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export default Alert;
