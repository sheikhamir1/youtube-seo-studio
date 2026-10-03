import { cn } from '../../utils/cn';

export function StatCard({ label, value, hint, icon: Icon, variant = 'default', className }) {
  const variants = {
    default: 'text-content',
    accent: 'text-accent',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
  };
  return (
    <div className={cn('card px-4 py-3', className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
        {Icon && <Icon className="h-3.5 w-3.5 text-muted" aria-hidden="true" />}
      </div>
      <p className={cn('mt-1.5 text-2xl font-semibold tabular-nums', variants[variant])}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export default StatCard;
