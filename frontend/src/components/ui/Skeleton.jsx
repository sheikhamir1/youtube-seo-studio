import { cn } from '../../utils/cn';

/** Loading placeholder - never used as a substitute for real data. */
export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded bg-surface-2', className)} />;
}

export function SkeletonText({ lines = 3, className }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton key={index} className={cn('h-3.5', index === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  );
}

export function SkeletonCard({ rows = 3, className }) {
  return (
    <div className={cn('card card-pad space-y-3', className)}>
      <Skeleton className="h-4 w-1/3" />
      <SkeletonText lines={rows} />
    </div>
  );
}

export function SkeletonTable({ rows = 6, columns = 4 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="grid gap-3" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
          {Array.from({ length: columns }).map((__, columnIndex) => (
            <Skeleton key={columnIndex} className="h-4" />
          ))}
        </div>
      ))}
    </div>
  );
}

export default Skeleton;
