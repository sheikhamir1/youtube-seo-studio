import { cn } from '../../utils/cn';

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact = false,
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-border text-center',
        compact ? 'gap-1.5 p-6' : 'gap-2 p-10',
        className,
      )}
    >
      {Icon && <Icon className="mb-1 h-7 w-7 text-muted" aria-hidden="true" />}
      <h3 className="text-sm font-semibold normal-case tracking-normal text-content">{title}</h3>
      {description && <p className="max-w-md text-sm text-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export default EmptyState;
