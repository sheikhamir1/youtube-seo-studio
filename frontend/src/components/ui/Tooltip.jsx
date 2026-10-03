import { cn } from '../../utils/cn';

/**
 * Accessible tooltip built from a wrapper span: on hover/focus it shows a small
 * label. Title is mirrored for screen readers so no information is lost.
 */
export function Tooltip({ label, children, side = 'top', className }) {
  if (!label) return children;
  const positions = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-1.5',
    left: 'right-full top-1/2 -translate-y-1/2 mr-1.5',
    right: 'left-full top-1/2 -translate-y-1/2 ml-1.5',
  };
  return (
    <span className={cn('group relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute z-40 hidden whitespace-nowrap rounded border border-border',
          'bg-surface px-2 py-1 text-xs text-content shadow-md group-hover:block group-focus-within:block',
          positions[side],
        )}
      >
        {label}
      </span>
    </span>
  );
}

export default Tooltip;
