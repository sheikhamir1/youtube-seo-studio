import { cn } from '../../utils/cn';

const VARIANTS = {
  accent: 'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
};

/**
 * Progress bar. Renders a *determinate* bar with a real percentage, or an
 * indeterminate stripe for the rare moment where no percentage exists yet.
 */
export function ProgressBar({
  value = 0,
  max = 100,
  variant = 'accent',
  indeterminate = false,
  height = 'md',
  label,
  className,
  animated = false,
}) {
  const percent = max > 0 ? Math.max(0, Math.min(100, (Number(value) / max) * 100)) : 0;
  const heights = { sm: 'h-1', md: 'h-1.5', lg: 'h-2.5' };

  return (
    <div
      className={cn('w-full overflow-hidden rounded-full bg-surface-2', heights[height], className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(percent)}
      aria-label={label || 'Progress'}
    >
      {indeterminate ? (
        <div className={cn('h-full w-1/4 rounded-full', VARIANTS[variant], 'animate-indeterminate')} />
      ) : (
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-300 ease-out',
            VARIANTS[variant] || VARIANTS.accent,
            animated && 'animate-pulse',
          )}
          style={{ width: `${percent}%` }}
        />
      )}
    </div>
  );
}

export default ProgressBar;
