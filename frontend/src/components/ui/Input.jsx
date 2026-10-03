import { forwardRef, useId } from 'react';

import { cn } from '../../utils/cn';

export const Input = forwardRef(function Input(
  { label, hint, error, leftAddon, rightAddon, className, id, ...rest },
  ref,
) {
  const generatedId = useId();
  const inputId = id || `input-${generatedId}`;
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium text-content">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {leftAddon && (
          <span className="pointer-events-none absolute left-2.5 text-muted">{leftAddon}</span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={hint || error ? `${inputId}-help` : undefined}
          className={cn(
            'input-base',
            leftAddon && 'pl-8',
            rightAddon && 'pr-16',
            error && 'border-danger focus:border-danger',
            className,
          )}
          {...rest}
        />
        {rightAddon && (
          <span className="absolute right-2.5 flex items-center text-xs text-muted">{rightAddon}</span>
        )}
      </div>
      {(hint || error) && (
        <p id={`${inputId}-help`} className={cn('mt-1 text-xs', error ? 'text-danger' : 'text-muted')}>
          {error || hint}
        </p>
      )}
    </div>
  );
});

export const Textarea = forwardRef(function Textarea(
  { label, hint, error, className, id, maxLength, value, ...rest },
  ref,
) {
  const generatedId = useId();
  const inputId = id || `textarea-${generatedId}`;
  const length = typeof value === 'string' ? value.length : null;
  return (
    <div className="w-full">
      {(label || maxLength) && (
        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          {label ? (
            <label htmlFor={inputId} className="block text-sm font-medium text-content">
              {label}
            </label>
          ) : (
            <span />
          )}
          {maxLength ? (
            <span className={cn('mono text-muted', length > maxLength && 'text-danger')}>
              {length ?? 0} / {maxLength}
            </span>
          ) : null}
        </div>
      )}
      <textarea
        ref={ref}
        id={inputId}
        value={value}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        className={cn('input-base min-h-[110px] resize-y', error && 'border-danger', className)}
        {...rest}
      />
      {(hint || error) && (
        <p className={cn('mt-1 text-xs', error ? 'text-danger' : 'text-muted')}>{error || hint}</p>
      )}
    </div>
  );
});

export default Input;
