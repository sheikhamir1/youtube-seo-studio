import { cn } from '../../utils/cn';

const SIZES = { sm: 'h-3.5 w-3.5', md: 'h-5 w-5', lg: 'h-8 w-8' };

export function Spinner({ size = 'md', className, label = 'Loading' }) {
  return (
    <span role="status" aria-label={label} className={cn('inline-flex', className)}>
      <span
        className={cn(
          'animate-spin rounded-full border-2 border-current border-t-transparent text-muted',
          SIZES[size],
        )}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function LoadingBlock({ label = 'Loading…', minHeight = 'min-h-[120px]' }) {
  return (
    <div className={cn('flex items-center justify-center gap-2 text-sm text-muted', minHeight)}>
      <Spinner size="sm" />
      {label}
    </div>
  );
}

export default Spinner;
