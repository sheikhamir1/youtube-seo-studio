import { forwardRef } from 'react';

import { cn } from '../../utils/cn';

const VARIANTS = {
  primary: 'bg-accent text-accent-fg hover:bg-accent/90 border-transparent',
  secondary: 'bg-surface-2 text-content hover:bg-surface-2/70 border-border',
  outline: 'bg-transparent text-content hover:bg-surface-2 border-border',
  ghost: 'bg-transparent text-muted hover:bg-surface-2 hover:text-content border-transparent',
  danger: 'bg-danger/10 text-danger hover:bg-danger/20 border-danger/40',
  success: 'bg-success/10 text-success hover:bg-success/20 border-success/40',
};

const SIZES = {
  xs: 'h-7 px-2 text-xs gap-1',
  sm: 'h-8 px-2.5 text-sm gap-1.5',
  md: 'h-9 px-3.5 text-sm gap-2',
  lg: 'h-11 px-5 text-base gap-2',
};

/**
 * Button. `isLoading` disables the button and shows a determinate-looking
 * spinner, so an in-flight request can never be triggered twice.
 */
export const Button = forwardRef(function Button(
  {
    variant = 'secondary',
    size = 'md',
    isLoading = false,
    disabled = false,
    type = 'button',
    className,
    children,
    icon: Icon,
    fullWidth = false,
    title,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      title={title}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      className={cn(
        'inline-flex select-none items-center justify-center whitespace-nowrap rounded-md border',
        'font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant] || VARIANTS.secondary,
        SIZES[size] || SIZES.md,
        fullWidth && 'w-full',
        className,
      )}
      {...rest}
    >
      {isLoading ? (
        <span
          className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      ) : (
        Icon && <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      )}
      {children}
    </button>
  );
});

export default Button;
